"""HR API: the Employee master, its documents, and the approval-gated offboarding
(termination) flow."""

from __future__ import annotations

from datetime import date
from typing import cast

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.core.lookups import lookup_pk
from apps.hr.models import (
    AttendanceLog,
    Employee,
    EmployeeDocument,
    LeaveRequest,
    PayrollRun,
    ShiftRoster,
    StatutoryRate,
)
from apps.hr.payroll_run import build_payroll_run, mark_payroll_run_paid, submit_payroll_run
from apps.hr.serializers import (
    AttendanceLogSerializer,
    EmployeeDocumentSerializer,
    EmployeeSerializer,
    LeaveRequestSerializer,
    PayrollRunSerializer,
    ShiftRosterSerializer,
    StatutoryRateSerializer,
)
from apps.hr.services import clock_attendance
from apps.hr.services import request_termination as request_termination_approval
from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to


def _require_hr_manage(user: User) -> None:
    if not (user.is_superuser or user.has_permission("employee.manage")):
        raise PermissionDenied("You may not manage employee records.")


class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.select_related(
        "organization", "department", "license", "user"
    ).prefetch_related("documents")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[Employee]:
        user = cast(User, self.request.user)
        qs = Employee.objects.select_related(
            "organization", "department", "license", "user"
        ).prefetch_related("documents")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            if not user.has_permission("employee.view"):
                raise PermissionDenied("You may not view employee records.")
            qs = qs.filter(organization__in=organizations_visible_to(user))
        org_param = self.request.query_params.get("organization")
        if org_param and org_param.isdigit():
            qs = qs.filter(organization_id=int(org_param))
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(employment_status=status_param.upper())
        return qs

    def perform_create(self, serializer: BaseSerializer) -> None:
        user = cast(User, self.request.user)
        _require_hr_manage(user)
        employee = serializer.save()
        record_audit(
            action="CREATE",
            user=user,
            organization=employee.organization,
            entity_type="employee",
            entity_id=str(employee.pk),
            request=self.request,
        )

    def perform_update(self, serializer: BaseSerializer) -> None:
        _require_hr_manage(cast(User, self.request.user))
        serializer.save()

    @action(detail=True, methods=["post"], url_path="documents")
    def add_document(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_hr_manage(user)
        employee = self.get_object()
        serializer = EmployeeDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = EmployeeDocument.objects.create(
            employee=employee, uploaded_by=user, **serializer.validated_data
        )
        return Response(EmployeeDocumentSerializer(doc).data, status=201)

    @action(detail=True, methods=["post"], url_path="request-termination")
    def request_termination(self, request: Request, pk: str | None = None) -> Response:
        """Propose ending this employee's employment — routed through the
        approvals engine (no self-approval, senior sign-off required)."""
        user = cast(User, request.user)
        _require_hr_manage(user)
        employee = self.get_object()
        if employee.employment_status == Employee.Status.TERMINATED:
            raise ValidationError("This employee is already terminated.")
        reason = str(request.data.get("reason", ""))
        if not reason:
            raise ValidationError("A reason is required to request termination.")
        approval = request_termination_approval(
            employee=employee,
            requested_by=user,
            reason=reason,
            effective_date=request.data.get("effective_date"),
        )
        return Response({"approval_request": approval.pk, "status": approval.status}, status=201)


class StatutoryRateViewSet(viewsets.ReadOnlyModelViewSet):
    """The versioned PAYE/RSSB/CBHI rate table the payroll engine reads from."""

    permission_classes = [IsAuthenticated]

    serializer_class = StatutoryRateSerializer
    queryset = StatutoryRate.objects.all()


class PayrollRunViewSet(viewsets.ModelViewSet):
    """Payroll runs: build (compute) → submit (approval-gated) → the approvals
    engine's approve/reject decides it → mark paid (bank/MoMo disbursement)."""

    serializer_class = PayrollRunSerializer
    queryset = PayrollRun.objects.select_related(
        "organization", "created_by", "approved_by"
    ).prefetch_related("records__employee")
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[PayrollRun]:
        user = cast(User, self.request.user)
        qs = PayrollRun.objects.select_related(
            "organization", "created_by", "approved_by"
        ).prefetch_related("records__employee")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            if not user.has_permission("employee.manage"):
                raise PermissionDenied("You may not view payroll runs.")
            qs = qs.filter(organization__in=organizations_visible_to(user))
        org_param = self.request.query_params.get("organization")
        if org_param and org_param.isdigit():
            qs = qs.filter(organization_id=int(org_param))
        return qs

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        user = cast(User, request.user)
        _require_hr_manage(user)
        org_id = request.data.get("organization")
        try:
            from apps.iam.models import Organization

            organization = Organization.objects.get(pk=str(org_id))
        except (Organization.DoesNotExist, TypeError, ValueError) as exc:
            raise ValidationError("A valid 'organization' id is required.") from exc
        period_start = request.data.get("period_start")
        period_end = request.data.get("period_end")
        if not period_start or not period_end:
            raise ValidationError("'period_start' and 'period_end' are required.")
        if PayrollRun.objects.filter(
            organization=organization, period_start=period_start, period_end=period_end
        ).exists():
            raise ValidationError("A payroll run already exists for this organization and period.")
        run = build_payroll_run(
            organization=organization,
            period_start=period_start,
            period_end=period_end,
            created_by=user,
        )
        record_audit(
            action="CREATE",
            user=user,
            organization=organization,
            entity_type="payroll_run",
            entity_id=str(run.pk),
            request=request,
        )
        return Response(PayrollRunSerializer(run).data, status=201)

    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_hr_manage(user)
        run = self.get_object()
        try:
            submit_payroll_run(run=run, requested_by=user)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        run.refresh_from_db()
        return Response(PayrollRunSerializer(run).data)

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_hr_manage(user)
        run = self.get_object()
        try:
            mark_payroll_run_paid(run=run, user=user)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        run.refresh_from_db()
        return Response(PayrollRunSerializer(run).data)


class AttendanceLogViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAuthenticated]
    serializer_class = AttendanceLogSerializer
    queryset = AttendanceLog.objects.select_related("employee")

    def get_queryset(self) -> QuerySet[AttendanceLog]:
        user = cast(User, self.request.user)
        qs = AttendanceLog.objects.select_related("employee")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(employee__organization__in=organizations_visible_to(user))
        # Filter to the caller's own employee records (e.g. for the clock-in
        # toolbar — the front-end needs to know whether the user has already
        # punched in today).
        user_param = self.request.query_params.get("user")
        if user_param and user_param.isdigit():
            qs = qs.filter(employee__user_id=int(user_param))
        date_param = self.request.query_params.get("date")
        if date_param:
            qs = qs.filter(date=date_param)
        return qs

    def perform_create(self, serializer: BaseSerializer) -> None:
        _require_hr_manage(cast(User, self.request.user))
        serializer.save()

    @action(detail=False, methods=["post"], url_path="clock")
    def clock(self, request: Request) -> Response:
        """Toggle today's attendance for the caller. Resolves the employee from
        the user's employee record; HR users can pass ``?employee_id=<id>`` to
        act on behalf of someone else (e.g. a manager marking the floor)."""
        user = cast(User, request.user)
        direction = str(request.data.get("direction", "")).upper()
        if direction not in {"IN", "OUT"}:
            raise ValidationError("direction must be 'IN' or 'OUT'.")

        override_id = request.query_params.get("employee_id")
        if override_id:
            _require_hr_manage(user)
            try:
                employee = Employee.objects.get(pk=int(override_id))
            except (Employee.DoesNotExist, ValueError, TypeError) as exc:
                raise ValidationError("Unknown employee_id.") from exc
        else:
            employee = Employee.objects.filter(user=user).first()  # type: ignore[assignment]
            if employee is None:
                raise ValidationError(
                    "No employee record is linked to this user — cannot clock in/out."
                )

        try:
            log = clock_attendance(employee=employee, direction=direction, user=user)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(AttendanceLogSerializer(log).data, status=201)


class ShiftRosterViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAuthenticated]
    serializer_class = ShiftRosterSerializer
    queryset = ShiftRoster.objects.select_related("organization", "employee")

    def get_queryset(self) -> QuerySet[ShiftRoster]:
        user = cast(User, self.request.user)
        qs = ShiftRoster.objects.select_related("organization", "employee")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        return qs

    def perform_create(self, serializer: BaseSerializer) -> None:
        _require_hr_manage(cast(User, self.request.user))
        serializer.save()


class LeaveRequestViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAuthenticated]
    serializer_class = LeaveRequestSerializer
    queryset = LeaveRequest.objects.select_related("employee", "approved_by")

    def get_queryset(self) -> QuerySet[LeaveRequest]:
        user = cast(User, self.request.user)
        qs = LeaveRequest.objects.select_related("employee", "approved_by")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(employee__organization__in=organizations_visible_to(user))
        return qs

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Book leave through the service so it is held against a real balance.

        Creating the row directly would let two requests spend the same day and
        would let someone book leave they have not accrued.
        """
        from apps.hr import services_people as people
        from apps.hr.models import Employee, LeaveType

        employee = Employee.objects.filter(
            pk=lookup_pk(request.data.get("employee")),
            organization__in=organizations_visible_to(cast(User, request.user)),
        ).first()
        if employee is None:
            raise ValidationError({"employee": "Unknown or not visible."})

        code = str(request.data.get("leave_type", "ANNUAL")).upper()
        leave_type = LeaveType.objects.filter(organization=employee.organization, code=code).first()
        if leave_type is None:
            raise ValidationError(
                {
                    "leave_type": f"'{code}' is not configured for {employee.organization.name}. "
                    "Seed the organization's leave types first."
                }
            )
        try:
            leave = people.request_leave(
                employee=employee,
                leave_type=leave_type,
                start_date=date.fromisoformat(str(request.data["start_date"])),
                end_date=date.fromisoformat(str(request.data["end_date"])),
                reason=str(request.data.get("reason", "")),
                user=cast(User, request.user),
            )
        except (KeyError, ValueError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(LeaveRequestSerializer(leave).data, status=201)

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        return self._decide(request, approve=True)

    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk: str | None = None) -> Response:
        return self._decide(request, approve=False)

    def _decide(self, request: Request, *, approve: bool) -> Response:
        """Approve or reject, converting or releasing the days held on the balance."""
        from apps.hr import services_people as people

        user = cast(User, request.user)
        _require_hr_manage(user)
        leave = self.get_object()
        try:
            people.decide_leave(
                request=leave,
                approve=approve,
                user=user,
                note=str(request.data.get("note", "")),
            )
        except people.PeopleError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(LeaveRequestSerializer(leave).data)
