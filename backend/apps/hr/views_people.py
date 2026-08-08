"""People API — contracts, pay structure, leave balances, timesheets, loans,
recruitment, offboarding, training and statutory filings.

Every queryset is tenant-scoped through ``organizations_visible_to``; every state
change goes through ``apps.hr.services_people`` so the API cannot take a shortcut
a management command couldn't.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework import status as http
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.core.lookups import lookup_pk
from apps.hr import services_people as people
from apps.hr.models import (
    Applicant,
    ChecklistItem,
    CompetencyAssessment,
    CPDRecord,
    DisciplinaryAction,
    Employee,
    EmploymentContract,
    InterviewSlot,
    JobRequisition,
    LeaveBalance,
    LeaveType,
    LoanAdvance,
    OnboardingChecklist,
    PayrollAdjustment,
    PerformanceReview,
    SalaryRevision,
    SalaryStructure,
    StatutoryFiling,
    Termination,
    Timesheet,
    TrainingRecord,
)
from apps.hr.serializers_people import (
    ApplicantSerializer,
    ChecklistItemSerializer,
    CompetencyAssessmentSerializer,
    CPDRecordSerializer,
    DisciplinaryActionSerializer,
    EmploymentContractSerializer,
    InterviewSlotSerializer,
    JobRequisitionSerializer,
    LeaveBalanceSerializer,
    LeaveTypeSerializer,
    LoanAdvanceSerializer,
    OnboardingChecklistSerializer,
    PayrollAdjustmentSerializer,
    PerformanceReviewSerializer,
    SalaryRevisionSerializer,
    SalaryStructureSerializer,
    SalaryStructureWriteSerializer,
    StatutoryFilingSerializer,
    TerminationSerializer,
    TimesheetSerializer,
    TrainingRecordSerializer,
)
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User
from apps.iam.scoping import organizations_visible_to

_WRITE = {"create", "update", "partial_update", "destroy"}


class CanViewPeople(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        return bool(
            user.is_superuser
            or user.has_role("SYS_ADMIN")
            or user.has_role("ORG_ADMIN")
            or user.has_role("HR_MANAGER")
            or user.has_permission("employee.view")
        )


class CanManagePeople(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        return bool(
            user.is_superuser
            or user.has_role("SYS_ADMIN")
            or user.has_role("ORG_ADMIN")
            or user.has_role("HR_MANAGER")
            or user.has_permission("employee.manage")
        )


def _decimal(raw: Any, field: str) -> Decimal:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field: "A number is required."}) from exc


def _parse_date(raw: Any, field: str, default: date | None = None) -> date:
    if raw in (None, ""):
        if default is not None:
            return default
        raise ValidationError({field: "A date (YYYY-MM-DD) is required."})
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        raise ValidationError({field: "Use the YYYY-MM-DD format."}) from exc


class _PeopleViewSet(viewsets.ModelViewSet):
    """Shared scaffolding: permission split, org scoping, audit trail."""

    entity_type = "people_object"
    #: dotted path from the model to the owning organization
    org_path = "organization"
    permission_classes = [IsAuthenticated, CanViewPeople]

    def get_permissions(self) -> list[Any]:
        if self.action in _WRITE or self.action in getattr(self, "manage_actions", ()):
            return [IsAuthenticated(), CanManagePeople()]
        return [IsAuthenticated(), CanViewPeople()]

    def visible_orgs(self) -> QuerySet[Organization]:
        return organizations_visible_to(cast(User, self.request.user))

    def scope(self, qs: QuerySet[Any]) -> QuerySet[Any]:
        return qs.filter(**{f"{self.org_path}__in": self.visible_orgs()})

    def _audit(self, verb: str, obj: Any) -> None:
        org = getattr(obj, "organization", None) or getattr(
            getattr(obj, "employee", None), "organization", None
        )
        record_audit(
            action=verb,
            user=cast(User, self.request.user),
            organization=org,
            entity_type=self.entity_type,
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        self._audit("CREATE", serializer.save())

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        self._audit("UPDATE", serializer.save())

    def perform_destroy(self, instance: Any) -> None:
        self._audit("DELETE", instance)
        instance.delete()

    def employee_or_400(self, pk: Any) -> Employee:
        employee = Employee.objects.filter(pk=pk, organization__in=self.visible_orgs()).first()
        if employee is None:
            raise ValidationError({"employee": "Unknown or not visible."})
        return employee


# ---------------------------------------------------------------------------
# Contracts & pay
# ---------------------------------------------------------------------------


class EmploymentContractViewSet(_PeopleViewSet):
    entity_type = "employment_contract"
    org_path = "employee__organization"
    serializer_class = EmploymentContractSerializer
    queryset = EmploymentContract.objects.all()
    manage_actions = ("issue",)

    def get_queryset(self) -> QuerySet[EmploymentContract]:
        qs = self.scope(
            EmploymentContract.objects.select_related("employee", "department", "reports_to")
        )
        employee = self.request.query_params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        if self.request.query_params.get("current") == "1":
            qs = qs.filter(is_current=True)
        if self.request.query_params.get("expiring") == "1":
            qs = qs.filter(
                is_current=True,
                end_date__isnull=False,
                end_date__lte=timezone.localdate() + timedelta(days=60),
            )
        return qs

    @action(detail=False, methods=["post"])
    def issue(self, request: Request) -> Response:
        """Open a new contract, superseding whatever was current."""
        employee = self.employee_or_400(request.data.get("employee"))
        try:
            contract = people.issue_contract(
                employee=employee,
                kind=request.data.get("kind", EmploymentContract.Kind.PERMANENT),
                job_title=str(request.data.get("job_title", employee.job_title)),
                start_date=_parse_date(request.data.get("start_date"), "start_date"),
                user=cast(User, request.user),
                end_date=(
                    _parse_date(request.data.get("end_date"), "end_date")
                    if request.data.get("end_date")
                    else None
                ),
                grade=str(request.data.get("grade", "")),
                step=str(request.data.get("step", "")),
                notice_period_days=int(request.data.get("notice_period_days", 30)),
                annual_leave_days=int(request.data.get("annual_leave_days", 18)),
                probation_months=int(request.data.get("probation_months", 3)),
                terms=str(request.data.get("terms", "")),
            )
        except people.PeopleError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(EmploymentContractSerializer(contract).data, status=http.HTTP_201_CREATED)


class SalaryStructureViewSet(_PeopleViewSet):
    entity_type = "salary_structure"
    org_path = "employee__organization"
    serializer_class = SalaryStructureSerializer
    queryset = SalaryStructure.objects.all()
    # A structure is never edited in place — it is opened via set_for_employee,
    # which closes the previous one and writes the revision.
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[SalaryStructure]:
        qs = self.scope(
            SalaryStructure.objects.select_related("employee").prefetch_related("components")
        )
        employee = self.request.query_params.get("employee")
        return qs.filter(employee_id=employee) if employee else qs

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, CanManagePeople])
    def set_for_employee(self, request: Request) -> Response:
        """Open a new effective-dated structure and record the revision."""
        employee = self.employee_or_400(request.data.get("employee"))
        payload = SalaryStructureWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            structure = people.set_salary_structure(
                employee=employee,
                effective_from=data["effective_from"],
                components=data["components"],
                reason=data.get("reason") or SalaryRevision.Reason.ANNUAL_REVIEW,
                note=data.get("note", ""),
                user=cast(User, request.user),
            )
        except people.PeopleError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(SalaryStructureSerializer(structure).data, status=http.HTTP_201_CREATED)


class SalaryRevisionViewSet(_PeopleViewSet):
    entity_type = "salary_revision"
    org_path = "employee__organization"
    serializer_class = SalaryRevisionSerializer
    queryset = SalaryRevision.objects.all()
    http_method_names = ["get", "head", "options"]

    def get_queryset(self) -> QuerySet[SalaryRevision]:
        qs = self.scope(SalaryRevision.objects.select_related("employee", "approved_by"))
        employee = self.request.query_params.get("employee")
        return qs.filter(employee_id=employee) if employee else qs


# ---------------------------------------------------------------------------
# Leave
# ---------------------------------------------------------------------------


class LeaveTypeViewSet(_PeopleViewSet):
    entity_type = "leave_type"
    serializer_class = LeaveTypeSerializer
    queryset = LeaveType.objects.all()
    manage_actions = ("seed_defaults",)

    def get_queryset(self) -> QuerySet[LeaveType]:
        return self.scope(LeaveType.objects.all())

    @action(detail=False, methods=["post"])
    def seed_defaults(self, request: Request) -> Response:
        """Create the Rwanda Labour Code leave types for an organization."""
        org = Organization.objects.filter(pk=lookup_pk(request.data.get("organization"))).first()
        if org is None or not self.visible_orgs().filter(pk=org.pk).exists():
            raise ValidationError({"organization": "Unknown or not visible."})
        created = people.seed_default_leave_types(org)
        return Response(LeaveTypeSerializer(created, many=True).data, status=http.HTTP_201_CREATED)


class LeaveBalanceViewSet(_PeopleViewSet):
    entity_type = "leave_balance"
    org_path = "employee__organization"
    serializer_class = LeaveBalanceSerializer
    queryset = LeaveBalance.objects.all()
    # A balance is never edited by hand — it moves through accrual, requests and
    # approvals, each of which writes a LeaveAccrual movement for the audit trail.
    http_method_names = ["get", "post", "head", "options"]
    manage_actions = ("accrue",)

    def get_queryset(self) -> QuerySet[LeaveBalance]:
        qs = self.scope(
            LeaveBalance.objects.select_related("employee", "leave_type").prefetch_related(
                "movements"
            )
        )
        employee = self.request.query_params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        year = self.request.query_params.get("year")
        if year and year.isdigit():
            qs = qs.filter(year=int(year))
        return qs

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, CanManagePeople])
    def accrue(self, request: Request) -> Response:
        """Post this month's accrual across the organization (idempotent)."""
        org = Organization.objects.filter(pk=lookup_pk(request.data.get("organization"))).first()
        if org is None or not self.visible_orgs().filter(pk=org.pk).exists():
            raise ValidationError({"organization": "Unknown or not visible."})
        posted = people.accrue_monthly_leave(
            organization=org,
            up_to=_parse_date(request.data.get("up_to"), "up_to", timezone.localdate()),
            user=cast(User, request.user),
        )
        return Response({"movements_posted": posted})


