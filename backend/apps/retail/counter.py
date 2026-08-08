"""What a completed sale must record beyond taking the money.

`complete_sale` deducted stock, took payment, posted the journal and printed a
receipt. Four things it never did, each of which a pharmacy is either legally or
commercially obliged to do:

* **The controlled-drugs register** was a separate screen someone typed into
  afterwards. It is a statutory running-balance record; asking a pharmacist to
  dispense and then retype it elsewhere guarantees the register disagrees with the
  stock, and the register is the document an inspector reads.
* **EBM fiscalisation** never happened. Rwandan retail must fiscalise; the
  `TaxRecord` model with its SDC id, MRC number and QR payload existed and nothing
  called it.
* **Promotions** were configured and never applied. Campaigns, coupons and BOGO
  bundles all sat in the database while every checkout charged full price.
* **Prescriptions** were referenced by free text, so dispensing never decremented
  a refill or advanced a prescription's status.

Each is written here, by the till, at the moment of sale — not by a person
remembering afterwards.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.iam.models import Organization, User

from .models import (
    ControlledSubstanceRegister,
    Dispensing,
    POSPromotion,
    Prescription,
    Sale,
)

ZERO = Decimal("0.00")


def _q(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------- #
# Barcodes — the till's primary input
# --------------------------------------------------------------------------- #


@dataclass
class ScanResult:
    product: Any
    # A carton barcode means the customer is buying a carton, not one tablet.
    units: int
    packaging_level: str
    barcode: str


def resolve_barcode(*, organization: Organization, code: str) -> ScanResult | None:
    """Turn a scanned code into a product and the quantity that code represents.

    Packaging level matters: scanning a carton must add the number of units in
    that carton, not one. Getting this wrong undercharges by the case.
    """
    from apps.catalog.models import ProductBarcode

    cleaned = (code or "").strip()
    if not cleaned:
        return None

    match = (
        ProductBarcode.objects.select_related("product")
        .filter(barcode__iexact=cleaned)
        .order_by("id")
        .first()
    )
    if match is None:
        return None
    return ScanResult(
        product=match.product,
        units=max(match.units_per_level or 1, 1),
        packaging_level=match.packaging_level,
        barcode=match.barcode,
    )


# --------------------------------------------------------------------------- #
# Promotions
# --------------------------------------------------------------------------- #


@dataclass
class PromotionOutcome:
    promotion: POSPromotion | None
    discount: Decimal
    reason: str

    @property
    def applied(self) -> bool:
        return self.promotion is not None and self.discount > 0


def active_promotions(*, organization: Any = None, on: date | None = None) -> list[POSPromotion]:
    """Promotions in force today **at this pharmacy**.

    Effective dates are respected, not decorative — and so is whose promotion it
    is. A promotion with no organization is group-wide, which is how a chain runs
    one campaign across its branches.
    """
    when = on or timezone.localdate()
    qs = POSPromotion.objects.filter(is_active=True, valid_from__lte=when, valid_until__gte=when)
    if organization is not None:
        org_id = getattr(organization, "pk", organization)
        qs = qs.filter(Q(organization_id=org_id) | Q(organization__isnull=True))
    return list(qs.order_by("code"))


def evaluate_promotion(*, sale: Sale, code: str, on: date | None = None) -> PromotionOutcome:
    """What a coupon is worth on this basket, and why.

    Returns a reason on every path. A till that silently ignores a code the
    customer is holding produces an argument at the counter; one that says
    "expired on 30 June" ends it.
    """
    when = on or timezone.localdate()
    cleaned = (code or "").strip().upper()
    if not cleaned:
        return PromotionOutcome(None, ZERO, "No code entered.")

    # Scoped to the pharmacy ringing the sale: a code created at one branch used
    # to be redeemable at every branch in the system.
    promotion = (
        POSPromotion.objects.filter(code__iexact=cleaned)
        .filter(Q(organization_id=sale.organization_id) | Q(organization__isnull=True))
        .first()
    )
    if promotion is None:
        return PromotionOutcome(None, ZERO, f"No promotion with the code {cleaned}.")
    if not promotion.is_active:
        return PromotionOutcome(None, ZERO, f"{promotion.name} is switched off.")
    if when < promotion.valid_from:
        return PromotionOutcome(
            None, ZERO, f"{promotion.name} does not start until {promotion.valid_from}."
        )
    if when > promotion.valid_until:
        return PromotionOutcome(None, ZERO, f"{promotion.name} expired on {promotion.valid_until}.")

    subtotal = _q(sale.total)
    if subtotal < _q(promotion.min_spend):
        short = _q(promotion.min_spend) - subtotal
        return PromotionOutcome(None, ZERO, f"Spend {short} more to qualify for {promotion.name}.")

    if promotion.promo_type == POSPromotion.PromoType.PERCENT_DISCOUNT:
        discount = _q(subtotal * _q(promotion.discount_value) / Decimal("100"))
    elif promotion.promo_type == POSPromotion.PromoType.FLAT_DISCOUNT:
        discount = _q(promotion.discount_value)
    else:  # BOGO — the cheapest unit of the highest-quantity line goes free.
        discount = _bogo_discount(sale)

    # Never discount past zero: a promotion is a price reduction, not a refund.
    discount = min(discount, subtotal)
    if discount <= 0:
        return PromotionOutcome(None, ZERO, f"{promotion.name} is worth nothing on this basket.")
    return PromotionOutcome(promotion, discount, f"{promotion.name} applied.")


def _bogo_discount(sale: Sale) -> Decimal:
    """One free unit for every two of the same product.

    Priced at the line's own unit price rather than the basket's cheapest, so the
    customer gets the item they actually bought two of.
    """
    discount = ZERO
    for item in sale.items.all():
        free_units = item.quantity // 2
        if free_units:
            discount += _q(Decimal(free_units) * item.unit_price)
    return _q(discount)


# --------------------------------------------------------------------------- #
# Controlled drugs register
# --------------------------------------------------------------------------- #


def _running_balance(organization: Organization, product: Any) -> int | None:
    """The register's last balance for this product, or None if it has no history."""
    latest = (
        ControlledSubstanceRegister.objects.filter(organization=organization, product=product)
        .order_by("-logged_at", "-id")
        .first()
    )
    if latest is not None:
        return latest.running_balance
    return None


