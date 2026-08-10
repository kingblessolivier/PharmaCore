"""Claims: turning an insured sale into money the pharmacy is actually owed.

The lifecycle the industry converges on, and the reasons each step exists:

* **Build** from a completed sale, using the split already agreed at the counter.
  Re-deriving it here would let the claim disagree with what the patient was
  charged.
* **Submit** — after which the claim is a debt, and the clock on the scheme's
  claim window is running.
* **Adjudicate** — accepted, short-paid or rejected with a reason code. A
  rejection without a code cannot be worked, resubmitted or learned from.
* **Reverse** — the script was never collected. The medicine goes back on the
  shelf and the patient's liability is restored; the claim is *not* deleted,
  because a claim that vanishes leaves the insurer's records disagreeing with
  ours and nothing to reconcile against.

The receivable itself is raised at the till, not here. An insured sale is tendered
partly in cash and partly as INSURANCE, and that tender debits 1410 Accounts
Receivable — Insurers against revenue recognised at the same moment. Submitting
the claim therefore posts nothing; the two events that move money afterwards are
settlement (bank against the receivable) and rejection (write-off against it).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.iam.audit import record_audit
from apps.insurance.eligibility import Split, check_eligibility, split_basket
from apps.insurance.models import Claim, ClaimLine, InsuranceScheme, MemberPolicy

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.iam.models import User
    from apps.retail.models import Sale

ZERO = Decimal("0.00")


class ClaimError(ValueError):
    """A claim cannot be moved as asked."""


@dataclass
class ClaimOutcome:
    claim: Claim
    lines: int
    claimed: Decimal
    patient: Decimal


@transaction.atomic
def build_from_sale(
    *, sale: Sale, policy: MemberPolicy, user: User | None = None, split: Split | None = None
) -> ClaimOutcome:
    """Create a draft claim for an insured sale.

    Refuses a second claim on the same sale: duplicates are the most common
    rejection reason in the industry, and the cheapest place to prevent one is
    before it is ever sent.
    """
    if sale.status != sale.Status.COMPLETED:
        raise ClaimError("Only a completed sale can be claimed.")

    existing = Claim.objects.filter(sale=sale).exclude(status=Claim.Status.REVERSED).first()
    if existing is not None:
        raise ClaimError(
            f"Sale {sale.sale_number} is already on claim {existing.claim_number or existing.pk}."
        )

    service_date = (sale.completed_at or sale.created_at).date()
    verdict = check_eligibility(member_number=policy.member_number, on=service_date)
    if not verdict.is_eligible:
        raise ClaimError(f"Not claimable: {verdict.reason}")

    if split is None:
        split = split_basket(
            policy=policy,
            lines=[
                {
                    "product": item.product,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "sale_item": item,
                }
                for item in sale.items.select_related("product").all()
            ],
        )

    claim = Claim.objects.create(
        organization=sale.organization,
        scheme=policy.scheme,
        policy=policy,
        sale=sale,
        service_date=service_date,
        patient_paid=split.patient_total,
        claimed_amount=split.insurer_total,
        created_by=user,
    )
    claim.claim_number = f"CLM-{claim.pk:06d}"
    claim.save(update_fields=["claim_number"])

    for line in split.lines:
        # Nothing is claimed for a line the insurer does not cover; recording it
        # anyway keeps the claim a faithful picture of the basket.
        ClaimLine.objects.create(
            claim=claim,
            product=line.product,
            sale_item=line.sale_item,
            quantity=line.quantity,
            unit_price=line.unit_price,
            gross_amount=line.gross,
            patient_amount=line.patient,
            insurer_amount=line.insurer,
            copay_pct_applied=line.copay_pct,
            note=line.note,
        )

    record_audit(
        action="CLAIM_BUILT",
        user=user,
        organization=sale.organization,
        entity_type="insurance_claim",
        entity_id=str(claim.pk),
        changes={
            "sale": sale.sale_number,
            "scheme": policy.scheme.code,
            "member": policy.member_number,
            "claimed": str(split.insurer_total),
            "patient": str(split.patient_total),
        },
    )
    return ClaimOutcome(
        claim=claim,
        lines=len(split.lines),
        claimed=split.insurer_total,
        patient=split.patient_total,
    )


@transaction.atomic
def submit(*, claim: Claim, user: User | None = None) -> Claim:
    """Send the claim, starting the clock on the scheme's window."""
    if claim.status != Claim.Status.DRAFT:
        raise ClaimError(
            f"Claim {claim.claim_number} is {claim.get_status_display().lower()} — only a draft "
            "can be submitted."
        )
    if claim.claimed_amount <= ZERO:
        raise ClaimError(
            "Nothing on this claim is covered by the scheme, so there is nothing to claim. "
            "The patient has already paid in full."
        )

    deadline = claim.service_date + timedelta(days=claim.scheme.claim_window_days)
    if timezone.localdate() > deadline:
        raise ClaimError(
            f"The claim window for {claim.scheme.name} closed on {deadline} "
            f"({claim.scheme.claim_window_days} days after service). Submitting now would be "
            "rejected as a late submission."
        )

    claim.status = Claim.Status.SUBMITTED
    claim.submitted_at = timezone.now()
    claim.save(update_fields=["status", "submitted_at", "updated_at"])

    # Nothing posts here. The receivable already exists: the sale debited 1410
    # Accounts Receivable — Insurers for the scheme's share at the till, against
    # revenue recognised then. Posting again on submission would recognise the
    # same revenue twice and inflate both income and assets.
    record_audit(
        action="CLAIM_SUBMITTED",
        user=user,
        organization=claim.organization,
        entity_type="insurance_claim",
        entity_id=str(claim.pk),
        changes={"claim": claim.claim_number, "amount": str(claim.claimed_amount)},
    )
    return claim


