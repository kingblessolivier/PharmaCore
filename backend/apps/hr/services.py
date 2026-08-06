"""HR services: employee-number allocation and the approval-gated termination flow.

Offboarding (termination) is never self-approved and never immediate — it always
routes through the approvals engine (see docs/12 §4, ROADMAP "13. Approve & authorise").
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.approvals import registry
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import request_approval
from apps.hr.models import Employee
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
