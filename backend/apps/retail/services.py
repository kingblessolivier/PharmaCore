"""Retail POS services — the write-path that turns a cart into stock movements.

Completing a sale FEFO-consumes the pharmacy's own batches (soonest-expiring
first), writes one immutable ``SALE`` ledger movement per batch, records the
tenders, and generates the fiscal receipt. Voiding reverses every movement.
Each function is one DB transaction.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.documents.models import DocType, Document
from apps.documents.services import generate_document
from apps.finance.services import post_sale_journal
from apps.iam.models import User
from apps.inventory.models import InventoryBatch, StockMovement
from apps.retail.models import (
    Dispensing,
    DrawerSession,
    Payment,
    Prescription,
    Sale,
    SaleBatchAllocation,
    SaleItem,
    SaleReturn,
    SaleReturnItem,
)

_CENTS = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_CENTS)


class InsufficientStock(Exception):
    """Raised when a sale line asks for more sellable units than are on hand."""

    def __init__(
        self, product_label: str, requested: Decimal | int, available: Decimal | int
    ) -> None:
        self.product_label = product_label
        self.requested = requested
        self.available = available
        super().__init__(
            f"Only {available} sellable (non-expired) of '{product_label}' "
            f"in stock ({requested} requested)."
        )


class DispensingRequired(Exception):
    """Raised when an Rx/controlled sale is missing pharmacist + prescription details."""


class PharmacistRequired(Exception):
    """Raised when a non-pharmacist tries to dispense an Rx/controlled item."""


def _product_label(product: Any) -> str:
    return f"{product.generic_name} {product.strength}".strip()


def _free(batch: InventoryBatch) -> Decimal:
    """Units free to sell — on hand minus any held for B2B orders."""
    return batch.quantity_available - batch.quantity_reserved


def _fefo_consume(item: SaleItem, org_id: int, user: User | None) -> None:
    """Draw the line's stock from the org's ACTIVE, non-expired batches, soonest-
    expiring first, recording allocations and one SALE movement per batch touched.

    Consumes ``quantity_base``, never ``quantity``: the line records what the
    customer asked for — one box — and the shelf gives up what that box holds.
    Drawing ``quantity`` would take one tablet off the shelf for a box sold.

    Expired batches (expiry date already passed) are never sold — they are skipped
    entirely, so a lot that lapsed yesterday cannot leave the counter."""
    remaining = item.quantity_base or item.quantity
    today = timezone.localdate()
    batches = [
        batch
        for batch in (
            InventoryBatch.objects.select_for_update()
            .filter(
                organization_id=org_id,
                product=item.product,
                status=InventoryBatch.Status.ACTIVE,
                expiry_date__gte=today,  # never sell expired stock
            )
            .order_by("expiry_date", "batch_number")
        )
        # A broken pack runs on its own, shorter clock: a split portion is held
        # to a 90-day stability window, so a loose remainder can sit inside the
        # printed expiry and outside its own. Sorting on the printed date alone
        # would hand exactly that one over.
        if batch.effective_expiry >= today
    ]
    # FEFO on the date that actually governs, and an already-open pack is
    # exhausted before another is broken — which is what a real counter does,
    # and the opposite of what pure FEFO on the printed date would say.
    batches.sort(key=lambda b: (b.effective_expiry, not b.is_broken_pack, b.batch_number))
    available = sum((max(Decimal(0), _free(b)) for b in batches), Decimal(0))
    if available < remaining:
        raise InsufficientStock(_product_label(item.product), remaining, available)

    for batch in batches:
        if remaining <= 0:
            break
        take = min(remaining, _free(batch))
        if take <= 0:
            continue
        batch.quantity_available -= take
        fields = ["quantity_available", "updated_at"]
        # Selling a fraction breaks the pack. From here the remainder runs on
        # the 90-day split-stability clock and can no longer be returned to the
        # supplier or transferred sealed.
        if batch.opened_at is None and take != take.to_integral_value():
            batch.opened_at = today
            fields.append("opened_at")
        batch.save(update_fields=fields)
        SaleBatchAllocation.objects.create(sale_item=item, batch=batch, quantity=take)
        StockMovement.objects.create(
            organization_id=org_id,
            product=item.product,
            batch=batch,
            batch_number=batch.batch_number,
            movement_type=StockMovement.Type.SALE,
            quantity_delta=-take,
            reference_type="sale",
            reference_id=str(item.sale_id),
            created_by=user,
        )
        remaining -= take


def _generate_receipt(sale: Sale, user: User | None) -> Document:
    lines = [
        {
            "name": _product_label(i.product),
            "tax_class": i.product.tax_class,
            "qty": i.quantity,
            "price": i.unit_price,
            "total": i.line_total,
        }
        for i in sale.items.select_related("product").all()
    ]
    return generate_document(
        organization=sale.organization,
        doc_type=DocType.RECEIPT,
        context={
            "seller_name": sale.organization.name,
            "cashier": (
                sale.cashier.get_full_name() or sale.cashier.username if sale.cashier else ""
            ),
            "sale_number": sale.sale_number,
            "lines": lines,
            "subtotal": sale.subtotal,
            "tax_total": sale.tax_total,
            "total": sale.total,
            "tendered": sale.amount_tendered,
            "change": sale.change_due,
        },
        reference_type="sale",
        reference_id=str(sale.pk),
        user=user,
    )


def _sale_needs_pharmacist(sale: Sale) -> bool:
    """True if any line is prescription-only or a controlled substance."""
    return any(
        i.product.requires_prescription or i.product.is_controlled_substance
        for i in sale.items.select_related("product")
    )


def _is_pharmacist(user: User | None) -> bool:
    if user is None:
        return False
    return bool(user.is_superuser or user.has_role("PHARMACIST") or user.has_role("SYS_ADMIN"))


@transaction.atomic
def complete_sale(
    *,
    sale: Sale,
    payments: list[dict[str, Any]],
    user: User | None,
    dispensing: dict[str, Any] | None = None,
) -> Sale:
    """Take payment for an OPEN sale: FEFO-deduct stock, record tenders, issue the
    receipt, and mark it COMPLETED. Raises on oversell or short payment (no writes).

    If the sale contains prescription-only or controlled items, it may only be
    completed by a pharmacist and must carry patient + prescriber details, which
    are recorded in a Dispensing log."""
    if sale.status != Sale.Status.OPEN:
        raise ValueError("Only an open sale can be completed.")
    if not sale.items.exists():
        raise ValueError("Cannot complete an empty sale.")

    needs_pharmacist = _sale_needs_pharmacist(sale)
    if needs_pharmacist:
        if not _is_pharmacist(user):
            raise PharmacistRequired(
                "A pharmacist must dispense prescription-only or controlled items."
            )
        patient = (dispensing or {}).get("patient_name", "").strip()
        prescriber = (dispensing or {}).get("prescriber_name", "").strip()
        if not patient or not prescriber:
            raise DispensingRequired(
                "This sale needs the patient name and prescribing doctor before dispensing."
            )

    tendered = sum((Decimal(str(p["amount"])) for p in payments), Decimal("0"))
    total = sale.total
    if tendered < total:
        raise ValueError(f"Payment of {tendered} does not cover the total of {total}.")

    for item in sale.items.select_related("product").select_for_update():
        _fefo_consume(item, sale.organization_id, user)

    for p in payments:
        Payment.objects.create(sale=sale, method=p["method"], amount=Decimal(str(p["amount"])))

    sale.amount_tendered = tendered
    sale.change_due = tendered - total
    sale.status = Sale.Status.COMPLETED
    sale.cashier = sale.cashier or user
    sale.completed_at = timezone.now()
    sale.save(
        update_fields=[
            "amount_tendered",
            "change_due",
            "status",
            "cashier",
            "completed_at",
            "updated_at",
        ]
    )

    # F1.3 — emit SaleFinalised on the bus (ADR-010). The journal service and
    # any Reporting/Insights subscriber pick this up asynchronously, so a
    # transient dispatcher failure cannot block a sale.
    from apps.events.publishers import publish_sale_finalised

    publish_sale_finalised(
        sale_id=sale.pk,
        organization=sale.organization,
        user=user,
        payload={
            "total": str(total),
            "payment_status": "PAID",
            "branch_id": sale.organization_id,
        },
    )
    if needs_pharmacist:
        d = dispensing or {}
        Dispensing.objects.create(
            sale=sale,
            dispensed_by=user,
            patient_name=d.get("patient_name", "").strip(),
            patient_id_number=d.get("patient_id_number", "").strip(),
            prescriber_name=d.get("prescriber_name", "").strip(),
            prescriber_license=d.get("prescriber_license", "").strip(),
            prescription_reference=d.get("prescription_reference", "").strip(),
        )
    # Auto-post the sale to the GL so the Finance cockpit reflects today's
    # reality: Dr Cash & Bank / Cr Sales Revenue + VAT Output, then the COGS
    # leg at the FEFO batch's wholesale_cost (Dr COGS / Cr Inventory).
    post_sale_journal(sale=sale, user=user)

    # Everything below is the till doing what a person used to be asked to
    # remember. Each is idempotent on the sale, so a retried completion cannot
    # double-log a narcotic or issue a second fiscal receipt.
    from apps.retail.counter import (
        consume_prescription,
        fiscalise_sale,
        record_controlled_dispensing,
        redeem_promotion,
    )

    # Count the coupon only now. Counting it when it was applied would burn one
    # of a limited promotion's uses on a basket that was abandoned or voided.
    redeem_promotion(sale=sale)

    # Statutory running-balance register for controlled drugs. Previously a
    # separate screen someone typed into afterwards, which guarantees it drifts
    # from the stock it is supposed to account for.
    record_controlled_dispensing(sale=sale, user=user)

    # Rwandan retail must fiscalise. The TaxRecord model existed and nothing
    # called it, so no sale in the system had an EBM record.
    fiscalise_sale(sale=sale, user=user)

    # Dispensing against a prescription uses up a fill. Without this the refill
    # counter never moves and a prescription can be filled indefinitely.
    reference = (dispensing or {}).get("prescription_id")
    if reference:
        prescription = Prescription.objects.filter(
            pk=reference, organization=sale.organization
        ).first()
        if prescription is not None:
            consume_prescription(sale=sale, prescription=prescription, user=user)

    _generate_receipt(sale, user)
    return sale


def _return_to_stock(item: SaleItem, quantity: Decimal, user: User | None) -> None:
    """Put returned units back on the shelf — onto the batch(es) they were sold
    from where those still exist, else the product's earliest-expiring batch."""
    remaining = quantity
    for alloc in item.allocations.select_related("batch").order_by("batch__expiry_date"):
        if remaining <= 0:
            break
        take = min(remaining, alloc.quantity)
        batch = alloc.batch
        batch.quantity_available += take
        batch.save(update_fields=["quantity_available", "updated_at"])
        StockMovement.objects.create(
            organization_id=item.sale.organization_id,
            product=item.product,
            batch=batch,
            batch_number=batch.batch_number,
            movement_type=StockMovement.Type.RETURN,
            quantity_delta=take,
            reference_type="sale_return",
            reference_id=str(item.sale_id),
            reason="Customer return",
            created_by=user,
        )
        remaining -= take