def _on_hand(organization: Organization, product: Any) -> int:
    """Units physically in stock right now, across every batch."""
    from apps.inventory.models import InventoryBatch

    total = InventoryBatch.objects.filter(organization=organization, product=product).aggregate(
        total=Sum("quantity_available")
    )["total"]
    return int(total or 0)


@transaction.atomic
def record_controlled_dispensing(*, sale: Sale, user: User | None = None) -> list[Any]:
    """Write the statutory register for every controlled item on a sale.

    Idempotent on the sale: a retried completion must not double-log a narcotic.
    """
    entries: list[Any] = []
    dispensing = getattr(sale, "dispensing", None)

    for item in sale.items.select_related("product"):
        if not getattr(item.product, "is_controlled_substance", False):
            continue

        reference = f"SALE:{sale.pk}:{item.pk}"
        if ControlledSubstanceRegister.objects.filter(
            organization=sale.organization, product=item.product, rx_reference=reference
        ).exists():
            continue

        # The register must agree with the shelf. This runs after FEFO has already
        # deducted the stock, so for a product with no register history the correct
        # closing balance is simply what is physically on hand now — opening at
        # on-hand and subtracting again would understate it by this sale.
        previous = _running_balance(sale.organization, item.product)
        batch_number = ""
        allocation = item.allocations.select_related("batch").first()
        if allocation is not None and allocation.batch is not None:
            batch_number = allocation.batch.batch_number

        entries.append(
            ControlledSubstanceRegister.objects.create(
                organization=sale.organization,
                product=item.product,
                batch_number=batch_number,
                movement_type=ControlledSubstanceRegister.MovementType.DISPENSING,
                quantity=item.quantity,
                # Never below zero: the register is a count of physical units.
                running_balance=(
                    max(previous - item.quantity, 0)
                    if previous is not None
                    else _on_hand(sale.organization, item.product)
                ),
                patient_name=getattr(dispensing, "patient_name", "") or "",
                prescriber_name=getattr(dispensing, "prescriber_name", "") or "",
                rx_reference=reference,
                logged_by=user,
            )
        )
    return entries


