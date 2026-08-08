"""Approval lifecycle: request → claim (lock) → decide (approve/reject).

No self-approval: the requester can never claim or decide their own request.
SLA timers: refresh_sla() releases a claim once its deadline has passed so the
item re-enters the queue unclaimed — nothing is ever silently stuck.

**Authority** (``apps.iam.authority``): claiming and deciding also require the
competence the resource demands and an approval limit that covers the amount at
risk. Until F2 this engine checked only that a request was pending, was not your
own, and was not already claimed — which meant a driver could approve a payroll
run of forty-eight million francs. Being free is not the same as being allowed.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.approvals import registry
from apps.approvals.models import DEFAULT_SLA_HOURS, ApprovalRequest
from apps.iam import authority
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
    approval = ApprovalRequest.objects.create(
        resource_type=resource_type,
        resource_id=str(resource_id),
        organization=organization,
        requested_by=requested_by,
        payload=payload or {},
        reason=reason,
        sla_hours=sla_hours,
    )

    # F1.3 — emit ApprovalRequested on the bus (ADR-010). Reporting / Insights
    # / the per-user bell counter all subscribe here without coupling to the
    # approvals engine internals.
    from apps.events.publishers import publish_approval_requested

    publish_approval_requested(
        approval_id=approval.pk,
        organization=organization,
        requested_by=requested_by,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return approval


def refresh_sla(qs: QuerySet[ApprovalRequest]) -> None:
    """Release any claim whose SLA has lapsed so the request re-enters the queue."""
    now = timezone.now()
    for approval in qs.filter(status=ApprovalRequest.Status.PENDING, claimed_by__isnull=False):
        if now > approval.sla_deadline:
            approval.claimed_by = None
            approval.claimed_at = None
            approval.sla_breached = True
            approval.save(update_fields=["claimed_by", "claimed_at", "sla_breached"])


def authority_for(*, approval: ApprovalRequest, user: User) -> authority.AuthorityCheck:
    """May ``user`` decide this request, and if not, who can?

    Exposed so screens can explain themselves. A queue that shows an item and
    then refuses it wastes the approver's time; one that says "above your limit —
    this goes to Grace" tells them what happens next.
    """
    return authority.can_decide(
        user=user,
        resource_type=approval.resource_type,
        amount=authority.amount_from_payload(approval.resource_type, approval.payload),
    )


def _require_authority(*, approval: ApprovalRequest, user: User, verb: str) -> None:
    check = authority_for(approval=approval, user=user)
    if check.allowed:
        return
    message = check.reason
    if check.escalate_to:
        names = ", ".join(u.get_full_name() or u.username for u in check.escalate_to[:2])
        message = f"{message} This should go to {names}."
    raise ApprovalError(f"You cannot {verb} this request. {message}")


def claim(*, approval: ApprovalRequest, user: User) -> ApprovalRequest:
    if approval.status != ApprovalRequest.Status.PENDING:
        raise ApprovalError("Only pending requests can be claimed.")
    if approval.requested_by_id == user.pk:
        raise ApprovalError("You cannot claim your own request (no self-approval).")
    if approval.claimed_by_id and approval.claimed_by_id != user.pk:
        raise ApprovalError("Already claimed by another approver.")
    _require_authority(approval=approval, user=user, verb="claim")
    approval.claimed_by = user
    approval.claimed_at = timezone.now()
    approval.save(update_fields=["claimed_by", "claimed_at"])
    return approval


def reassign(
    *, approval: ApprovalRequest, to_user: User, by: User | None = None
) -> ApprovalRequest:
    """Senior oversight: forward/reassign a claim to another approver.

    Handing a request on does not launder it. The recipient must be able to
    decide it in their own right (R1/R2), and whoever forwards it cannot pass on
    authority they do not hold themselves (R4) — otherwise reassignment becomes
    the way round every other rule.
    """
    if approval.status != ApprovalRequest.Status.PENDING:
        raise ApprovalError("Only pending requests can be reassigned.")
    if approval.requested_by_id == to_user.pk:
        raise ApprovalError("Cannot assign a request to its own requester.")

    if by is not None:
        required = authority.required_permission_for(approval.resource_type)
        delegable = authority.can_delegate(granter=by, permission_codes={required})
        if not delegable.allowed:
            raise ApprovalError(f"You cannot reassign this request. {delegable.reason}")

    _require_authority(approval=approval, user=to_user, verb="be assigned")
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
    # Re-checked at the point of decision, not only at claim: a role or limit can
    # change while an item sits in someone's queue, and the decision is the moment
    # that matters.
    _require_authority(approval=approval, user=user, verb="decide")

    approval.status = (
        ApprovalRequest.Status.APPROVED if approve else ApprovalRequest.Status.REJECTED
    )
    approval.decided_by = user
    approval.decided_at = timezone.now()
    approval.decision_note = note
    approval.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
    if approve:
        registry.apply(approval)

    # F1.3 — emit ApprovalGranted/ApprovalRejected on the bus (ADR-010). The
    # downstream resource handler (registry.apply) is in-process; the event
    # is what Reporting/Insights listen to for their dashboards.
    from apps.events.publishers import publish_approval_decided

    publish_approval_decided(
        approval_id=approval.pk,
        organization=approval.organization,
        user=user,
        approve=approve,
    )

    record_audit(
        action="APPROVE" if approve else "REJECT",
        user=user,
        organization=approval.organization,
        entity_type="approval_request",
        entity_id=str(approval.pk),
        changes={"resource_type": approval.resource_type, "resource_id": approval.resource_id},
    )
    return approval