def _generate_credit_note(ret: SaleReturn, user: User | None) -> None:
    sale = ret.sale
    generate_document(
        organization=sale.organization,
        doc_type=DocType.CREDIT_NOTE,
        context={
            "seller_name": sale.organization.name,
            "sale_number": sale.sale_number,
            "return_number": ret.return_number,
            "reason": ret.reason,
            "lines": [
                {
                    "name": _product_label(ri.sale_item.product),
                    "qty": ri.quantity,
                    "refund": ri.refund_amount,
                }
                for ri in ret.items.select_related("sale_item__product").all()
            ],
            "refund": ret.refund_amount,
        },
        reference_type="sale_return",
        reference_id=str(ret.pk),
        user=user,
    )


@transaction.atomic
def return_sale_items(
    *, sale: Sale, lines: list[dict[str, Any]], reason: str, user: User | None
) -> SaleReturn:
    """Return some items from a completed sale: put stock back, refund the value,
    and issue a credit note. ``lines`` = [{"sale_item": id, "quantity": n}]."""
    if sale.status != Sale.Status.COMPLETED:
        raise ValueError("Only a completed sale can be returned against.")

    ret = SaleReturn.objects.create(sale=sale, reason=reason, created_by=user)
    refund = Decimal("0")
    any_line = False
    for line in lines:
        item = sale.items.select_for_update().get(pk=line["sale_item"])
        qty = Decimal(str(line.get("quantity", 0)))
        if qty <= 0:
            continue
        if qty > item.returnable:
            raise ValueError(
                f"Cannot return {qty} of '{_product_label(item.product)}' — "
                f"only {item.returnable} left to return."
            )
        _return_to_stock(item, qty, user)
        item.returned_quantity += qty
        item.save(update_fields=["returned_quantity"])
        line_refund = (item.unit_price * qty).quantize(Decimal("0.01"))
        SaleReturnItem.objects.create(
            sale_return=ret, sale_item=item, quantity=qty, refund_amount=line_refund
        )
        refund += line_refund
        any_line = True

    if not any_line:
        raise ValueError("No items to return.")

    ret.refund_amount = refund
    ret.return_number = f"RET-{ret.pk:06d}"
    ret.save(update_fields=["refund_amount", "return_number"])
    _generate_credit_note(ret, user)
    return ret


