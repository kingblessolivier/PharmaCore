"""What is waiting for *you*, and what is waiting for your team.

A nav entry is a filing cabinet. A work queue is a colleague telling you what
needs doing. The audit measured one ordinary job — buy a drug from your own depot —
crossing seven screens in five nav groups, with no link from any step to the next.
Once the system knows who reports to whom and who may act (``apps.iam.authority``),
it can answer a better question than "which table would you like to open".

Three lists, and the distinction between the first two matters:

``waiting_on_me``   approvals I am competent and authorised to decide **now**.
``needs_escalation`` approvals I can see and *cannot* decide — with who can. These
                    are the ones that quietly rot in a shared queue, because
                    everyone assumes someone else is dealing with them.
``my_team``         for anyone with reports: what their people have raised, and
                    what has breached its SLA. This is the reporting line made
                    visible rather than merely recorded.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.iam import authority


def _describe(approval: Any) -> dict[str, Any]:
    rule = authority.rule_for(approval.resource_type)
    amount = authority.amount_from_payload(approval.resource_type, approval.payload)
    requester = approval.requested_by
    return {
        "id": approval.pk,
        "resource_type": approval.resource_type,
        "label": rule.label if rule else approval.resource_type,
        "resource_id": approval.resource_id,
        "organization": approval.organization_id,
        "organization_name": approval.organization.name,
        "requested_by": requester.get_full_name() or requester.username,
        "requested_at": approval.created_at,
        "reason": approval.reason,
        "amount": float(amount) if amount is not None else None,
        "sla_breached": approval.sla_breached,
        "claimed_by": (
            (approval.claimed_by.get_full_name() or approval.claimed_by.username)
            if approval.claimed_by
            else None
        ),
    }


def for_user(user: Any) -> dict[str, Any]:
    """Everything this person could act on, sorted into what they can and cannot do."""
    from apps.approvals.models import ApprovalRequest
    from apps.approvals.services import authority_for
    from apps.iam.scoping import organizations_visible_to

    pending = (
        ApprovalRequest.objects.filter(
            status=ApprovalRequest.Status.PENDING,
            organization__in=organizations_visible_to(user),
        )
        .select_related("organization", "requested_by", "claimed_by")
        .order_by("created_at")
    )

    waiting: list[dict[str, Any]] = []
    escalate: list[dict[str, Any]] = []
    mine: list[dict[str, Any]] = []

    for approval in pending:
        row = _describe(approval)
        if approval.requested_by_id == user.pk:
            # Your own request: you are waiting on somebody else, by design.
            check = authority_for(approval=approval, user=user)
            row["with"] = [
                person.get_full_name() or person.username for person in check.escalate_to[:2]
            ]
            mine.append(row)
            continue
        check = authority_for(approval=approval, user=user)
        if check.allowed:
            waiting.append(row)
        else:
            row["why"] = check.reason
            row["escalate_to"] = [
                person.get_full_name() or person.username for person in check.escalate_to[:2]
            ]
            escalate.append(row)

    team = authority.reports_of(user, recursive=True)
    team_ids = {person.pk for person in team}
    team_rows = [
        _describe(approval) for approval in pending if approval.requested_by_id in team_ids
    ]

    return {
        "waiting_on_me": waiting,
        "needs_escalation": escalate,
        "raised_by_me": mine,
        "my_team": {
            "size": len(team),
            "members": [
                {
                    "id": person.pk,
                    "name": person.get_full_name() or person.username,
                    "roles": list(person.roles.values_list("code", flat=True)),
                }
                for person in team
            ],
            "open_requests": team_rows,
            "breaching": [row for row in team_rows if row["sla_breached"]],
        },
        "as_of": timezone.now(),
    }


def next_steps(user: Any) -> list[dict[str, Any]]:
    """Work that is not an approval but is plainly the next thing to do.

    Deliberately small and honest: each entry is a real count with a real link.
    A dashboard that invents "suggestions" nobody asked for teaches people to
    ignore it.
    """
    from apps.distribution.models import StockOrder
    from apps.iam.scoping import organizations_visible_to
    from apps.inventory.models import InventoryBatch

    org_ids = list(organizations_visible_to(user).values_list("id", flat=True))
    today = timezone.localdate()
    steps: list[dict[str, Any]] = []

    if user.has_permission("order.receive"):
        count = StockOrder.objects.filter(
            retail_id__in=org_ids, status=StockOrder.Status.IN_TRANSIT
        ).count()
        if count:
            steps.append(
                {
                    "label": f"{count} delivery{'ies' if count > 1 else ''} to receive",
                    "to": "/distribution/in-transit",
                    "count": count,
                    "tone": "info",
                }
            )

    if user.has_permission("inventory.view"):
        expired = InventoryBatch.objects.filter(
            organization_id__in=org_ids, expiry_date__lt=today, quantity_available__gt=0
        ).count()
        if expired:
            plural = "es" if expired > 1 else ""
            steps.append(
                {
                    "label": f"{expired} expired batch{plural} still on the shelf",
                    "to": "/catalog/expiry",
                    "count": expired,
                    "tone": "danger",
                }
            )

    return steps