# ---------------------------------------------------------------------------
# Timesheets
# ---------------------------------------------------------------------------


class TimesheetViewSet(_PeopleViewSet):
    entity_type = "timesheet"
    org_path = "employee__organization"
    serializer_class = TimesheetSerializer
    queryset = Timesheet.objects.all()
    manage_actions = ("build", "approve", "reject", "submit")

    def get_queryset(self) -> QuerySet[Timesheet]:
        qs = self.scope(Timesheet.objects.select_related("employee", "approved_by"))
        employee = self.request.query_params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        return qs

    @action(detail=False, methods=["post"])
    def build(self, request: Request) -> Response:
        """Derive timesheets for a period from attendance, roster and leave."""
        period_start = _parse_date(request.data.get("period_start"), "period_start")
        period_end = _parse_date(request.data.get("period_end"), "period_end")
        employee_id = request.data.get("employee")
        if employee_id:
            employees = [self.employee_or_400(employee_id)]
        else:
            org = Organization.objects.filter(
                pk=lookup_pk(request.data.get("organization"))
            ).first()
            if org is None or not self.visible_orgs().filter(pk=org.pk).exists():
                raise ValidationError({"organization": "An organization or employee is required."})
            employees = list(
                Employee.objects.filter(organization=org).exclude(
                    employment_status=Employee.Status.TERMINATED
                )
            )
        built = []
        for employee in employees:
            try:
                built.append(
                    people.build_timesheet(
                        employee=employee,
                        period_start=period_start,
                        period_end=period_end,
                        user=cast(User, request.user),
                    )
                )
            except people.PeopleError as exc:
                raise ValidationError(str(exc)) from exc
        return Response(TimesheetSerializer(built, many=True).data, status=http.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        from django.utils import timezone

        timesheet = self.get_object()
        if not timesheet.is_editable:
            raise ValidationError("Only a draft timesheet can be submitted.")
        timesheet.status = Timesheet.Status.SUBMITTED
        timesheet.submitted_at = timezone.now()
        timesheet.save(update_fields=["status", "submitted_at", "updated_at"])
        return Response(TimesheetSerializer(timesheet).data)

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        return self._decide(request, approve=True)

    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk: str | None = None) -> Response:
        return self._decide(request, approve=False)

    def _decide(self, request: Request, *, approve: bool) -> Response:
        timesheet = self.get_object()
        try:
            people.decide_timesheet(
                timesheet=timesheet,
                approve=approve,
                user=cast(User, request.user),
                reason=str(request.data.get("reason", "")),
            )
        except people.PeopleError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(TimesheetSerializer(timesheet).data)