@transaction.atomic
def void_sale(*, sale: Sale, reason: str, user: User | None) -> Sale:
    """Reverse a COMPLETED sale: return each allocated quantity to its batch and
    append a RETURN movement. The receipt already issued stays in the vault."""
    if sale.status != Sale.Status.COMPLETED:
        raise ValueError("Only a completed sale can be voided.")

    for item in sale.items.select_related("product").all():
        for alloc in item.allocations.select_related("batch").select_for_update():
            batch = alloc.batch
            batch.quantity_available += alloc.quantity
            batch.save(update_fields=["quantity_available", "updated_at"])
            StockMovement.objects.create(
                organization_id=sale.organization_id,
                product=item.product,
                batch=batch,
                batch_number=batch.batch_number,
                movement_type=StockMovement.Type.RETURN,
                quantity_delta=alloc.quantity,
                reference_type="sale_void",
                reference_id=str(sale.pk),
                reason=reason,
                created_by=user,
            )

    sale.status = Sale.Status.VOIDED
    sale.void_reason = reason
    sale.voided_at = timezone.now()
    sale.save(update_fields=["status", "void_reason", "voided_at", "updated_at"])
    return sale


def drawer_report(session: DrawerSession) -> dict[str, Any]:
    """The cash position of a till session (works while OPEN as an X-report, and on
    CLOSE as a Z-report). Expected drawer cash =
    opening float + cash taken − change given − cash refunds.

    Only physical cash affects the drawer; mobile-money / card tenders are reported
    separately for the shift total but don't change what's in the till.
    """
    completed = session.sales.filter(status=Sale.Status.COMPLETED)
    cash_in = Payment.objects.filter(
        sale__drawer_session=session,
        sale__status=Sale.Status.COMPLETED,
        method=Payment.Method.CASH,
    ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
    change_out = completed.aggregate(s=Sum("change_due"))["s"] or Decimal("0")
    refunds = SaleReturn.objects.filter(sale__drawer_session=session).aggregate(
        s=Sum("refund_amount")
    )["s"] or Decimal("0")
    noncash = Payment.objects.filter(
        sale__drawer_session=session, sale__status=Sale.Status.COMPLETED
    ).exclude(method=Payment.Method.CASH).aggregate(s=Sum("amount"))["s"] or Decimal("0")
    expected = session.opening_float + cash_in - change_out - refunds
    # Money as strings, matching the rest of the API (DRF coerces decimals to strings).
    return {
        "sales_count": completed.count(),
        "opening_float": str(_q(session.opening_float)),
        "cash_payments": str(_q(cash_in)),
        "change_given": str(_q(change_out)),
        "cash_refunds": str(_q(refunds)),
        "noncash_payments": str(_q(noncash)),
        "expected_cash": str(_q(expected)),
    }


@transaction.atomic
def close_drawer(
    *, session: DrawerSession, counted_cash: Decimal, user: User | None, notes: str = ""
) -> DrawerSession:
    """Cash up: reconcile the counted cash against the expected cash and close."""
    if session.status != DrawerSession.Status.OPEN:
        raise ValueError("This drawer is already closed.")
    expected = Decimal(drawer_report(session)["expected_cash"])
    session.counted_cash = _q(counted_cash)
    session.expected_cash = expected
    session.over_short = _q(counted_cash - expected)
    session.notes = notes
    session.status = DrawerSession.Status.CLOSED
    session.closed_at = timezone.now()
    session.closed_by = user
    session.save(
        update_fields=[
            "counted_cash",
            "expected_cash",
            "over_short",
            "notes",
            "status",
            "closed_at",
            "closed_by",
        ]
    )

    # A till shortage is a real cost. It used to be computed here, stored, and
    # never posted, so cash losses never reached the P&L and the GL cash balance
    # drifted from the drawer by the whole variance.
    from apps.finance.operations import post_drawer_variance

    post_drawer_variance(drawer=session, user=user)
    return session