# --------------------------------------------------------------------------- #
# EBM fiscalisation
# --------------------------------------------------------------------------- #


def _sdc_signature(sale: Sale, payload: str) -> str:
    """A deterministic stand-in for the SDC signature.

    The real device signs the receipt; until it is connected this keeps the shape
    of the record honest — one stable signature per sale, derived from its
    contents, so a tampered total produces a different value.
    """
    return hashlib.sha256(f"{sale.pk}:{payload}".encode()).hexdigest()[:32].upper()


@transaction.atomic
def fiscalise_sale(*, sale: Sale, user: User | None = None) -> Any:
    """Create the EBM record for a completed sale.

    Rwandan retail must fiscalise. The `TaxRecord` model — SDC id, MRC number, QR
    payload — was built and nothing ever called it, so no sale in the system had
    a fiscal record.

    Idempotent on the sale: a receipt is fiscalised once.
    """
    from apps.finance.models import TaxRecord
    from apps.finance.services import tenant_settings_for

    existing = TaxRecord.objects.filter(
        organization=sale.organization, receipt_number=sale.sale_number
    ).first()
    if existing is not None:
        return existing

    taxable = _q(sum((i.line_net for i in sale.items.all()), ZERO))
    vat = _q(sum((i.line_tax for i in sale.items.all()), ZERO))

    # Read directly, not through getattr with a fallback: a default that silently
    # stamps "UNREGISTERED" on every receipt forever is worse than an empty field,
    # because nobody ever notices it.
    settings = tenant_settings_for(sale.organization)
    sdc_id = settings.ebm_sdc_id
    mrc = settings.ebm_mrc_number
    registered = bool(sdc_id and mrc)

    payload = f"{sale.sale_number}|{taxable}|{vat}"
    return TaxRecord.objects.create(
        organization=sale.organization,
        receipt_number=sale.sale_number,
        sdc_id=sdc_id or "UNREGISTERED",
        mrc_number=mrc or "UNREGISTERED",
        taxable_amount=taxable,
        vat_amount=vat,
        tax_class_b=vat,
        # No QR without a registered device — a verification link that resolves to
        # nothing is worse than none, because it looks fiscalised.
        qr_code_payload=(
            f"https://ebm.rra.gov.rw/verify/{sale.sale_number}?s={_sdc_signature(sale, payload)}"
            if registered
            else ""
        ),
    )


# --------------------------------------------------------------------------- #
# Prescriptions
# --------------------------------------------------------------------------- #


class PrescriptionError(Exception):
    """Raised when a prescription cannot be dispensed against."""


@transaction.atomic
def consume_prescription(
    *, sale: Sale, prescription: Prescription, user: User | None = None
) -> Prescription:
    """Record that this sale filled a prescription, and use up a refill.

    Previously `SaleItem.prescription_reference` was free text, so a prescription
    could be dispensed against forever: nothing decremented the refill counter and
    nothing ever moved it out of ACTIVE.
    """
    if prescription.organization_id != sale.organization_id:
        raise PrescriptionError("That prescription belongs to another pharmacy.")
    if prescription.status != Prescription.Status.ACTIVE:
        state = prescription.get_status_display().lower()
        raise PrescriptionError(f"This prescription is {state} and cannot be filled.")
    if prescription.refills_used >= prescription.refills_allowed:
        raise PrescriptionError(
            f"All {prescription.refills_allowed} fill(s) of this prescription have been used."
        )

    prescription.refills_used += 1
    if prescription.refills_used >= prescription.refills_allowed:
        prescription.status = Prescription.Status.FULFILLED
    prescription.save(update_fields=["refills_used", "status"])

    # Stamp the dispensing record — that is where the reference lives, and the FK
    # keeps the link even if the number is later reused.
    Dispensing.objects.filter(sale=sale).update(
        prescription=prescription, prescription_reference=prescription.prescription_number
    )
    return prescription


