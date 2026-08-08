"""Eligibility and the co-payment split — decided before dispensing, not after.

An expired card discovered at claim time is not an administrative problem; the
medicine has already gone and the money is already lost. So the counter asks two
questions in this order: *is this card good today*, and *what does this basket
split into*.

The split has one arithmetic invariant, and everything here exists to keep it:

    patient share + insurer share == what the basket costs

Rounding is the usual way that breaks. Percentages applied line by line and
rounded independently drift from the total, so the patient portion absorbs the
remainder exactly once, at the end. A pharmacy that collects one franc less than
it should has an unexplainable till; the patient never sees a gap.

Co-payment resolves member-first, then formulary, then scheme. That order is not
arbitrary — under CBHI the rate belongs to the member (Ubudehe category 1 is
fully subsidised), and a scheme-level rate alone would overcharge the poorest
patients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.utils import timezone

from apps.insurance.models import InsuranceScheme, MemberPolicy, SchemeFormulary

ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class EligibilityError(ValueError):
    """The card cannot be used for this dispense."""


@dataclass
class Eligibility:
    """Whether this card may be used today, and why not if it may not."""

    policy: MemberPolicy | None
    is_eligible: bool
    reason: str = ""
    copay_pct: Decimal = ZERO
    consultation_fee: Decimal = ZERO

    @property
    def scheme(self) -> InsuranceScheme | None:
        return self.policy.scheme if self.policy else None


def check_eligibility(
    *, member_number: str, scheme: InsuranceScheme | int | None = None, on: date | None = None
) -> Eligibility:
    """Look up a card and decide whether it is good on ``on`` (default today).

    Returns a verdict rather than raising, because "not eligible" is a normal
    answer at a counter — the sale proceeds as a cash sale.
    """
    on = on or timezone.localdate()
    qs = MemberPolicy.objects.select_related("scheme").filter(member_number=member_number)
    if scheme is not None:
        qs = qs.filter(scheme_id=getattr(scheme, "pk", scheme))
    policy = qs.order_by("priority").first()

    if policy is None:
        return Eligibility(
            policy=None, is_eligible=False, reason="No policy found for that number."
        )
    if not policy.scheme.is_active:
        return Eligibility(
            policy=policy, is_eligible=False, reason=f"{policy.scheme.name} is not active."
        )
    if policy.status != MemberPolicy.Status.ACTIVE:
        return Eligibility(
            policy=policy,
            is_eligible=False,
            reason=f"Membership is {policy.get_status_display().lower()}.",
        )
    if on < policy.valid_from:
        return Eligibility(
            policy=policy, is_eligible=False, reason=f"Cover starts on {policy.valid_from}."
        )
    if on > policy.valid_to:
        return Eligibility(
            policy=policy, is_eligible=False, reason=f"Cover expired on {policy.valid_to}."
        )

    return Eligibility(
        policy=policy,
        is_eligible=True,
        copay_pct=resolve_copay_pct(policy=policy),
        consultation_fee=policy.scheme.consultation_fee,
    )


def resolve_copay_pct(*, policy: MemberPolicy, formulary: SchemeFormulary | None = None) -> Decimal:
    """The share this patient pays: member override, then formulary, then scheme.

    Member first because Rwanda's co-payment is a property of the person — an
    Ubudehe category 1 member on CBHI pays nothing while a category 3 member on
    the same scheme pays 10%.
    """
    if policy.copay_pct_override is not None:
        return Decimal(policy.copay_pct_override)
    if formulary is not None and formulary.copay_pct_override is not None:
        return Decimal(formulary.copay_pct_override)
    return Decimal(policy.scheme.default_copay_pct)


@dataclass
class LineSplit:
    """How one basket line divides between patient and insurer."""

    product: Any
    quantity: int
    unit_price: Decimal
    gross: Decimal
    patient: Decimal
    insurer: Decimal
    copay_pct: Decimal
    covered: bool
    requires_prior_auth: bool = False
    note: str = ""
    sale_item: Any | None = None


@dataclass
class Split:
    """The whole basket, divided."""

    policy: MemberPolicy
    lines: list[LineSplit] = field(default_factory=list)
    consultation_fee: Decimal = ZERO

    @property
    def gross(self) -> Decimal:
        return _money(sum((ln.gross for ln in self.lines), ZERO))

    @property
    def patient_total(self) -> Decimal:
        """Includes the flat facility fee, which the insurer never covers."""
        return _money(sum((ln.patient for ln in self.lines), ZERO) + self.consultation_fee)

    @property
    def insurer_total(self) -> Decimal:
        return _money(sum((ln.insurer for ln in self.lines), ZERO))

    @property
    def uncovered_lines(self) -> list[LineSplit]:
        return [ln for ln in self.lines if not ln.covered]

    @property
    def needs_prior_auth(self) -> list[LineSplit]:
        return [ln for ln in self.lines if ln.requires_prior_auth]

    def reconciles(self) -> bool:
        """The split must account for every franc of the basket, plus the fee."""
        return self.patient_total + self.insurer_total == _money(self.gross + self.consultation_fee)


def split_basket(
    *,
    policy: MemberPolicy,
    lines: list[dict[str, Any]],
    include_consultation_fee: bool = True,
) -> Split:
    """Divide a basket between the patient and their insurer.

    ``lines`` are dicts of ``product``, ``quantity``, ``unit_price`` and optionally
    ``sale_item``. Each line is resolved against the scheme's formulary; anything
    absent from it is the patient's in full, because a scheme that never listed a
    product has not agreed to pay for it.
    """
    scheme = policy.scheme
    formulary = {
        row.product_id: row
        for row in SchemeFormulary.objects.filter(
            scheme=scheme,
            product_id__in=[getattr(ln["product"], "pk", ln["product"]) for ln in lines],
        )
    }

    split = Split(
        policy=policy,
        consultation_fee=scheme.consultation_fee if include_consultation_fee else ZERO,
    )

    for raw in lines:
        product = raw["product"]
        product_id = getattr(product, "pk", product)
        quantity = int(raw["quantity"])
        unit_price = Decimal(str(raw["unit_price"]))
        gross = _money(unit_price * quantity)
        cover = formulary.get(product_id)

        if cover is None or not cover.is_covered:
            split.lines.append(
                LineSplit(
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    gross=gross,
                    patient=gross,
                    insurer=ZERO,
                    copay_pct=HUNDRED,
                    covered=False,
                    note=(
                        "Not on this scheme's formulary — payable in full"
                        if cover is None
                        else "Excluded by the scheme"
                    ),
                    sale_item=raw.get("sale_item"),
                )
            )
            continue

        note = ""
        claimable_unit = unit_price
        # A ceiling caps what the insurer will consider; the excess is the
        # patient's, on top of their co-payment on the covered part.
        if cover.max_price_per_unit is not None and unit_price > cover.max_price_per_unit:
            claimable_unit = Decimal(cover.max_price_per_unit)
            note = f"Scheme pays up to {claimable_unit} per unit; the excess is the patient's."

        claimable_qty = quantity
        if cover.max_quantity_per_claim is not None and quantity > cover.max_quantity_per_claim:
            claimable_qty = cover.max_quantity_per_claim
            extra = f"Scheme covers {claimable_qty} unit(s) per claim."
            note = f"{note} {extra}".strip()

        claimable_gross = _money(claimable_unit * claimable_qty)
        excess = _money(gross - claimable_gross)

        pct = resolve_copay_pct(policy=policy, formulary=cover)
        patient_share = _money(claimable_gross * pct / HUNDRED)
        insurer_share = _money(claimable_gross - patient_share)

        split.lines.append(
            LineSplit(
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                gross=gross,
                patient=_money(patient_share + excess),
                insurer=insurer_share,
                copay_pct=pct,
                covered=True,
                requires_prior_auth=cover.requires_prior_auth,
                note=note,
                sale_item=raw.get("sale_item"),
            )
        )

    _absorb_rounding(split)
    return split


def _absorb_rounding(split: Split) -> None:
    """Push any rounding drift onto the patient's portion, once.

    Percentages rounded line by line do not necessarily re-add to the basket
    total. Rather than let the difference vanish — which would leave the till a
    franc short with nothing to point at — the last covered line's patient share
    takes it.
    """
    expected = _money(split.gross + split.consultation_fee)
    actual = split.patient_total + split.insurer_total
    drift = _money(expected - actual)
    if drift == ZERO:
        return
    for line in reversed(split.lines):
        if line.covered:
            line.patient = _money(line.patient + drift)
            return
    if split.lines:
        split.lines[-1].patient = _money(split.lines[-1].patient + drift)


def quote(
    *, member_number: str, lines: list[dict[str, Any]], on: date | None = None
) -> dict[str, Any]:
    """What the counter needs before dispensing: eligibility and the split.

    Deliberately read-only. Nothing is claimed or committed until the sale
    completes — a quote that mutated state would leave phantom claims behind
    every time a customer changed their mind.
    """
    verdict = check_eligibility(member_number=member_number, on=on)
    if not verdict.is_eligible or verdict.policy is None:
        return {
            "eligible": False,
            "reason": verdict.reason,
            "member_number": member_number,
            "policy": verdict.policy.pk if verdict.policy else None,
            "patient_pays": None,
            "insurer_pays": None,
        }

    split = split_basket(policy=verdict.policy, lines=lines)
    return {
        "eligible": True,
        "reason": "",
        "member_number": member_number,
        "policy": verdict.policy.pk,
        "member_name": verdict.policy.full_name,
        "scheme": verdict.policy.scheme_id,
        "scheme_name": verdict.policy.scheme.name,
        "copay_pct": str(verdict.copay_pct),
        "consultation_fee": str(split.consultation_fee),
        "gross": str(split.gross),
        "patient_pays": str(split.patient_total),
        "insurer_pays": str(split.insurer_total),
        "reconciles": split.reconciles(),
        "uncovered": [
            {
                "product": getattr(ln.product, "pk", ln.product),
                "amount": str(ln.patient),
                "note": ln.note,
            }
            for ln in split.uncovered_lines
        ],
        "needs_prior_auth": [
            {"product": getattr(ln.product, "pk", ln.product), "note": ln.note}
            for ln in split.needs_prior_auth
        ],
        "lines": [
            {
                "product": getattr(ln.product, "pk", ln.product),
                "quantity": ln.quantity,
                "unit_price": str(ln.unit_price),
                "gross": str(ln.gross),
                "patient": str(ln.patient),
                "insurer": str(ln.insurer),
                "copay_pct": str(ln.copay_pct),
                "covered": ln.covered,
                "requires_prior_auth": ln.requires_prior_auth,
                "note": ln.note,
            }
            for ln in split.lines
        ],
    }
