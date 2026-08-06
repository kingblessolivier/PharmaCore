"""Approval lifecycle: request → claim (lock) → decide (approve/reject).

No self-approval: the requester can never claim or decide their own request.
SLA timers: refresh_sla() releases a claim once its deadline has passed so the
item re-enters the queue unclaimed — nothing is ever silently stuck.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.approvals import registry
from apps.approvals.models import DEFAULT_SLA_HOURS, ApprovalRequest
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User


class ApprovalError(Exception):
    pass


def request_approval(
    *,
    resource_type: str,
    resource_id: str,
    organization: Organization,
    requested_by: User,
    payload: dict[str, Any] | None = None,
    reason: str = "",
    sla_hours: int = DEFAULT_SLA_HOURS,
) -> ApprovalRequest:
    return ApprovalRequest.objects.create(
        resource_type=resource_type,
        resource_id=str(resource_id),
        organization=organization,
        requested_by=requested_by,
        payload=payload or {},
        reason=reason,
        sla_hours=sla_hours,
    )


def refresh_sla(qs: QuerySet[ApprovalRequest]) -> None:
    """Release any claim whose SLA has lapsed so the request re-enters the queue."""
    now = timezone.now()
    for approval in qs.filter(status=ApprovalRequest.Status.PENDING, claimed_by__isnull=False):
        if now > approval.sla_deadline:
            approval.claimed_by = None
            approval.claimed_at = None
            approval.sla_breached = True
            approval.save(update_fields=["claimed_by", "claimed_at", "sla_breached"])


def claim(*, approval: ApprovalRequest, user: User) -> ApprovalRequest:
    if approval.status != ApprovalRequest.Status.PENDING:
        raise ApprovalError("Only pending requests can be claimed.")
    if approval.requested_by_id == user.pk:
        raise ApprovalError("You cannot claim your own request (no self-approval).")
    if approval.claimed_by_id and approval.claimed_by_id != user.pk:
        raise ApprovalError("Already claimed by another approver.")
    approval.claimed_by = user
    approval.claimed_at = timezone.now()
    approval.save(update_fields=["claimed_by", "claimed_at"])
    return approval


def reassign(*, approval: ApprovalRequest, to_user: User) -> ApprovalRequest:
    """Senior oversight: forward/reassign a claim to another approver."""
    if approval.status != ApprovalRequest.Status.PENDING:
        raise ApprovalError("Only pending requests can be reassigned.")
    if approval.requested_by_id == to_user.pk:
        raise ApprovalError("Cannot assign a request to its own requester.")
    approval.claimed_by = to_user
    approval.claimed_at = timezone.now()
    approval.sla_breached = False
    approval.save(update_fields=["claimed_by", "claimed_at", "sla_breached"])
    return approval


@transaction.atomic
def decide(
    *, approval: ApprovalRequest, user: User, approve: bool, note: str = ""
) -> ApprovalRequest:
    if approval.status != ApprovalRequest.Status.PENDING:
        raise ApprovalError("This request has already been decided.")
    if approval.requested_by_id == user.pk:
        raise ApprovalError("You cannot decide your own request (no self-approval).")
    if approval.claimed_by_id != user.pk:
        raise ApprovalError("Claim the request before deciding it.")

    approval.status = (
        ApprovalRequest.Status.APPROVED if approve else ApprovalRequest.Status.REJECTED
    )
    approval.decided_by = user
    approval.decided_at = timezone.now()
    approval.decision_note = note
    approval.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
    if approve:
        registry.apply(approval)
    record_audit(
        action="APPROVE" if approve else "REJECT",
        user=user,
        organization=approval.organization,
        entity_type="approval_request",
        entity_id=str(approval.pk),
        changes={"resource_type": approval.resource_type, "resource_id": approval.resource_id},
    )
    return approval