def refills_remaining(prescription: Prescription) -> int:
    return max(prescription.refills_allowed - prescription.refills_used, 0)


# --------------------------------------------------------------------------- #
# Applying a promotion to a basket
# --------------------------------------------------------------------------- #


@transaction.atomic
def apply_promotion(*, sale: Sale, code: str, on: date | None = None) -> PromotionOutcome:
    """Evaluate a coupon and record the result on the sale.

    Evaluating alone was not enough: `Sale` had nowhere to put a discount, so the
    number was computed and thrown away and every basket charged full price.
    """
    if sale.status != Sale.Status.OPEN:
        raise ValueError("Only an open sale can be discounted.")

    outcome = evaluate_promotion(sale=sale, code=code, on=on)
    if not outcome.applied:
        return outcome

    promotion = outcome.promotion
    assert promotion is not None
    # A cap is checked at the moment of use, not when the coupon was issued —
    # otherwise two tills redeem the last one simultaneously.
    if promotion.max_redemptions and promotion.times_redeemed >= promotion.max_redemptions:
        return PromotionOutcome(
            None, ZERO, f"{promotion.name} has reached its limit of {promotion.max_redemptions}."
        )

    sale.promotion = promotion
    sale.discount_amount = outcome.discount
    sale.save(update_fields=["promotion", "discount_amount", "updated_at"])
    return outcome


@transaction.atomic
def clear_promotion(*, sale: Sale) -> Sale:
    """Take a coupon back off a basket — the customer changed their mind."""
    sale.promotion = None
    sale.discount_amount = ZERO
    sale.save(update_fields=["promotion", "discount_amount", "updated_at"])
    return sale


@transaction.atomic
def redeem_promotion(*, sale: Sale) -> None:
    """Count the redemption once the sale is actually completed.

    Counted at completion rather than at application, so a basket that is
    abandoned or voided does not burn one of a limited coupon's uses.
    """
    if sale.promotion_id is None or sale.discount_amount <= 0:
        return
    POSPromotion.objects.filter(pk=sale.promotion_id).update(
        times_redeemed=models.F("times_redeemed") + 1
    )


# --------------------------------------------------------------------------- #
# Clinical services — billed, and now banked
# --------------------------------------------------------------------------- #


@transaction.atomic
def bill_clinical_service(*, record: Any, user: User | None = None) -> Any:
    """Post a clinical service fee to the ledger.

    `fee_charged` was recorded on the encounter and never reached the till or the
    books, so `4300 Services Revenue` — an account created for exactly this — sat
    permanently empty while the pharmacy earned money on vaccinations, screenings
    and consultations.

        Dr Cash on hand      the fee
        Cr Services revenue  the fee

    Idempotent on the encounter.
    """
    from apps.finance.models import JournalLine
    from apps.finance.services import ensure_default_accounts, post_journal

    if record.is_paid:
        return record

    fee = _q(record.fee_charged)
    if fee <= 0:
        record.is_paid = True
        record.save(update_fields=["is_paid"])
        return record

    accounts = ensure_default_accounts(record.organization)
    post_journal(
        organization=record.organization,
        entry_date=timezone.localdate(),
        description=f"Clinical service — {record.service.name}",
        lines=[
            {
                "account": accounts["1100"],
                "side": JournalLine.Side.DEBIT,
                "amount": fee,
                "memo": record.patient_name[:200],
            },
            {
                "account": accounts["4300"],
                "side": JournalLine.Side.CREDIT,
                "amount": fee,
                "memo": record.service.name[:200],
            },
        ],
        reference_type="clinical_service",
        reference_id=str(record.pk),
        source_module="SALES",
        user=user,
    )
    record.is_paid = True
    record.save(update_fields=["is_paid"])
    return record
