"""Reconciling what insurers say they paid against what was claimed.

Two documents disagree by default: the pharmacy's claims and the insurer's
remittance advice. The difference is where the money goes missing — a short-pay
nobody chased, a claim the insurer never received, or a payment that arrived
against nothing anyone can identify.

The advice is kept as its own record rather than folded straight into the claims,
because once a claim's ``paid_amount`` has been overwritten there is nothing left
to answer *did they pay what they agreed to* with.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils import timezone

from apps.iam.audit import record_audit
from apps.insurance.models import Claim, RemittanceAdvice, RemittanceLine

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.iam.models import User

ZERO = Decimal("0.00")


class ReconciliationError(ValueError):
    """A remittance cannot be posted as presented."""


@dataclass
class PostingOutcome:
    advice: RemittanceAdvice
    claims_settled: int
    total_posted: Decimal
    short_paid: Decimal
    unmatched: Decimal


@transaction.atomic
def add_line(
    *, advice: RemittanceAdvice, claim: Claim, amount_paid: Decimal, denial_reason: str = ""
) -> RemittanceLine:
    """Match one claim on the advice to what the insurer says it paid for it."""
    if advice.status == RemittanceAdvice.Status.POSTED:
        raise ReconciliationError("This advice has already been posted.")
    if claim.scheme_id != advice.scheme_id:
        raise ReconciliationError(
            f"Claim {claim.claim_number} is against {claim.scheme.name}, not {advice.scheme.name}."
        )
    if claim.status in (Claim.Status.DRAFT, Claim.Status.REVERSED):
        raise ReconciliationError(
            f"Claim {claim.claim_number} is {claim.get_status_display().lower()} — it was never "
            "submitted, so nothing can be settled against it."
        )
    amount = Decimal(str(amount_paid))
    if amount < ZERO:
        raise ReconciliationError("A settlement cannot be negative.")

    line, created = RemittanceLine.objects.get_or_create(
        remittance=advice,
        claim=claim,
        defaults={"amount_paid": amount, "denial_reason": denial_reason[:255]},
    )
    if not created:
        line.amount_paid = amount
        line.denial_reason = denial_reason[:255]
        line.save(update_fields=["amount_paid", "denial_reason"])
    return line


@transaction.atomic
def post(*, advice: RemittanceAdvice, user: User | None = None) -> PostingOutcome:
    """Apply the advice: settle each matched claim and bank the money.

    Refuses while the advice does not foot. If the insurer says it paid a total
    that its own lines do not add up to, posting it anyway buries the discrepancy
    in the ledger where nobody will find it.
    """
    from apps.insurance.claims import adjudicate

    if advice.status == RemittanceAdvice.Status.POSTED:
        raise ReconciliationError("This advice has already been posted.")

    lines = list(advice.lines.select_related("claim", "claim__scheme"))
    if not lines:
        raise ReconciliationError("Match at least one claim before posting this advice.")

    matched = sum((ln.amount_paid for ln in lines), ZERO)
    if matched != advice.total_advised:
        raise ReconciliationError(
            f"The advice says {advice.total_advised} but its lines total {matched}. "
            f"The difference of {advice.total_advised - matched} has to be explained before "
            "this can be posted."
        )

    settled = 0
    short = ZERO
    for line in lines:
        claim = line.claim
        if line.amount_paid < claim.claimed_amount:
            short += claim.claimed_amount - line.amount_paid
        adjudicate(
            claim=claim,
            accepted=True,
            paid_amount=line.amount_paid,
            notes=(
                f"Settled on advice {advice.reference}"
                + (f" — {line.denial_reason}" if line.denial_reason else "")
            ),
            user=user,
        )
        settled += 1

    advice.status = RemittanceAdvice.Status.POSTED
    advice.posted_at = timezone.now()
    advice.posted_by = user
    advice.save(update_fields=["status", "posted_at", "posted_by"])

    record_audit(
        action="REMITTANCE_POSTED",
        user=user,
        organization=advice.organization,
        entity_type="remittance_advice",
        entity_id=str(advice.pk),
        changes={
            "reference": advice.reference,
            "scheme": advice.scheme.code,
            "claims": settled,
            "total": str(matched),
            "short_paid": str(short),
        },
    )
    return PostingOutcome(
        advice=advice,
        claims_settled=settled,
        total_posted=matched,
        short_paid=short,
        unmatched=ZERO,
    )


def suggest_matches(*, advice: RemittanceAdvice) -> list[dict[str, Any]]:
    """Claims this advice plausibly settles: same scheme, submitted, still owed.

    Deliberately a suggestion rather than an auto-match. Guessing which claim a
    payment belongs to is how a short-pay gets silently attached to the wrong one
    and both records stop being true.
    """
    candidates = (
        Claim.objects.filter(scheme=advice.scheme, organization=advice.organization)
        .filter(status__in=[Claim.Status.SUBMITTED, Claim.Status.PART_PAID])
        .exclude(pk__in=advice.lines.values_list("claim_id", flat=True))
        .select_related("policy")
        .order_by("service_date")
    )
    return [
        {
            "claim": c.pk,
            "claim_number": c.claim_number,
            "member_name": c.policy.full_name,
            "service_date": c.service_date,
            "claimed": str(c.claimed_amount),
            "already_paid": str(c.paid_amount),
            "outstanding": str(c.outstanding),
        }
        for c in candidates
    ]


def summary(*, organization: Any) -> dict[str, Any]:
    """Reconciliation health for the insurance overview."""
    org_id = getattr(organization, "pk", organization)
    drafts = RemittanceAdvice.objects.filter(
        organization_id=org_id, status=RemittanceAdvice.Status.DRAFT
    )
    posted = RemittanceAdvice.objects.filter(
        organization_id=org_id, status=RemittanceAdvice.Status.POSTED
    )
    short = sum(
        (
            c.claimed_amount - c.paid_amount
            for c in Claim.objects.filter(organization_id=org_id, status=Claim.Status.PART_PAID)
        ),
        ZERO,
    )
    return {
        "advices_awaiting": drafts.count(),
        "advices_posted": posted.count(),
        # Accepted but under-paid. A short-pay nobody chases is a write-off that
        # never got a decision.
        "short_paid_total": str(short),
        "short_paid_claims": Claim.objects.filter(
            organization_id=org_id, status=Claim.Status.PART_PAID
        ).count(),
    }