@transaction.atomic
def adjudicate(
    *,
    claim: Claim,
    accepted: bool,
    paid_amount: Decimal | None = None,
    reason: str = "",
    notes: str = "",
    user: User | None = None,
) -> Claim:
    """Record the insurer's decision.

    A rejection must carry a reason code. Working a rejected claim — fixing it,
    resubmitting it, or learning that a scheme keeps refusing a product — is
    impossible from "rejected" alone.
    """
    if claim.status not in (Claim.Status.SUBMITTED, Claim.Status.ACCEPTED, Claim.Status.PART_PAID):
        raise ClaimError(
            f"Claim {claim.claim_number} is {claim.get_status_display().lower()} and cannot be "
            "adjudicated."
        )

    if not accepted:
        if not reason:
            raise ClaimError(
                "A rejection needs a reason code — without one the claim cannot be worked or "
                "resubmitted."
            )
        claim.status = Claim.Status.REJECTED
        claim.rejection_reason = reason
        claim.notes = f"{claim.notes}\n{notes}".strip()
        claim.adjudicated_at = timezone.now()
        claim.save(
            update_fields=["status", "rejection_reason", "notes", "adjudicated_at", "updated_at"]
        )
        _post_write_off(claim=claim, user=user)
        record_audit(
            action="CLAIM_REJECTED",
            user=user,
            organization=claim.organization,
            entity_type="insurance_claim",
            entity_id=str(claim.pk),
            changes={"claim": claim.claim_number, "reason": reason},
        )
        return claim

    settled = Decimal(str(paid_amount)) if paid_amount is not None else claim.claimed_amount
    if settled < ZERO:
        raise ClaimError("A settled amount cannot be negative.")
    if settled > claim.claimed_amount:
        raise ClaimError(
            f"The insurer cannot settle {settled} against a claim for {claim.claimed_amount}. "
            "An overpayment needs a credit note, not a larger claim."
        )

    claim.paid_amount = settled
    claim.status = Claim.Status.PAID if settled == claim.claimed_amount else Claim.Status.PART_PAID
    claim.notes = f"{claim.notes}\n{notes}".strip()
    claim.adjudicated_at = timezone.now()
    claim.save(update_fields=["paid_amount", "status", "notes", "adjudicated_at", "updated_at"])

    _post_settlement(claim=claim, amount=settled, user=user)
    record_audit(
        action="CLAIM_ADJUDICATED",
        user=user,
        organization=claim.organization,
        entity_type="insurance_claim",
        entity_id=str(claim.pk),
        changes={
            "claim": claim.claim_number,
            "claimed": str(claim.claimed_amount),
            "paid": str(settled),
            "shortfall": str(claim.claimed_amount - settled),
        },
    )
    return claim