# ---------------------------------------------------------------------------
# Loans & payroll adjustments
# ---------------------------------------------------------------------------


class LoanAdvanceViewSet(_PeopleViewSet):
    entity_type = "loan_advance"
    org_path = "employee__organization"
    serializer_class = LoanAdvanceSerializer
    queryset = LoanAdvance.objects.all()
    manage_actions = ("approve", "disburse", "write_off")

    def get_queryset(self) -> QuerySet[LoanAdvance]:
        qs = self.scope(
            LoanAdvance.objects.select_related("employee", "guarantor").prefetch_related(
                "installments"
            )
        )
        employee = self.request.query_params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        return qs

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Raise a loan and lay out its repayment schedule."""
        employee = self.employee_or_400(request.data.get("employee"))
        try:
            loan = people.create_loan(
                employee=employee,
                principal=_decimal(request.data.get("principal"), "principal"),
                installments_count=int(request.data.get("installments_count", 1)),
                kind=request.data.get("kind", LoanAdvance.Kind.SALARY_ADVANCE),
                interest_rate_pct=_decimal(
                    request.data.get("interest_rate_pct", 0), "interest_rate_pct"
                ),
                start_date=(
                    _parse_date(request.data.get("start_date"), "start_date")
                    if request.data.get("start_date")
                    else None
                ),
                reason=str(request.data.get("reason", "")),
                user=cast(User, request.user),
            )
        except people.PeopleError as exc:
            raise ValidationError(str(exc)) from exc
        self._audit("CREATE", loan)
        return Response(LoanAdvanceSerializer(loan).data, status=http.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        loan = self.get_object()
        try:
            people.approve_loan(loan=loan, user=cast(User, request.user))
        except people.PeopleError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(LoanAdvanceSerializer(loan).data)

    @action(detail=True, methods=["post"])
    def disburse(self, request: Request, pk: str | None = None) -> Response:
        loan = self.get_object()
        if loan.status != LoanAdvance.Status.ACTIVE:
            raise ValidationError("Approve the loan before disbursing it.")
        loan.disbursed_on = _parse_date(
            request.data.get("disbursed_on"), "disbursed_on", timezone.localdate()
        )
        loan.disbursement_method = str(request.data.get("method", "BANK"))
        loan.disbursement_reference = str(request.data.get("reference", ""))
        loan.save(
            update_fields=[
                "disbursed_on",
                "disbursement_method",
                "disbursement_reference",
                "updated_at",
            ]
        )
        self._audit("LOAN_DISBURSED", loan)
        return Response(LoanAdvanceSerializer(loan).data)

    @action(detail=True, methods=["post"])
    def write_off(self, request: Request, pk: str | None = None) -> Response:
        loan = self.get_object()
        reason = str(request.data.get("reason", ""))
        if not reason.strip():
            raise ValidationError({"reason": "Writing off a loan requires a reason."})
        loan.status = LoanAdvance.Status.WRITTEN_OFF
        loan.reason = f"{loan.reason}\nWritten off: {reason}".strip()
        loan.save(update_fields=["status", "reason", "updated_at"])
        self._audit("LOAN_WRITTEN_OFF", loan)
        return Response(LoanAdvanceSerializer(loan).data)


class PayrollAdjustmentViewSet(_PeopleViewSet):
    entity_type = "payroll_adjustment"
    org_path = "employee__organization"
    serializer_class = PayrollAdjustmentSerializer
    queryset = PayrollAdjustment.objects.all()

    def get_queryset(self) -> QuerySet[PayrollAdjustment]:
        qs = self.scope(PayrollAdjustment.objects.select_related("employee"))
        employee = self.request.query_params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        if self.request.query_params.get("unapplied") == "1":
            qs = qs.filter(applied_run__isnull=True)
        return qs


# ---------------------------------------------------------------------------
# Recruitment & onboarding
# ---------------------------------------------------------------------------


class JobRequisitionViewSet(_PeopleViewSet):
    entity_type = "job_requisition"
    serializer_class = JobRequisitionSerializer
    queryset = JobRequisition.objects.all()
    manage_actions = ("open_requisition", "close_requisition")

    def get_queryset(self) -> QuerySet[JobRequisition]:
        qs = self.scope(
            JobRequisition.objects.select_related(
                "organization", "department", "hiring_manager"
            ).prefetch_related("applicants__interviews")
        )
        status_param = self.request.query_params.get("status")
        return qs.filter(status=status_param.upper()) if status_param else qs

    @action(detail=True, methods=["post"], url_path="open")
    def open_requisition(self, request: Request, pk: str | None = None) -> Response:
        requisition = self.get_object()
        if requisition.status not in {
            JobRequisition.Status.DRAFT,
            JobRequisition.Status.PENDING_APPROVAL,
            JobRequisition.Status.ON_HOLD,
        }:
            raise ValidationError("Only a draft, pending or held requisition can be opened.")
        requisition.status = JobRequisition.Status.OPEN
        requisition.opened_at = requisition.opened_at or timezone.localdate()
        requisition.save(update_fields=["status", "opened_at", "updated_at"])
        self._audit("REQUISITION_OPENED", requisition)
        return Response(JobRequisitionSerializer(requisition).data)

    @action(detail=True, methods=["post"], url_path="close")
    def close_requisition(self, request: Request, pk: str | None = None) -> Response:
        requisition = self.get_object()
        requisition.status = JobRequisition.Status.CANCELLED
        requisition.save(update_fields=["status", "updated_at"])
        self._audit("REQUISITION_CLOSED", requisition)
        return Response(JobRequisitionSerializer(requisition).data)


class ApplicantViewSet(_PeopleViewSet):
    entity_type = "applicant"
    org_path = "requisition__organization"
    serializer_class = ApplicantSerializer
    queryset = Applicant.objects.all()
    manage_actions = ("advance", "reject", "hire")

    def get_queryset(self) -> QuerySet[Applicant]:
        qs = self.scope(
            Applicant.objects.select_related("requisition").prefetch_related("interviews")
        )
        requisition = self.request.query_params.get("requisition")
        if requisition:
            qs = qs.filter(requisition_id=requisition)
        stage = self.request.query_params.get("stage")
        return qs.filter(stage=stage.upper()) if stage else qs

    @action(detail=True, methods=["post"])
    def advance(self, request: Request, pk: str | None = None) -> Response:
        """Move the applicant to the next stage of the funnel."""
        applicant = self.get_object()
        order = [
            Applicant.Stage.APPLIED,
            Applicant.Stage.SCREENED,
            Applicant.Stage.SHORTLISTED,
            Applicant.Stage.INTERVIEWED,
            Applicant.Stage.OFFERED,
        ]
        target = request.data.get("stage")
        if target:
            applicant.stage = str(target).upper()
        else:
            if applicant.stage not in order or applicant.stage == order[-1]:
                raise ValidationError("This applicant cannot advance any further automatically.")
            applicant.stage = order[order.index(applicant.stage) + 1]
        if applicant.stage == Applicant.Stage.OFFERED:
            applicant.offer_sent_on = timezone.localdate()
            if request.data.get("offered_salary"):
                applicant.offered_salary = _decimal(
                    request.data["offered_salary"], "offered_salary"
                )
        applicant.save()
        self._audit("APPLICANT_ADVANCED", applicant)
        return Response(ApplicantSerializer(applicant).data)

    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk: str | None = None) -> Response:
        applicant = self.get_object()
        applicant.stage = Applicant.Stage.REJECTED
        applicant.rejection_reason = str(request.data.get("reason", ""))
        applicant.save(update_fields=["stage", "rejection_reason", "updated_at"])
        return Response(ApplicantSerializer(applicant).data)

    @action(detail=True, methods=["post"])
    def hire(self, request: Request, pk: str | None = None) -> Response:
        """Convert the applicant into an employee, contract and onboarding."""
        applicant = self.get_object()
        try:
            employee = people.hire_applicant(
                applicant=applicant,
                organization=applicant.requisition.organization,
                hire_date=_parse_date(
                    request.data.get("hire_date"), "hire_date", timezone.localdate()
                ),
                user=cast(User, request.user),
            )
        except people.PeopleError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {"employee_id": employee.pk, "applicant": ApplicantSerializer(applicant).data},
            status=http.HTTP_201_CREATED,
        )


class InterviewSlotViewSet(_PeopleViewSet):
    entity_type = "interview_slot"
    org_path = "applicant__requisition__organization"
    serializer_class = InterviewSlotSerializer
    queryset = InterviewSlot.objects.all()

    def get_queryset(self) -> QuerySet[InterviewSlot]:
        qs = self.scope(InterviewSlot.objects.select_related("applicant"))
        applicant = self.request.query_params.get("applicant")
        return qs.filter(applicant_id=applicant) if applicant else qs


class OnboardingViewSet(_PeopleViewSet):
    entity_type = "onboarding_checklist"
    org_path = "employee__organization"
    serializer_class = OnboardingChecklistSerializer
    queryset = OnboardingChecklist.objects.all()
    manage_actions = ("start",)

    def get_queryset(self) -> QuerySet[OnboardingChecklist]:
        qs = self.scope(
            OnboardingChecklist.objects.select_related("employee").prefetch_related("items")
        )
        employee = self.request.query_params.get("employee")
        return qs.filter(employee_id=employee) if employee else qs

    @action(detail=False, methods=["post"])
    def start(self, request: Request) -> Response:
        employee = self.employee_or_400(request.data.get("employee"))
        checklist = people.start_onboarding(employee=employee, user=cast(User, request.user))
        return Response(OnboardingChecklistSerializer(checklist).data, status=http.HTTP_201_CREATED)


class ChecklistItemViewSet(_PeopleViewSet):
    entity_type = "checklist_item"
    serializer_class = ChecklistItemSerializer
    queryset = ChecklistItem.objects.all()
    manage_actions = ("toggle",)

    def get_queryset(self) -> QuerySet[ChecklistItem]:
        # An item hangs off either an onboarding checklist or a termination, so
        # scoping has to reach the organization down both paths.
        orgs = self.visible_orgs()
        qs = ChecklistItem.objects.filter(
            Q(onboarding__employee__organization__in=orgs)
            | Q(termination__employee__organization__in=orgs)
        )
        onboarding = self.request.query_params.get("onboarding")
        if onboarding:
            qs = qs.filter(onboarding_id=lookup_pk(onboarding))
        termination = self.request.query_params.get("termination")
        if termination:
            qs = qs.filter(termination_id=termination)
        return qs.distinct()

    @action(detail=True, methods=["post"])
    def toggle(self, request: Request, pk: str | None = None) -> Response:
        from django.utils import timezone

        item = self.get_object()
        item.is_done = not item.is_done
        item.completed_at = timezone.now() if item.is_done else None
        item.completed_by = cast(User, request.user) if item.is_done else None
        item.save(update_fields=["is_done", "completed_at", "completed_by"])
        return Response(ChecklistItemSerializer(item).data)


# ---------------------------------------------------------------------------
# Offboarding
# ---------------------------------------------------------------------------


class TerminationViewSet(_PeopleViewSet):
    entity_type = "termination"
    org_path = "employee__organization"
    serializer_class = TerminationSerializer
    queryset = Termination.objects.all()
    manage_actions = ("initiate", "approve", "recompute", "mark_paid")

    def get_queryset(self) -> QuerySet[Termination]:
        qs = self.scope(
            Termination.objects.select_related("employee", "settlement").prefetch_related("items")
        )
        status_param = self.request.query_params.get("status")
        return qs.filter(status=status_param.upper()) if status_param else qs

    @action(detail=False, methods=["post"])
    def initiate(self, request: Request) -> Response:
        employee = self.employee_or_400(request.data.get("employee"))
        try:
            termination = people.initiate_termination(
                employee=employee,
                reason=request.data.get("reason", Termination.Reason.RESIGNATION),
                last_working_day=_parse_date(
                    request.data.get("last_working_day"), "last_working_day"
                ),
                user=cast(User, request.user),
                notice_given_on=(
                    _parse_date(request.data.get("notice_given_on"), "notice_given_on")
                    if request.data.get("notice_given_on")
                    else None
                ),
                notice_period_served=bool(request.data.get("notice_period_served", True)),
                detail=str(request.data.get("detail", "")),
            )
        except people.PeopleError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(TerminationSerializer(termination).data, status=http.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        termination = self.get_object()
        try:
            people.approve_termination(termination=termination, user=cast(User, request.user))
        except people.PeopleError as exc:
            raise ValidationError(str(exc)) from exc
        termination.refresh_from_db()
        return Response(TerminationSerializer(termination).data)

    @action(detail=True, methods=["post"])
    def recompute(self, request: Request, pk: str | None = None) -> Response:
        """Re-run the final settlement (after clearing a loan, say)."""
        termination = self.get_object()
        people.compute_final_settlement(termination=termination, user=cast(User, request.user))
        termination.refresh_from_db()
        return Response(TerminationSerializer(termination).data)

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request: Request, pk: str | None = None) -> Response:
        from django.utils import timezone

        termination = self.get_object()
        settlement = getattr(termination, "settlement", None)
        if settlement is None:
            raise ValidationError("Compute the final settlement first.")
        settlement.status = settlement.Status.PAID
        settlement.paid_on = _parse_date(
            request.data.get("paid_on"), "paid_on", timezone.localdate()
        )
        settlement.payment_method = str(request.data.get("method", "BANK"))
        settlement.payment_reference = str(request.data.get("reference", ""))
        settlement.approved_by = cast(User, request.user)
        settlement.approved_at = timezone.now()
        settlement.save()
        termination.status = Termination.Status.SETTLED
        termination.save(update_fields=["status", "updated_at"])
        self._audit("FINAL_SETTLEMENT_PAID", termination)
        return Response(TerminationSerializer(termination).data)


# ---------------------------------------------------------------------------
# Training, CPD, competency, discipline, performance
# ---------------------------------------------------------------------------


class TrainingRecordViewSet(_PeopleViewSet):
    entity_type = "training_record"
    org_path = "employee__organization"
    serializer_class = TrainingRecordSerializer
    queryset = TrainingRecord.objects.all()
    manage_actions = ("acknowledge", "complete")

    def get_queryset(self) -> QuerySet[TrainingRecord]:
        qs = self.scope(TrainingRecord.objects.select_related("employee"))
        employee = self.request.query_params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        if self.request.query_params.get("overdue") == "1":
            qs = qs.filter(
                status__in=[TrainingRecord.Status.ASSIGNED, TrainingRecord.Status.IN_PROGRESS],
                due_on__lt=timezone.localdate(),
            )
        return qs

    @action(detail=True, methods=["post"])
    def acknowledge(self, request: Request, pk: str | None = None) -> Response:
        from django.utils import timezone

        record = self.get_object()
        record.acknowledged_at = timezone.now()
        record.status = TrainingRecord.Status.COMPLETED
        record.completed_on = timezone.localdate()
        record.save(update_fields=["acknowledged_at", "status", "completed_on"])
        return Response(TrainingRecordSerializer(record).data)

    @action(detail=True, methods=["post"])
    def complete(self, request: Request, pk: str | None = None) -> Response:
        record = self.get_object()
        record.status = TrainingRecord.Status.COMPLETED
        record.completed_on = _parse_date(
            request.data.get("completed_on"), "completed_on", timezone.localdate()
        )
        if request.data.get("score") not in (None, ""):
            record.score = _decimal(request.data["score"], "score")
        record.certificate_number = str(
            request.data.get("certificate_number", record.certificate_number)
        )
        record.save()
        return Response(TrainingRecordSerializer(record).data)


class CPDRecordViewSet(_PeopleViewSet):
    entity_type = "cpd_record"
    org_path = "employee__organization"
    serializer_class = CPDRecordSerializer
    queryset = CPDRecord.objects.all()
    manage_actions = ("verify",)

    def get_queryset(self) -> QuerySet[CPDRecord]:
        qs = self.scope(CPDRecord.objects.select_related("employee"))
        employee = self.request.query_params.get("employee")
        return qs.filter(employee_id=employee) if employee else qs

    @action(detail=True, methods=["post"])
    def verify(self, request: Request, pk: str | None = None) -> Response:
        from django.utils import timezone

        record = self.get_object()
        record.verified_by = cast(User, request.user)
        record.verified_at = timezone.now()
        record.save(update_fields=["verified_by", "verified_at"])
        return Response(CPDRecordSerializer(record).data)


class CompetencyAssessmentViewSet(_PeopleViewSet):
    entity_type = "competency_assessment"
    org_path = "employee__organization"
    serializer_class = CompetencyAssessmentSerializer
    queryset = CompetencyAssessment.objects.all()

    def get_queryset(self) -> QuerySet[CompetencyAssessment]:
        qs = self.scope(CompetencyAssessment.objects.select_related("employee", "assessor"))
        employee = self.request.query_params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        competency = self.request.query_params.get("competency")
        return qs.filter(competency=competency.upper()) if competency else qs


class DisciplinaryActionViewSet(_PeopleViewSet):
    entity_type = "disciplinary_action"
    org_path = "employee__organization"
    serializer_class = DisciplinaryActionSerializer
    queryset = DisciplinaryAction.objects.all()
    manage_actions = ("issue",)

    def get_queryset(self) -> QuerySet[DisciplinaryAction]:
        qs = self.scope(DisciplinaryAction.objects.select_related("employee"))
        employee = self.request.query_params.get("employee")
        return qs.filter(employee_id=employee) if employee else qs

    @action(detail=True, methods=["post"])
    def issue(self, request: Request, pk: str | None = None) -> Response:
        action_record = self.get_object()
        if action_record.status != DisciplinaryAction.Status.DRAFT:
            raise ValidationError("Only a draft action can be issued.")
        action_record.status = DisciplinaryAction.Status.ISSUED
        action_record.issued_on = timezone.localdate()
        action_record.issued_by = cast(User, request.user)
        action_record.save(update_fields=["status", "issued_on", "issued_by"])
        self._audit("DISCIPLINARY_ISSUED", action_record)
        return Response(DisciplinaryActionSerializer(action_record).data)


class PerformanceReviewViewSet(_PeopleViewSet):
    entity_type = "performance_review"
    org_path = "employee__organization"
    serializer_class = PerformanceReviewSerializer
    queryset = PerformanceReview.objects.all()
    manage_actions = ("acknowledge", "complete")

    def get_queryset(self) -> QuerySet[PerformanceReview]:
        qs = self.scope(PerformanceReview.objects.select_related("employee", "reviewer"))
        employee = self.request.query_params.get("employee")
        return qs.filter(employee_id=employee) if employee else qs

    @action(detail=True, methods=["post"])
    def acknowledge(self, request: Request, pk: str | None = None) -> Response:
        from django.utils import timezone

        review = self.get_object()
        review.employee_comments = str(request.data.get("comments", review.employee_comments))
        review.acknowledged_at = timezone.now()
        review.status = PerformanceReview.Status.COMPLETED
        review.completed_at = timezone.now()
        review.save()
        return Response(PerformanceReviewSerializer(review).data)

    @action(detail=True, methods=["post"])
    def complete(self, request: Request, pk: str | None = None) -> Response:
        from django.utils import timezone

        review = self.get_object()
        review.status = PerformanceReview.Status.AWAITING_ACK
        review.completed_at = timezone.now()
        review.save(update_fields=["status", "completed_at", "updated_at"])
        return Response(PerformanceReviewSerializer(review).data)


# ---------------------------------------------------------------------------
# Statutory filings & dashboards
# ---------------------------------------------------------------------------


class StatutoryFilingViewSet(_PeopleViewSet):
    entity_type = "statutory_filing"
    serializer_class = StatutoryFilingSerializer
    queryset = StatutoryFiling.objects.all()
    manage_actions = ("generate", "mark_filed", "mark_paid")

    def get_queryset(self) -> QuerySet[StatutoryFiling]:
        qs = self.scope(StatutoryFiling.objects.select_related("organization"))
        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind.upper())
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        if self.request.query_params.get("due") == "1":
            qs = qs.exclude(
                status__in=[StatutoryFiling.Status.FILED, StatutoryFiling.Status.FILED_PAID]
            )
        return qs

    @action(detail=False, methods=["post"])
    def generate(self, request: Request) -> Response:
        """Aggregate the period's payroll into a return, ready to file."""
        from apps.hr.statutory import generate_filing

        org = Organization.objects.filter(pk=lookup_pk(request.data.get("organization"))).first()
        if org is None or not self.visible_orgs().filter(pk=org.pk).exists():
            raise ValidationError({"organization": "Unknown or not visible."})
        try:
            filing = generate_filing(
                organization=org,
                kind=str(request.data.get("kind", StatutoryFiling.Kind.PAYE_MONTHLY)),
                period_start=_parse_date(request.data.get("period_start"), "period_start"),
                period_end=_parse_date(request.data.get("period_end"), "period_end"),
                user=cast(User, request.user),
            )
        except people.PeopleError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(StatutoryFilingSerializer(filing).data, status=http.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="mark-filed")
    def mark_filed(self, request: Request, pk: str | None = None) -> Response:
        filing = self.get_object()
        if filing.status not in {StatutoryFiling.Status.GENERATED, StatutoryFiling.Status.DRAFT}:
            raise ValidationError("Only a generated filing can be marked filed.")
        if not filing.ties_to_ledger:
            raise ValidationError(
                f"The filing amount ({filing.amount_due}) does not tie to the GL sub-ledger "
                f"balance ({filing.gl_balance_at_generation}). Reconcile before filing."
            )
        filing.status = StatutoryFiling.Status.FILED
        filing.filed_on = timezone.localdate()
        filing.filed_by = cast(User, request.user)
        filing.authority_reference = str(request.data.get("authority_reference", ""))
        filing.save()
        self._audit("STATUTORY_FILED", filing)
        return Response(StatutoryFilingSerializer(filing).data)

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request: Request, pk: str | None = None) -> Response:
        filing = self.get_object()
        if filing.status != StatutoryFiling.Status.FILED:
            raise ValidationError("File the return before recording its payment.")
        filing.status = StatutoryFiling.Status.FILED_PAID
        filing.save(update_fields=["status", "updated_at"])
        self._audit("STATUTORY_PAID", filing)
        return Response(StatutoryFilingSerializer(filing).data)


