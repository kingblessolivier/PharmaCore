"""HR services: employee-number allocation, the approval-gated termination flow,
and the attendance clock in/out flow.

Offboarding (termination) is never self-approved and never immediate — it always
routes through the approvals engine (see docs/12 §4, ROADMAP "13. Approve & authorise").
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.approvals import registry
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import request_approval
from apps.hr.models import AttendanceLog, Employee
from apps.iam.audit import record_audit
from apps.iam.models import User


def allocate_employee_number(employee: Employee) -> str:
    return f"EMP-{employee.pk:05d}"


def request_termination(
    *, employee: Employee, requested_by: User, reason: str, effective_date: Any = None
) -> ApprovalRequest:
    eff = effective_date or timezone.now().date()
    return request_approval(
        resource_type="hr.employee_termination",
        resource_id=str(employee.pk),
        organization=employee.organization,
        requested_by=requested_by,
        payload={"effective_date": str(eff)},
        reason=reason,
    )


@registry.register("hr.employee_termination")
@transaction.atomic
def _apply_termination(approval: ApprovalRequest) -> None:
    employee = Employee.objects.select_related("user").get(pk=int(approval.resource_id))
    employee.employment_status = Employee.Status.TERMINATED
    employee.end_date = approval.payload.get("effective_date") or timezone.now().date()
    employee.save(update_fields=["employment_status", "end_date", "updated_at"])
    # De-provision the login, if any (roadmap: "de-provision login" on offboarding).
    linked_user = employee.user
    if linked_user is not None and linked_user.is_active:
        linked_user.is_active = False
        linked_user.save(update_fields=["is_active"])
    record_audit(
        action="TERMINATE",
        user=approval.decided_by,
        organization=employee.organization,
        entity_type="employee",
        entity_id=str(employee.pk),
        changes={"effective_date": str(employee.end_date)},
    )


# 8 hours in seconds — anything beyond this is overtime.
SHIFT_LENGTH_SECONDS = 8 * 60 * 60


@transaction.atomic
def clock_attendance(
    *,
    employee: Employee,
    direction: str,
    user: User | None = None,
) -> AttendanceLog:
    """Toggle today's attendance for ``employee``.

    ``direction`` is either ``"IN"`` or ``"OUT"``. The first call of the day
    creates the row; subsequent calls fill in the out-time and any overtime.
    A second IN is refused (one punch in per day); an OUT without an IN is
    also refused.
    """
    direction = direction.upper()
    if direction not in {"IN", "OUT"}:
        raise ValueError("direction must be 'IN' or 'OUT'.")

    today = timezone.now().date()
    now = timezone.now()
    log = AttendanceLog.objects.select_for_update().filter(employee=employee, date=today).first()

    if direction == "IN":
        if log is not None and log.clock_in is not None:
            raise ValueError(f"{employee.full_name} has already clocked in today.")
        if log is None:
            log = AttendanceLog(
                employee=employee,
                date=today,
                clock_in=now,
                status=AttendanceLog.Status.PRESENT,
            )
        else:
            log.clock_in = now
            log.status = AttendanceLog.Status.PRESENT
        log.save()
    else:  # OUT
        if log is None or log.clock_in is None:
            raise ValueError(
                f"{employee.full_name} has not clocked in today — clock in before clocking out."
            )
        if log.clock_out is not None:
            raise ValueError(f"{employee.full_name} has already clocked out today.")
        log.clock_out = now
        worked = (now - log.clock_in).total_seconds()
        if worked > SHIFT_LENGTH_SECONDS:
            overtime = Decimal(str(round((worked - SHIFT_LENGTH_SECONDS) / 3600.0, 2)))
            log.overtime_hours = overtime
        log.save()

    record_audit(
        action="CLOCK",
        user=user,
        organization=employee.organization,
        entity_type="attendance_log",
        entity_id=str(log.pk),
        changes={"direction": direction, "date": str(today)},
    )
    return log