@transaction.atomic
def reverse(*, claim: Claim, reason: str, user: User | None = None) -> Claim:
    """Withdraw a claim for a script that was never collected.

    The record is kept, not deleted. A claim that disappears leaves the insurer's
    file and ours disagreeing, with nothing left to reconcile the difference
    against.
    """
    if claim.status == Claim.Status.REVERSED:
        raise ClaimError("This claim has already been reversed.")
    if claim.status == Claim.Status.PAID:
        raise ClaimError(
            "A settled claim cannot be reversed — recover it through a credit note to the insurer."
        )
    if not reason.strip():
        raise ClaimError("A reversal must say why.")

    claim.status = Claim.Status.REVERSED
    claim.reversed_at = timezone.now()
    claim.notes = f"{claim.notes}\nReversed: {reason}".strip()
    claim.save(update_fields=["status", "reversed_at", "notes", "updated_at"])

    record_audit(
        action="CLAIM_REVERSED",
        user=user,
        organization=claim.organization,
        entity_type="insurance_claim",
        entity_id=str(claim.pk),
        changes={"claim": claim.claim_number, "reason": reason},
    )
    return claim


def _post_settlement(*, claim: Claim, amount: Decimal, user: User | None) -> None:
    """Money arrived: clear the insurer receivable raised at the till.

    Dr 1200 Bank
    Cr 1410 Accounts Receivable — Insurers
    """
    if amount <= ZERO:
        return
    from apps.finance.models import JournalEntry, JournalLine
    from apps.finance.services import ensure_default_accounts, post_journal

    accounts = ensure_default_accounts(claim.organization)
    post_journal(
        organization=claim.organization,
        description=f"Insurance settlement {claim.claim_number} · {claim.scheme.name}",
        lines=[
            {
                "account": accounts["1200"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": f"Received from {claim.scheme.name}",
            },
            {
                "account": accounts["1410"],
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": f"Clears claim {claim.claim_number}",
            },
        ],
        reference_type="insurance_settlement",
        source_module=JournalEntry.Source.TREASURY,
        reference_id=str(claim.pk),
        user=user,
    )


def _post_write_off(*, claim: Claim, user: User | None) -> None:
    """A rejected claim is money that is not coming.

        Dr 6160 Bad debt / claim write-off
        Cr 1410 Accounts Receivable — Insurers

    Left on the balance sheet it would overstate assets indefinitely, which is
    exactly how a rejected-claims pile becomes invisible.
    """
    owed = claim.claimed_amount - claim.paid_amount
    if owed <= ZERO:
        return
    from apps.finance.models import JournalEntry, JournalLine
    from apps.finance.services import ensure_default_accounts, post_journal

    accounts = ensure_default_accounts(claim.organization)
    expense = accounts.get("6160") or accounts.get("6100")
    if expense is None:
        return
    post_journal(
        organization=claim.organization,
        description=f"Claim {claim.claim_number} rejected · {claim.scheme.name}",
        lines=[
            {
                "account": expense,
                "side": JournalLine.Side.DEBIT,
                "amount": owed,
                "memo": f"Rejected: {claim.get_rejection_reason_display()}",
            },
            {
                "account": accounts["1410"],
                "side": JournalLine.Side.CREDIT,
                "amount": owed,
                "memo": f"Writes off claim {claim.claim_number}",
            },
        ],
        reference_type="insurance_write_off",
        source_module=JournalEntry.Source.SALES,
        reference_id=str(claim.pk),
        user=user,
    )


# ---------------------------------------------------------------------------
# Queues and exposure
# ---------------------------------------------------------------------------


def work_queue(*, organization: Any) -> list[dict[str, Any]]:
    """Claims needing action, most urgent first.

    Ranked by how close each is to its scheme's claim window closing, because a
    claim that misses the window is not late — it is unrecoverable.
    """
    org_id = getattr(organization, "pk", organization)
    today = timezone.localdate()
    rows: list[dict[str, Any]] = []
    claims = (
        Claim.objects.filter(organization_id=org_id)
        .exclude(status__in=[Claim.Status.PAID, Claim.Status.REVERSED])
        .select_related("scheme", "policy", "sale")
    )
    for claim in claims:
        deadline = claim.service_date + timedelta(days=claim.scheme.claim_window_days)
        rows.append(
            {
                "claim": claim.pk,
                "claim_number": claim.claim_number,
                "status": claim.status,
                "scheme": claim.scheme_id,
                "scheme_name": claim.scheme.name,
                "member_name": claim.policy.full_name,
                "sale_number": claim.sale.sale_number,
                "service_date": claim.service_date,
                "claimed": str(claim.claimed_amount),
                "paid": str(claim.paid_amount),
                "outstanding": str(claim.outstanding),
                "deadline": deadline,
                "days_left": (deadline - today).days,
                "rejection_reason": claim.rejection_reason,
            }
        )
    rows.sort(key=lambda r: r["days_left"])
    return rows


def insurer_exposure(*, organization: Any) -> list[dict[str, Any]]:
    """What each payer owes, aged. Insurer debt behaves like any other AR."""
    org_id = getattr(organization, "pk", organization)
    today = timezone.localdate()
    out: list[dict[str, Any]] = []

    for scheme in InsuranceScheme.objects.filter(organization_id=org_id, is_active=True):
        buckets = {"current": ZERO, "d30": ZERO, "d60": ZERO, "d90": ZERO, "over90": ZERO}
        total = ZERO
        claims = Claim.objects.filter(scheme=scheme).exclude(
            status__in=[Claim.Status.DRAFT, Claim.Status.REVERSED, Claim.Status.REJECTED]
        )
        for claim in claims:
            owed = claim.outstanding
            if owed <= ZERO:
                continue
            age = (today - claim.service_date).days
            key = (
                "current"
                if age <= 30
                else (
                    "d30"
                    if age <= 60
                    else "d60" if age <= 90 else "d90" if age <= 120 else "over90"
                )
            )
            buckets[key] += owed
            total += owed
        if total > ZERO or claims.exists():
            out.append(
                {
                    "scheme": scheme.pk,
                    "scheme_name": scheme.name,
                    "settlement": scheme.settlement,
                    "outstanding": str(total),
                    **{k: str(v) for k, v in buckets.items()},
                }
            )
    out.sort(key=lambda r: Decimal(r["outstanding"]), reverse=True)
    return out


def summary(*, organization: Any) -> dict[str, Any]:
    """Headline insurance figures for the module overview."""
    org_id = getattr(organization, "pk", organization)
    today = timezone.localdate()
    claims = Claim.objects.filter(organization_id=org_id)

    agg = claims.aggregate(
        drafts=Count("id", filter=Q(status=Claim.Status.DRAFT)),
        submitted=Count("id", filter=Q(status=Claim.Status.SUBMITTED)),
        rejected=Count("id", filter=Q(status=Claim.Status.REJECTED)),
        claimed=Sum("claimed_amount"),
        paid=Sum("paid_amount"),
    )

    queue = work_queue(organization=org_id)
    expiring = [r for r in queue if 0 <= r["days_left"] <= 7]
    missed = [r for r in queue if r["days_left"] < 0]
    outstanding = sum(
        (Decimal(r["outstanding"]) for r in queue if r["status"] != Claim.Status.DRAFT), ZERO
    )

    return {
        "drafts": agg["drafts"] or 0,
        "submitted": agg["submitted"] or 0,
        "rejected": agg["rejected"] or 0,
        "outstanding": str(outstanding),
        "claimed_total": str(agg["claimed"] or ZERO),
        "paid_total": str(agg["paid"] or ZERO),
        # The two numbers that cost money if ignored.
        "closing_within_7_days": len(expiring),
        "window_missed": len(missed),
        "as_at": today,
    }