class PeopleOverviewView(APIView):
    """Headline numbers and the compliance warning list for the People home."""

    permission_classes = [IsAuthenticated, CanViewPeople]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        orgs = organizations_visible_to(user)
        org = (
            orgs.filter(pk=lookup_pk(request.query_params.get("organization"))).first()
            if request.query_params.get("organization")
            else orgs.first()
        )
        if org is None:
            raise PermissionDenied("No visible organization.")

        employees = Employee.objects.filter(organization=org)
        active = employees.exclude(employment_status=Employee.Status.TERMINATED)
        today = timezone.localdate()
        return Response(
            {
                "organization_id": org.pk,
                "headcount": active.count(),
                "on_probation": active.filter(employment_status=Employee.Status.PROBATION).count(),
                "present_today": active.filter(
                    attendance_logs__date=today,
                    attendance_logs__status__in=["PRESENT", "LATE"],
                )
                .distinct()
                .count(),
                "on_leave_today": active.filter(
                    leave_requests__status="APPROVED",
                    leave_requests__start_date__lte=today,
                    leave_requests__end_date__gte=today,
                )
                .distinct()
                .count(),
                "leave_requests_pending": active.filter(leave_requests__status="PENDING")
                .distinct()
                .count(),
                "timesheets_pending": Timesheet.objects.filter(
                    employee__organization=org,
                    status__in=[Timesheet.Status.DRAFT, Timesheet.Status.SUBMITTED],
                ).count(),
                "loans_active": LoanAdvance.objects.filter(
                    employee__organization=org, status=LoanAdvance.Status.ACTIVE
                ).count(),
                "open_requisitions": JobRequisition.objects.filter(
                    organization=org, status=JobRequisition.Status.OPEN
                ).count(),
                "applicants_in_funnel": Applicant.objects.filter(requisition__organization=org)
                .exclude(stage__in=[Applicant.Stage.HIRED, Applicant.Stage.REJECTED])
                .count(),
                "training_overdue": TrainingRecord.objects.filter(
                    employee__organization=org,
                    status__in=[TrainingRecord.Status.ASSIGNED, TrainingRecord.Status.IN_PROGRESS],
                    due_on__lt=today,
                ).count(),
                "filings_due": StatutoryFiling.objects.filter(organization=org, due_date__gte=today)
                .exclude(
                    status__in=[StatutoryFiling.Status.FILED, StatutoryFiling.Status.FILED_PAID]
                )
                .count(),
                "filings_overdue": StatutoryFiling.objects.filter(
                    organization=org, due_date__lt=today
                )
                .exclude(
                    status__in=[StatutoryFiling.Status.FILED, StatutoryFiling.Status.FILED_PAID]
                )
                .count(),
                "alerts": people.compliance_alerts(org),
            }
        )
