"""Procurement services — the write-path for the buy side.

Every state change that matters lives here (never in a serializer or view), so the
same rule holds whether it is triggered by the API, a management command or a test:

* numbering is gapless and transactional (``next_document_number``);
* sensitive steps (requisition, purchase order, supplier invoice) are routed to the
  **shared approvals engine** — claim-to-lock, no self-approval, SLA timers — and
  applied by the handlers registered at the bottom of this module;
* goods only become saleable stock through ``post_goods_receipt``, which writes the
  immutable inventory movements and parks the batch in quarantine for QC;
* money only reaches the ledger through ``apps.finance.services.post_journal``.

GL treatment of a purchase (kept deliberately explicit):

    Goods receipt posted   Dr 1200 Inventory on Hand    (landed value received)
                           Cr 2150 GRNI                 (goods received, not invoiced)

    Invoice approved       Dr 2150 GRNI                 (clears the accrual)
                           Dr 5000 COGS                 (price variance, either side)
                           Dr 1300 VAT Input            (recoverable)
                           Cr 2000 Accounts Payable     (what we now owe)

    Note issued            Dr 2000 Accounts Payable     (we owe the supplier less)
                           Cr 5000 COGS
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.approvals import registry
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import request_approval
from apps.catalog.units import normalise
from apps.documents.models import DocType, Document
from apps.documents.services import generate_document
from apps.finance.models import Account, JournalLine, SupplierBill
from apps.finance.services import JournalLineInput, ensure_default_accounts, post_journal
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User
from apps.inventory.models import InventoryBatch, QualityCheck
from apps.inventory.services import receive_intake
from apps.procurement.models import (
    ZERO,
    GoodsReceipt,
    GoodsReceiptLine,
    ImportConsignment,
    NumberSequence,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    RequestForQuotation,
    SupplierEvaluation,
    SupplierInvoice,
    SupplierLicence,
    SupplierNote,
    SupplierPriceAgreement,
    SupplierProfile,
    SupplierQuote,
    _q,
)

# Approval resource keys — the strings the central inbox groups on.
RES_REQUISITION = "procurement.requisition"
RES_PURCHASE_ORDER = "procurement.purchase_order"
RES_SUPPLIER_INVOICE = "procurement.supplier_invoice"

GRNI_CODE = "2150"


class ProcurementError(ValueError):
    """A business-rule violation — surfaced to the API as a 400, never a 500."""


# ---------------------------------------------------------------------------
# Numbering
# ---------------------------------------------------------------------------


@transaction.atomic
def next_document_number(organization: Organization, kind: str) -> str:
    """Allocate the next gapless number for a document kind, e.g. ``PO-2026-00042``."""
    year = timezone.now().year
    seq, _ = NumberSequence.objects.select_for_update().get_or_create(
        organization=organization,
        domain=NumberSequence.Domain.PROCUREMENT,
        kind=kind,
        year=year,
    )
    number = seq.next_number
    seq.next_number += 1
    seq.save(update_fields=["next_number"])
    return f"{kind}-{year}-{number:05d}"


# ---------------------------------------------------------------------------
# Approvals plumbing
# ---------------------------------------------------------------------------


def sync_approval_outcomes(
    *, resource_type: str, objects: list[Any], pending_status: str, rejected_status: str
) -> None:
    """Reflect engine *rejections* back onto their source documents.

    The approvals engine only calls a handler when a request is approved (a
    rejection is, by design, "nothing happens"). Documents still need to leave
    their pending state, so before listing/serving them we take one query over
    the decided requests and flip any that were turned down.
    """
    pending = [o for o in objects if o.status == pending_status]
    if not pending:
        return
    decided = ApprovalRequest.objects.filter(
        resource_type=resource_type,
        resource_id__in=[str(o.pk) for o in pending],
        status=ApprovalRequest.Status.REJECTED,
    ).values_list("resource_id", "decision_note")
    notes = dict(decided)
    for obj in pending:
        note = notes.get(str(obj.pk))
        if note is None:
            continue
        obj.status = rejected_status
        fields = ["status"]
        if hasattr(obj, "decision_note"):
            obj.decision_note = note or "Rejected by approver."
            fields.append("decision_note")
        if hasattr(obj, "rejected_reason"):
            obj.rejected_reason = note or "Rejected by approver."
            fields.append("rejected_reason")
        obj.save(update_fields=fields)


def open_approval_for(resource_type: str, obj: Any) -> ApprovalRequest | None:
    return (
        ApprovalRequest.objects.filter(
            resource_type=resource_type,
            resource_id=str(obj.pk),
            status=ApprovalRequest.Status.PENDING,
        )
        .order_by("-created_at")
        .first()
    )


# ---------------------------------------------------------------------------
# Supplier master
# ---------------------------------------------------------------------------


def get_or_create_profile(supplier: Any) -> SupplierProfile:
    profile, _ = SupplierProfile.objects.get_or_create(supplier=supplier)
    return profile


def supplier_licence_issues(supplier: Any) -> list[str]:
    """Reasons this supplier is not qualified to receive an order right now."""
    issues: list[str] = []
    required = SupplierLicence.objects.filter(supplier=supplier, is_required=True)
    if not required.exists():
        issues.append("No required licence is on file (GDP supplier qualification).")
    for licence in required:
        label = licence.get_kind_display()
        if not licence.is_verified:
            issues.append(f"{label} is not verified.")
        if licence.is_expired:
            issues.append(f"{label} expired on {licence.expires_on}.")
    return issues


def assert_supplier_orderable(supplier: Any) -> None:
    """Trading-partner qualification gate — enforced before a PO is approved."""
    profile = SupplierProfile.objects.filter(supplier=supplier).first()
    if profile and not profile.can_order:
        raise ProcurementError(
            f"{supplier.name} is {profile.get_standing_display().lower()} — "
            "no new purchase orders may be approved for this supplier."
        )
    issues = supplier_licence_issues(supplier)
    if issues:
        raise ProcurementError(f"{supplier.name} is not qualified to supply: " + " ".join(issues))


@transaction.atomic
def set_supplier_standing(
    *, profile: SupplierProfile, standing: str, reason: str, user: User | None
) -> SupplierProfile:
    """Preferred / approved / probation / suspended / blacklisted — always audited."""
    if standing not in SupplierProfile.Standing.values:
        raise ProcurementError(f"'{standing}' is not a valid supplier standing.")
    if (
        standing
        in {
            SupplierProfile.Standing.SUSPENDED,
            SupplierProfile.Standing.BLACKLISTED,
        }
        and not reason.strip()
    ):
        raise ProcurementError("Suspending or blacklisting a supplier requires a reason.")
    previous = profile.standing
    profile.standing = standing
    profile.standing_reason = reason
    profile.standing_changed_at = timezone.now()
    profile.standing_changed_by = user
    profile.save(
        update_fields=[
            "standing",
            "standing_reason",
            "standing_changed_at",
            "standing_changed_by",
            "updated_at",
        ]
    )
    record_audit(
        action="SUPPLIER_STANDING",
        user=user,
        organization=None,
        entity_type="supplier_profile",
        entity_id=str(profile.pk),
        changes={"from": previous, "to": standing, "reason": reason},
    )
    return profile


def resolve_supplier_price(
    *,
    supplier: Any,
    product: Any,
    quantity: int = 1,
    organization: Organization | None = None,
    day: date | None = None,
) -> SupplierPriceAgreement | None:
    """The contract price that applies — best volume break in force on ``day``.

    A branch-specific agreement beats a group-wide one; among those, the highest
    ``min_quantity`` the order qualifies for wins.
    """
    day = day or timezone.localdate()
    candidates = [
        a
        for a in SupplierPriceAgreement.objects.filter(
            supplier=supplier, product=product, is_active=True, min_quantity__lte=quantity
        ).select_related("organization")
        if a.covers(day)
        and (a.organization_id is None or a.organization_id == getattr(organization, "pk", None))
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda a: (a.organization_id is not None, a.min_quantity))
    return candidates[-1]


@transaction.atomic
def refresh_supplier_scores(
    *,
    supplier: Any,
    organization: Organization,
    period_start: date,
    period_end: date,
    user: User | None = None,
    price_competitiveness: Decimal | None = None,
    responsiveness: Decimal | None = None,
    documentation_compliance: Decimal | None = None,
    comments: str = "",
) -> SupplierEvaluation:
    """Score a supplier over a period from what actually happened.

    Delivery and quality are computed from the receipts (no self-reporting);
    price/responsiveness/documentation are the buyer's judgement, defaulting to
    the profile's last value so a partial rating never wipes the scorecard.
    """
    receipts = GoodsReceipt.objects.filter(
        order__supplier=supplier,
        order__organization=organization,
        status=GoodsReceipt.Status.POSTED,
        received_on__gte=period_start,
        received_on__lte=period_end,
    ).select_related("order")

    on_time = late = 0
    received_units = rejected_units = Decimal(0)
    orders_seen: set[int] = set()
    for receipt in receipts.prefetch_related("lines"):
        orders_seen.add(receipt.order_id)
        due = receipt.order.expected_delivery
        if due is None or receipt.received_on <= due:
            on_time += 1
        else:
            late += 1
        for line in receipt.lines.all():
            received_units += line.quantity_received
            rejected_units += line.quantity_rejected

    deliveries = on_time + late
    delivery_score = _q(Decimal(on_time) * 100 / Decimal(deliveries)) if deliveries else ZERO
    total_units = received_units + rejected_units
    quality_score = (
        _q(Decimal(received_units) * 100 / Decimal(total_units)) if total_units else ZERO
    )

    profile = get_or_create_profile(supplier)
    price = price_competitiveness if price_competitiveness is not None else profile.price_score
    resp = responsiveness if responsiveness is not None else profile.compliance_score
    docs = (
        documentation_compliance
        if documentation_compliance is not None
        else (ZERO if supplier_licence_issues(supplier) else Decimal("100"))
    )
    overall = _q((delivery_score + quality_score + Decimal(price) + Decimal(docs)) / Decimal("4"))

    evaluation = SupplierEvaluation.objects.create(
        supplier=supplier,
        organization=organization,
        period_start=period_start,
        period_end=period_end,
        orders_count=len(orders_seen),
        on_time_delivery_pct=delivery_score,
        quality_acceptance_pct=quality_score,
        price_competitiveness=price,
        responsiveness=resp,
        documentation_compliance=docs,
        overall_score=overall,
        is_auto_generated=price_competitiveness is None,
        comments=comments,
        rated_by=user,
    )
    profile.delivery_score = delivery_score
    profile.quality_score = quality_score
    profile.price_score = Decimal(price)
    profile.compliance_score = Decimal(docs)
    profile.scores_updated_at = timezone.now()
    profile.save(
        update_fields=[
            "delivery_score",
            "quality_score",
            "price_score",
            "compliance_score",
            "scores_updated_at",
            "updated_at",
        ]
    )
    return evaluation


# ---------------------------------------------------------------------------
# Requisitions
# ---------------------------------------------------------------------------


@transaction.atomic
def submit_requisition(*, requisition: PurchaseRequisition, user: User) -> ApprovalRequest:
    """Send a branch requisition to the central approvals inbox."""
    if requisition.status != PurchaseRequisition.Status.DRAFT:
        raise ProcurementError("Only a draft requisition can be submitted.")
    if not requisition.lines.exists():
        raise ProcurementError("Add at least one line before submitting.")
    if not requisition.requisition_number:
        requisition.requisition_number = next_document_number(
            requisition.organization, NumberSequence.Kind.REQUISITION
        )
    requisition.status = PurchaseRequisition.Status.SUBMITTED
    requisition.submitted_at = timezone.now()
    requisition.save(update_fields=["requisition_number", "status", "submitted_at", "updated_at"])
    approval = request_approval(
        resource_type=RES_REQUISITION,
        resource_id=str(requisition.pk),
        organization=requisition.organization,
        requested_by=user,
        payload={
            "requisition_number": requisition.requisition_number,
            "lines": requisition.lines.count(),
            "estimated_total": str(requisition.estimated_total),
            "priority": requisition.priority,
        },
        reason=requisition.justification[:300] or f"Requisition {requisition.requisition_number}",
    )
    record_audit(
        action="REQUISITION_SUBMIT",
        user=user,
        organization=requisition.organization,
        entity_type="purchase_requisition",
        entity_id=str(requisition.pk),
        changes={"number": requisition.requisition_number},
    )
    return approval


@registry.register(RES_REQUISITION)
def _apply_requisition_approval(approval: ApprovalRequest) -> None:
    requisition = PurchaseRequisition.objects.filter(pk=approval.resource_id).first()
    if requisition is None or requisition.status != PurchaseRequisition.Status.SUBMITTED:
        return
    requisition.status = PurchaseRequisition.Status.APPROVED
    requisition.approved_by = approval.decided_by
    requisition.approved_at = timezone.now()
    requisition.decision_note = approval.decision_note
    requisition.save(
        update_fields=["status", "approved_by", "approved_at", "decision_note", "updated_at"]
    )
    # Default the approved quantity to what was asked for, unless a reviewer
    # already trimmed individual lines.
    for line in requisition.lines.all():
        if line.quantity_approved == 0:
            line.quantity_approved = line.quantity
            line.save(update_fields=["quantity_approved"])


@transaction.atomic
def consolidate_requisitions(
    *,
    organization: Organization,
    supplier: Any,
    requisitions: list[PurchaseRequisition],
    user: User,
    expected_delivery: date | None = None,
    currency: str | None = None,
    exchange_rate: Decimal | None = None,
    is_import: bool = False,
    deliver_to: Organization | None = None,
) -> PurchaseOrder:
    """Roll several approved branch requisitions into one supplier PO.

    Demand for the same product across branches is merged onto a single line —
    that consolidation is the whole point of buying centrally at HQ.
    """
    if not requisitions:
        raise ProcurementError("Select at least one approved requisition.")
    for req in requisitions:
        if req.status != PurchaseRequisition.Status.APPROVED:
            raise ProcurementError(
                f"{req} is {req.get_status_display().lower()} — only approved "
                "requisitions can be consolidated."
            )

    profile = SupplierProfile.objects.filter(supplier=supplier).first()
    order = PurchaseOrder.objects.create(
        po_number=next_document_number(organization, NumberSequence.Kind.PURCHASE_ORDER),
        organization=organization,
        supplier=supplier,
        currency=currency or (profile.currency if profile else "RWF"),
        exchange_rate=exchange_rate or Decimal("1"),
        incoterm=(profile.incoterm if profile else ""),
        payment_terms_days=(profile.payment_terms_days if profile else 30),
        expected_delivery=expected_delivery,
        is_import=is_import,
        deliver_to=deliver_to,
        is_dropship=bool(deliver_to and deliver_to.pk != organization.pk),
        requisition=requisitions[0],
        notes="Consolidated from: "
        + ", ".join(r.requisition_number or str(r.pk) for r in requisitions),
        created_by=user,
    )

    merged: dict[int, dict[str, Any]] = {}
    for req in requisitions:
        for line in req.lines.select_related("product").all():
            qty = line.quantity_outstanding
            if qty <= 0:
                continue
            bucket = merged.setdefault(
                line.product_id,
                {
                    "product": line.product,
                    "quantity": 0,
                    "price": line.estimated_unit_cost,
                    "req_line": line,
                },
            )
            bucket["quantity"] += qty
    if not merged:
        raise ProcurementError("Those requisitions have nothing left to order.")

    for bucket in merged.values():
        agreement = resolve_supplier_price(
            supplier=supplier,
            product=bucket["product"],
            quantity=bucket["quantity"],
            organization=organization,
        )
        PurchaseOrderLine.objects.create(
            order=order,
            product=bucket["product"],
            quantity_ordered=bucket["quantity"],
            unit_price=agreement.unit_price if agreement else bucket["price"],
            expected_delivery=expected_delivery,
            requisition_line=bucket["req_line"],
        )

    for req in requisitions:
        for line in req.lines.all():
            line.quantity_ordered = line.quantity_approved or line.quantity
            line.save(update_fields=["quantity_ordered"])
        req.status = PurchaseRequisition.Status.CONVERTED
        req.save(update_fields=["status", "updated_at"])

    record_audit(
        action="REQUISITION_CONSOLIDATE",
        user=user,
        organization=organization,
        entity_type="purchase_order",
        entity_id=str(order.pk),
        changes={
            "po_number": order.po_number,
            "requisitions": [r.requisition_number or r.pk for r in requisitions],
        },
    )
    return order


# ---------------------------------------------------------------------------
# RFQ & quotes
# ---------------------------------------------------------------------------


@transaction.atomic
def send_rfq(*, rfq: RequestForQuotation, user: User) -> RequestForQuotation:
    if rfq.status != RequestForQuotation.Status.DRAFT:
        raise ProcurementError("Only a draft RFQ can be sent.")
    if not rfq.lines.exists():
        raise ProcurementError("Add at least one line before sending the RFQ.")
    if not rfq.rfq_number:
        rfq.rfq_number = next_document_number(rfq.organization, NumberSequence.Kind.RFQ)
    rfq.status = RequestForQuotation.Status.SENT
    rfq.issued_on = rfq.issued_on or timezone.localdate()
    rfq.save(update_fields=["rfq_number", "status", "issued_on", "updated_at"])
    record_audit(
        action="RFQ_SENT",
        user=user,
        organization=rfq.organization,
        entity_type="rfq",
        entity_id=str(rfq.pk),
        changes={"number": rfq.rfq_number},
    )
    return rfq


def compare_quotes(rfq: RequestForQuotation) -> list[dict[str, Any]]:
    """Side-by-side comparison in base currency — the buyer's decision table."""
    rows: list[dict[str, Any]] = []
    quotes = list(rfq.quotes.select_related("supplier").prefetch_related("lines__product"))
    cheapest = min((qt.total_amount_base for qt in quotes), default=ZERO)
    for quote in quotes:
        profile = SupplierProfile.objects.filter(supplier=quote.supplier).first()
        total = quote.total_amount_base
        rows.append(
            {
                "quote_id": quote.pk,
                "supplier_id": quote.supplier_id,
                "supplier_name": quote.supplier.name,
                "status": quote.status,
                "currency": quote.currency,
                "goods_total": str(quote.goods_total),
                "total_amount": str(quote.total_amount),
                "total_amount_base": str(total),
                "delta_vs_best": str(_q(total - cheapest)) if cheapest else "0.00",
                "is_cheapest": bool(cheapest) and total == cheapest,
                "lead_time_days": quote.lead_time_days,
                "payment_terms_days": quote.payment_terms_days,
                "incoterm": quote.incoterm,
                "valid_until": quote.valid_until,
                "supplier_score": str(profile.overall_score) if profile else None,
                "supplier_standing": profile.standing if profile else None,
                "lines": [
                    {
                        "product_id": ln.product_id,
                        "product": str(ln.product),
                        "quantity": ln.quantity_offered,
                        "unit_price": str(ln.unit_price),
                        "line_total": str(ln.line_total),
                    }
                    for ln in quote.lines.all()
                ],
            }
        )
    rows.sort(key=lambda r: Decimal(r["total_amount_base"]))
    return rows


@transaction.atomic
def award_quote(*, quote: SupplierQuote, user: User) -> PurchaseOrder:
    """Award an RFQ to one supplier and raise the draft PO from their quote."""
    rfq = quote.rfq
    if rfq.status == RequestForQuotation.Status.AWARDED:
        raise ProcurementError("This RFQ has already been awarded.")
    if rfq.status == RequestForQuotation.Status.CANCELLED:
        raise ProcurementError("This RFQ was cancelled.")
    if not quote.lines.exists():
        raise ProcurementError("This quote has no priced lines to order from.")

    order = PurchaseOrder.objects.create(
        po_number=next_document_number(rfq.organization, NumberSequence.Kind.PURCHASE_ORDER),
        organization=rfq.organization,
        supplier=quote.supplier,
        currency=quote.currency,
        exchange_rate=quote.exchange_rate,
        incoterm=quote.incoterm,
        payment_terms_days=quote.payment_terms_days,
        freight_amount=quote.freight_amount,
        other_charges=quote.other_charges,
        discount_amount=quote.discount_amount,
        expected_delivery=(
            timezone.localdate() + timedelta(days=quote.lead_time_days)
            if quote.lead_time_days
            else None
        ),
        is_import=quote.currency != "RWF",
        requisition=rfq.requisition,
        quote=quote,
        supplier_reference=quote.quote_reference,
        notes=f"Awarded from {rfq.rfq_number} — {quote.supplier.name}",
        created_by=user,
    )
    for line in quote.lines.select_related("product").all():
        PurchaseOrderLine.objects.create(
            order=order,
            product=line.product,
            quantity_ordered=line.quantity_offered,
            unit_price=line.unit_price,
            expected_delivery=(
                timezone.localdate() + timedelta(days=line.lead_time_days)
                if line.lead_time_days
                else None
            ),
            notes=line.notes,
        )

    quote.status = SupplierQuote.Status.AWARDED
    quote.save(update_fields=["status"])
    rfq.quotes.exclude(pk=quote.pk).update(status=SupplierQuote.Status.DECLINED)
    rfq.status = RequestForQuotation.Status.AWARDED
    rfq.save(update_fields=["status", "updated_at"])

    record_audit(
        action="RFQ_AWARDED",
        user=user,
        organization=rfq.organization,
        entity_type="supplier_quote",
        entity_id=str(quote.pk),
        changes={"rfq": rfq.rfq_number, "supplier": quote.supplier.name, "po": order.po_number},
    )
    return order


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------


@transaction.atomic
def submit_order(*, order: PurchaseOrder, user: User) -> ApprovalRequest:
    """Raise a PO for approval. Supplier qualification is checked *here*, before
    an approver's time is wasted on an order we may not legally place."""
    if order.status != PurchaseOrder.Status.DRAFT:
        raise ProcurementError("Only a draft purchase order can be submitted for approval.")
    if not order.lines.exists():
        raise ProcurementError("Add at least one line before submitting the order.")
    assert_supplier_orderable(order.supplier)

    profile = SupplierProfile.objects.filter(supplier=order.supplier).first()
    if profile and profile.minimum_order_value and order.total_amount < profile.minimum_order_value:
        raise ProcurementError(
            f"Order total {order.total_amount} is below {order.supplier.name}'s "
            f"minimum order value of {profile.minimum_order_value}."
        )

    if not order.po_number:
        order.po_number = next_document_number(
            order.organization, NumberSequence.Kind.PURCHASE_ORDER
        )
    order.status = PurchaseOrder.Status.PENDING_APPROVAL
    order.submitted_at = timezone.now()
    order.save(update_fields=["po_number", "status", "submitted_at", "updated_at"])

    approval = request_approval(
        resource_type=RES_PURCHASE_ORDER,
        resource_id=str(order.pk),
        organization=order.organization,
        requested_by=user,
        payload={
            "po_number": order.po_number,
            "supplier": order.supplier.name,
            "currency": order.currency,
            "total_amount": str(order.total_amount),
            "total_amount_base": str(order.total_amount_base),
            "lines": order.lines.count(),
            "expected_delivery": str(order.expected_delivery or ""),
        },
        reason=f"Purchase order {order.po_number} — {order.supplier.name} "
        f"{order.currency} {order.total_amount}",
    )
    record_audit(
        action="PO_SUBMIT",
        user=user,
        organization=order.organization,
        entity_type="purchase_order",
        entity_id=str(order.pk),
        changes={"po_number": order.po_number, "total": str(order.total_amount)},
    )
    return approval


@registry.register(RES_PURCHASE_ORDER)
def _apply_order_approval(approval: ApprovalRequest) -> None:
    order = PurchaseOrder.objects.filter(pk=approval.resource_id).first()
    if order is None or order.status != PurchaseOrder.Status.PENDING_APPROVAL:
        return
    order.status = PurchaseOrder.Status.APPROVED
    order.approved_by = approval.decided_by
    order.approved_at = timezone.now()
    order.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

    # F1.3 — emit PurchaseOrderApproved on the bus (ADR-010). Inventory
    # planning / Reporting / Finance accruals all subscribe here.
    from apps.events.publishers import publish_purchase_order_approved

    publish_purchase_order_approved(
        po_id=order.pk,
        organization=order.organization,
        user=approval.decided_by,
        supplier_id=order.supplier_id,
        total_amount=order.total_amount,
    )


@transaction.atomic
def send_order(*, order: PurchaseOrder, user: User | None, method: str = "EMAIL") -> Document:
    """Issue the approved PO to the supplier and vault the signed PDF."""
    if order.status != PurchaseOrder.Status.APPROVED:
        raise ProcurementError("Only an approved purchase order can be sent to the supplier.")
    document = generate_document(
        organization=order.organization,
        doc_type=DocType.PURCHASE_ORDER,
        context={
            "buyer_name": order.organization.name,
            "buyer_phone": order.organization.phone,
            "seller_name": order.supplier.name,
            "seller_contact": getattr(order.supplier, "contact_person", ""),
            "seller_address": getattr(order.supplier, "address", ""),
            "seller_phone": getattr(order.supplier, "phone", ""),
            "seller_email": getattr(order.supplier, "email", ""),
            "deliver_to_name": order.deliver_to.name if order.deliver_to is not None else "",
            "deliver_to_address": order.delivery_address,
            "po_number": order.po_number,
            "order_date": order.order_date,
            "expected_delivery": order.expected_delivery,
            "payment_terms_days": order.payment_terms_days,
            "incoterm": order.incoterm,
            "currency": order.currency,
            "terms": order.terms,
            "notes": order.notes,
            "lines": [
                {
                    "name": f"{ln.product.generic_name} {ln.product.strength}".strip(),
                    "qty": normalise(ln.quantity_ordered),
                    # The unit the quantity is counted in, and what it comes to
                    # on the shelf. A supplier reading "10" needs to know it
                    # means ten cartons, and the buyer's stock controller needs
                    # to know that is 24,000 tablets.
                    "unit_label": (ln.unit.name or ln.unit.get_code_display()) if ln.unit else "",
                    "base_quantity": normalise(ln.quantity_ordered_base),
                    "base_unit": (
                        ln.product.base_unit.get_code_display().lower()
                        if ln.product.base_unit
                        else "units"
                    ),
                    "price": ln.unit_price,
                    "total": ln.line_total,
                }
                for ln in order.lines.select_related("product", "unit").all()
            ],
            "subtotal": order.subtotal,
            "tax_total": order.tax_total,
            "freight_amount": order.freight_amount,
            "other_charges": order.other_charges,
            "discount_amount": order.discount_amount,
            "total": order.total_amount,
        },
        reference_type="purchase_order",
        reference_id=str(order.pk),
        user=user,
    )
    order.status = PurchaseOrder.Status.SENT
    order.sent_at = timezone.now()
    order.sent_method = method
    order.save(update_fields=["status", "sent_at", "sent_method", "updated_at"])
    record_audit(
        action="PO_SENT",
        user=user,
        organization=order.organization,
        entity_type="purchase_order",
        entity_id=str(order.pk),
        changes={"po_number": order.po_number, "method": method, "document": document.doc_number},
    )
    return document


@transaction.atomic
def cancel_order(*, order: PurchaseOrder, user: User | None, reason: str) -> PurchaseOrder:
    if order.status in {PurchaseOrder.Status.CANCELLED, PurchaseOrder.Status.CLOSED}:
        raise ProcurementError("This order is already closed or cancelled.")
    if order.quantity_received > 0:
        raise ProcurementError(
            "Goods have already been received against this order — close it instead of cancelling."
        )
    if not reason.strip():
        raise ProcurementError("A cancellation reason is required.")
    order.status = PurchaseOrder.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancel_reason = reason
    order.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    record_audit(
        action="PO_CANCELLED",
        user=user,
        organization=order.organization,
        entity_type="purchase_order",
        entity_id=str(order.pk),
        changes={"po_number": order.po_number, "reason": reason},
    )
    return order


@transaction.atomic
def close_order(*, order: PurchaseOrder, user: User | None, reason: str = "") -> PurchaseOrder:
    """Close a short-delivered order: we accept we will not receive the balance."""
    if order.status not in PurchaseOrder.RECEIVABLE | {PurchaseOrder.Status.RECEIVED}:
        raise ProcurementError("Only a live purchase order can be closed.")
    order.status = PurchaseOrder.Status.CLOSED
    order.closed_at = timezone.now()
    if reason:
        order.notes = f"{order.notes}\nClosed: {reason}".strip()
    order.save(update_fields=["status", "closed_at", "notes", "updated_at"])
    record_audit(
        action="PO_CLOSED",
        user=user,
        organization=order.organization,
        entity_type="purchase_order",
        entity_id=str(order.pk),
        changes={"po_number": order.po_number, "reason": reason},
    )
    return order


def refresh_order_status(order: PurchaseOrder) -> PurchaseOrder:
    """Roll the order's status forward from what has actually been received."""
    if order.status in {
        PurchaseOrder.Status.CANCELLED,
        PurchaseOrder.Status.CLOSED,
        PurchaseOrder.Status.DRAFT,
        PurchaseOrder.Status.PENDING_APPROVAL,
    }:
        return order
    received = order.quantity_received
    if received == 0:
        return order
    new_status = (
        PurchaseOrder.Status.RECEIVED
        if order.is_fully_received
        else PurchaseOrder.Status.PARTIALLY_RECEIVED
    )
    if order.status != new_status:
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
    return order


# ---------------------------------------------------------------------------
# Imports & landed cost
# ---------------------------------------------------------------------------


@dataclass
class LandedCostAllocation:
    line: PurchaseOrderLine
    weight: Decimal
    allocated: Decimal
    landed_unit_cost: Decimal


@transaction.atomic
def allocate_landed_costs(
    *, consignment: ImportConsignment, user: User | None = None
) -> dict[str, Any]:
    """Spread duty/freight/insurance/clearing across the consignment's PO lines.

    Recoverable import VAT is excluded — it is reclaimed from RRA, so letting it
    inflate unit cost would overstate COGS and understate margin on every sale.
    The final line absorbs the rounding remainder so the allocation ties exactly
    to the pool.
    """
    orders = list(consignment.orders.prefetch_related("lines").all())
    lines = [ln for order in orders for ln in order.lines.all()]
    if not lines:
        raise ProcurementError(
            "Attach at least one purchase order with lines to this consignment first."
        )

    pool = consignment.landed_cost_total
    by_quantity = consignment.allocation_basis == "QUANTITY"
    weights: list[Decimal] = [
        (
            Decimal(ln.quantity_ordered)
            if by_quantity
            else _q(ln.line_subtotal * ln.order.exchange_rate)
        )
        for ln in lines
    ]
    total_weight = sum(weights, ZERO)
    if total_weight <= 0:
        raise ProcurementError("Cannot allocate landed cost across zero-value/zero-quantity lines.")

    allocations: list[LandedCostAllocation] = []
    running = ZERO
    for index, (line, weight) in enumerate(zip(lines, weights, strict=True)):
        if index == len(lines) - 1:
            share = _q(pool - running)  # last line takes the remainder
        else:
            share = _q(pool * weight / total_weight)
            running += share
        qty = Decimal(line.quantity_ordered or 1)
        landed_unit = _q(line.base_unit_cost + share / qty)
        line.landed_cost_allocated = share
        line.landed_unit_cost = landed_unit
        line.save(update_fields=["landed_cost_allocated", "landed_unit_cost"])
        allocations.append(LandedCostAllocation(line, weight, share, landed_unit))

    consignment.costs_allocated_at = timezone.now()
    if consignment.status in {
        ImportConsignment.Status.CLEARED,
        ImportConsignment.Status.AT_CUSTOMS,
        ImportConsignment.Status.ARRIVED,
    }:
        consignment.status = ImportConsignment.Status.LANDED
    consignment.save(update_fields=["costs_allocated_at", "status", "updated_at"])

    record_audit(
        action="LANDED_COST_ALLOCATED",
        user=user,
        organization=consignment.organization,
        entity_type="import_consignment",
        entity_id=str(consignment.pk),
        changes={
            "reference": consignment.reference,
            "pool": str(pool),
            "basis": consignment.allocation_basis,
            "lines": len(allocations),
        },
    )
    return {
        "consignment": consignment.reference,
        "basis": consignment.allocation_basis,
        "pool": str(pool),
        "recoverable_tax": str(consignment.recoverable_tax_total),
        "goods_value_base": str(consignment.goods_value_base),
        "uplift_pct": str(consignment.uplift_pct),
        "allocations": [
            {
                "order": a.line.order.po_number,
                "line_id": a.line.pk,
                "product": str(a.line.product),
                "quantity": a.line.quantity_ordered,
                "goods_unit_cost": str(a.line.base_unit_cost),
                "allocated": str(a.allocated),
                "landed_unit_cost": str(a.landed_unit_cost),
            }
            for a in allocations
        ],
    }


# ---------------------------------------------------------------------------
# Goods receipt
# ---------------------------------------------------------------------------


def _grni_account(organization: Organization) -> tuple[dict[str, Account], Account]:
    accounts = ensure_default_accounts(organization)
    grni, _ = Account.objects.get_or_create(
        organization=organization,
        code=GRNI_CODE,
        defaults={
            "name": "Goods Received Not Invoiced (GRNI)",
            "account_type": Account.Type.LIABILITY,
            "normal_balance": Account.Balance.CREDIT,
            "is_system": True,
        },
    )
    return accounts, grni


def _to_base(order_line: Any, quantity: Any) -> Decimal:
    """Restate a quantity stated in the order's trading unit as base units."""
    factor = Decimal(order_line.unit.factor_to_base) if order_line.unit_id else Decimal(1)
    return (Decimal(str(quantity)) * factor).quantize(Decimal("0.001"))


@transaction.atomic
def build_receipt_draft(
    *,
    order: PurchaseOrder,
    user: User,
    received_on: date | None = None,
    requires_qc: bool | None = None,
) -> GoodsReceipt:
    """Open a draft GRN pre-filled with everything still outstanding on the PO.

    The clerk then edits quantities and types in batch numbers and expiry dates —
    they never re-key the product list.
    """
    if not order.can_receive:
        raise ProcurementError(
            f"Purchase order {order} is {order.get_status_display().lower()} — "
            "goods can only be received against an approved or sent order."
        )
    outstanding = [
        ln for ln in order.lines.select_related("product") if ln.quantity_outstanding > 0
    ]
    if not outstanding:
        raise ProcurementError("Every line on this order has already been received.")

    needs_qc = (
        requires_qc
        if requires_qc is not None
        else any(
            ln.product.storage_condition != "AMBIENT" or ln.product.is_controlled_substance
            for ln in outstanding
        )
        or True  # GDP default: inbound goods are quarantined until QC releases them
    )
    receipt = GoodsReceipt.objects.create(
        grn_number=next_document_number(order.organization, NumberSequence.Kind.GOODS_RECEIPT),
        order=order,
        organization=cast(Any, order.destination),
        consignment=order.consignment,
        received_on=received_on or timezone.localdate(),
        requires_qc=needs_qc,
        received_by=user,
    )
    for line in outstanding:
        GoodsReceiptLine.objects.create(
            receipt=receipt,
            order_line=line,
            product=line.product,
            batch_number="",
            expiry_date=timezone.localdate() + timedelta(days=365),
            quantity_expected=line.quantity_outstanding,
            quantity_received=line.quantity_outstanding,
            unit_cost=line.effective_unit_cost,
        )
    return receipt


@transaction.atomic
def post_goods_receipt(*, receipt: GoodsReceipt, user: User) -> GoodsReceipt:
    """Book the delivery in: stock, quarantine/QC, PO progress, GRN document, GL.

    Over- and under-delivery are recorded rather than blocked — what physically
    arrived is the truth; the variance drives the 3-way match and any debit note.
    """
    if receipt.status != GoodsReceipt.Status.DRAFT:
        raise ProcurementError("This goods receipt has already been posted or cancelled.")
    order = receipt.order
    if not order.can_receive:
        raise ProcurementError(
            f"Purchase order {order} is {order.get_status_display().lower()} — "
            "it cannot be received."
        )
    lines = list(receipt.lines.select_related("product", "order_line"))
    if not lines:
        raise ProcurementError("Add at least one line before posting the receipt.")
    for line in lines:
        if line.quantity_received <= 0 and line.quantity_rejected <= 0:
            raise ProcurementError(f"Line for {line.product} has nothing received or rejected.")
        if line.quantity_received > 0 and not line.batch_number.strip():
            raise ProcurementError(
                f"A batch number is required for {line.product} (GDP traceability)."
            )
        if line.quantity_received > 0 and line.expiry_date <= timezone.localdate():
            raise ProcurementError(
                f"{line.product} batch {line.batch_number} is already expired "
                f"({line.expiry_date}) — refuse the delivery."
            )

    discrepancy = False
    for line in lines:
        if line.quantity_received > 0:
            unit_cost = line.unit_cost or line.order_line.effective_unit_cost
            # The delivery note counts what the supplier shipped — twenty
            # cartons — and the shelf counts tablets. Converting here, once, is
            # the whole point of the order line carrying a unit: putting the
            # carton count on the shelf understates stock by the pack factor,
            # and nothing downstream could ever detect it.
            received_base = _to_base(line.order_line, line.quantity_received)
            batch = receive_intake(
                organization=receipt.organization,
                product=line.product,
                batch_number=line.batch_number,
                expiry_date=line.expiry_date,
                quantity=received_base,
                manufacture_date=line.manufacture_date,
                wholesale_cost=unit_cost,
                storage_location=line.storage_location,
                user=user,
                reference_type="goods_receipt",
                reference_id=str(receipt.pk),
                source_supplier=order.supplier,
            )
            fields = ["updated_at"]
            if line.bin_location_id:
                batch.bin_location = line.bin_location
                fields.append("bin_location")
            if receipt.requires_qc:
                batch.status = InventoryBatch.Status.QUARANTINE
                fields.append("status")
                QualityCheck.objects.create(
                    batch=batch,
                    inspector=user,
                    status=QualityCheck.Status.PENDING_REVIEW,
                    temp_indicator_ok=receipt.cold_chain_intact,
                    visual_integrity_ok=receipt.packaging_intact,
                    inspection_notes=(
                        f"Inbound quarantine from {receipt.grn_number} "
                        f"(PO {order.po_number}, {order.supplier.name})."
                    ),
                )
            batch.save(update_fields=fields)
            line.batch = batch
            line.unit_cost = unit_cost
            line.save(update_fields=["batch", "unit_cost"])

        order_line = line.order_line
        order_line.quantity_received += line.quantity_received
        order_line.quantity_rejected += line.quantity_rejected
        order_line.save(update_fields=["quantity_received", "quantity_rejected"])
        if line.variance != 0 or line.quantity_rejected:
            discrepancy = True

    receipt.has_discrepancy = discrepancy
    receipt.status = GoodsReceipt.Status.POSTED
    receipt.posted_by = user
    receipt.posted_at = timezone.now()
    receipt.save(
        update_fields=["has_discrepancy", "status", "posted_by", "posted_at", "updated_at"]
    )

    refresh_order_status(order)
    _settle_retail_demand(receipt)
    _generate_grn_document(receipt, user)
    _post_receipt_journal(receipt, user)

    # F1.3 — emit GoodsReceivedNotePosted on the bus (ADR-010). AP matching /
    # stock-value recompute / Reporting all subscribe here. The journal and
    # event are atomic — both succeed or both roll back.
    from apps.events.publishers import publish_goods_received_note_posted

    publish_goods_received_note_posted(
        grn_id=receipt.pk,
        organization=receipt.organization,
        user=user,
        po_id=order.pk,
        total_value_base=receipt.goods_value_base,
    )

    record_audit(
        action="GRN_POSTED",
        user=user,
        organization=receipt.organization,
        entity_type="goods_receipt",
        entity_id=str(receipt.pk),
        changes={
            "grn_number": receipt.grn_number,
            "po_number": order.po_number,
            "received": receipt.total_received,
            "rejected": receipt.total_rejected,
            "quarantined": receipt.requires_qc,
            "value": str(receipt.goods_value_base),
        },
    )
    return receipt


def _settle_retail_demand(receipt: GoodsReceipt) -> None:
    """Close the retail backorders this delivery was imported to satisfy.

    The demand loop only pays for itself if it closes. A pharmacy's unmet request
    becomes a requisition, the requisition becomes an import, and the import lands
    here — at which point the people who have been waiting are, in fact, no longer
    waiting. Leaving the backorders open would keep re-proposing an import that has
    already arrived.

    Quantities are settled oldest-request-first against what physically landed, so
    a partial delivery closes the front of the queue rather than a little of
    everybody's.
    """
    from apps.distribution.demand import settle_backorders_for

    for line in receipt.lines.select_related("product").all():
        if line.quantity_received > 0:
            settle_backorders_for(
                depot=receipt.organization_id,
                product=line.product_id,
                quantity=line.quantity_received,
            )


def _generate_grn_document(receipt: GoodsReceipt, user: User | None) -> Document:
    return generate_document(
        organization=receipt.organization,
        doc_type=DocType.GRN,
        context={
            "retail_name": receipt.organization.name,
            "depot_name": receipt.order.supplier.name,
            "has_discrepancy": receipt.has_discrepancy,
            "lines": [
                {
                    "name": f"{ln.product.generic_name} {ln.product.strength}".strip(),
                    "batch": ln.batch_number,
                    "expiry": ln.expiry_date,
                    "expected": ln.quantity_expected,
                    "received": ln.quantity_received,
                    "damaged": ln.quantity_rejected,
                }
                for ln in receipt.lines.select_related("product").all()
            ],
        },
        reference_type="goods_receipt",
        reference_id=str(receipt.pk),
        user=user,
    )


def _post_receipt_journal(receipt: GoodsReceipt, user: User | None) -> None:
    """Dr Inventory / Cr GRNI — stock is on the shelf, the invoice is not here yet."""
    value = receipt.goods_value_base
    if value <= 0:
        return
    accounts, grni = _grni_account(receipt.organization)
    post_journal(
        organization=receipt.organization,
        entry_date=receipt.received_on,
        description=f"Goods received {receipt.grn_number} — {receipt.order.supplier.name}",
        lines=[
            {
                "account": accounts["1500"],  # 1500 Inventory on Hand (1200 is Bank)
                "side": JournalLine.Side.DEBIT,
                "amount": value,
                "memo": f"PO {receipt.order.po_number}",
            },
            {
                "account": grni,
                "side": JournalLine.Side.CREDIT,
                "amount": value,
                "memo": "Goods received not invoiced",
            },
        ],
        reference_type="goods_receipt",
        reference_id=str(receipt.pk),
        user=user,
    )


# ---------------------------------------------------------------------------
# Supplier invoices — 3-way match
# ---------------------------------------------------------------------------


def _received_quantity_for(order_line: PurchaseOrderLine, receipt: GoodsReceipt | None) -> Decimal:
    """Quantity to match against: this receipt's if one is linked, else the PO's total."""
    if receipt is not None:
        return Decimal(
            sum(
                ln.quantity_received
                for ln in receipt.lines.all()
                if ln.order_line_id == order_line.pk
            )
        )
    return Decimal(order_line.quantity_received)


@transaction.atomic
def run_three_way_match(*, invoice: SupplierInvoice, user: User | None = None) -> SupplierInvoice:
    """Reconcile invoice ↔ PO (price) ↔ GRN (quantity), line by line.

    Tolerances are per-invoice so a buyer can accept, say, a 1% price drift on an
    import without an override; anything outside them is a variance and blocks
    approval until someone senior owns it.
    """
    if invoice.order_id is None:
        invoice.match_result = SupplierInvoice.MatchResult.NO_RECEIPT
        invoice.match_detail = [
            {
                "line": None,
                "issue": "NO_ORDER",
                "message": "Invoice is not linked to a purchase order — nothing to match.",
            }
        ]
        invoice.status = SupplierInvoice.Status.VARIANCE
        invoice.matched_at = timezone.now()
        invoice.matched_by = user
        invoice.save(
            update_fields=[
                "match_result",
                "match_detail",
                "status",
                "matched_at",
                "matched_by",
                "updated_at",
            ]
        )
        return invoice

    receipt = invoice.receipt
    if receipt is not None:
        receipt.lines.all()  # warm the prefetch used by _received_quantity_for

    detail: list[dict[str, Any]] = []
    qty_variance = price_variance = False
    invoice_order = invoice.order
    has_receipt = bool(
        receipt
        or (
            invoice_order is not None
            and invoice_order.receipts.filter(status=GoodsReceipt.Status.POSTED).exists()
        )
    )

    for line in invoice.lines.select_related("order_line", "product").all():
        order_line = line.order_line
        if order_line is None:
            price_variance = True
            detail.append(
                {
                    "line": line.pk,
                    "product": str(line.product or line.description),
                    "issue": "UNMATCHED_LINE",
                    "message": "Invoice line is not linked to any purchase-order line.",
                }
            )
            continue

        received = _received_quantity_for(order_line, receipt)
        entry: dict[str, Any] = {
            "line": line.pk,
            "product": str(line.product or order_line.product),
            # Quantities read as a person would write them: 60, not 60.000. The
            # trailing zeros are storage precision, and on a variance report they
            # invite the reader to look for a fraction that was never there.
            "invoiced_qty": normalise(line.quantity),
            "received_qty": normalise(received),
            "ordered_qty": normalise(order_line.quantity_ordered),
            "invoiced_price": str(line.net_unit_price),
            "order_price": str(order_line.net_unit_price),
            "issue": "OK",
            "message": "Matched.",
        }

        qty_tol = received * invoice.qty_tolerance_pct / Decimal("100")
        if abs(line.quantity - received) > qty_tol:
            qty_variance = True
            entry["issue"] = "QTY"
            entry["message"] = (
                f"Invoiced {line.quantity} but {received} were received"
                f"{' (no goods receipt posted)' if not has_receipt else ''}."
            )

        order_price = order_line.net_unit_price
        price_tol = order_price * invoice.price_tolerance_pct / Decimal("100")
        if abs(line.net_unit_price - order_price) > price_tol:
            price_variance = True
            entry["issue"] = "PRICE" if entry["issue"] == "OK" else "QTY_AND_PRICE"
            entry["message"] = (
                f"{entry['message'] if entry['issue'] == 'QTY_AND_PRICE' else ''} "
                f"Invoiced at {line.net_unit_price}, ordered at {order_price}."
            ).strip()

        detail.append(entry)

    if not detail:
        raise ProcurementError("Add at least one invoice line before matching.")

    if not has_receipt:
        result = SupplierInvoice.MatchResult.NO_RECEIPT
    elif qty_variance and price_variance:
        result = SupplierInvoice.MatchResult.QTY_AND_PRICE
    elif qty_variance:
        result = SupplierInvoice.MatchResult.QTY_VARIANCE
    elif price_variance:
        result = SupplierInvoice.MatchResult.PRICE_VARIANCE
    else:
        result = SupplierInvoice.MatchResult.MATCHED

    invoice.match_result = result
    invoice.match_detail = detail
    invoice.matched_at = timezone.now()
    invoice.matched_by = user
    invoice.status = (
        SupplierInvoice.Status.MATCHED
        if result == SupplierInvoice.MatchResult.MATCHED
        else SupplierInvoice.Status.VARIANCE
    )
    invoice.save(
        update_fields=[
            "match_result",
            "match_detail",
            "matched_at",
            "matched_by",
            "status",
            "updated_at",
        ]
    )
    return invoice


@transaction.atomic
def submit_invoice(
    *, invoice: SupplierInvoice, user: User, override_reason: str = ""
) -> ApprovalRequest:
    """Send a matched (or explicitly overridden) invoice for approval."""
    if invoice.status not in {
        SupplierInvoice.Status.DRAFT,
        SupplierInvoice.Status.MATCHED,
        SupplierInvoice.Status.VARIANCE,
    }:
        raise ProcurementError("This invoice is not in a state that can be submitted.")
    if not invoice.lines.exists():
        raise ProcurementError("Add at least one line before submitting the invoice.")
    if invoice.match_result == SupplierInvoice.MatchResult.NOT_RUN:
        run_three_way_match(invoice=invoice, user=user)
        invoice.refresh_from_db()
    if invoice.has_variance and not override_reason.strip():
        raise ProcurementError(
            "The 3-way match found a variance — an override reason is required to submit "
            "this invoice for approval."
        )
    if not invoice.internal_number:
        invoice.internal_number = next_document_number(
            invoice.organization, NumberSequence.Kind.SUPPLIER_INVOICE
        )
    invoice.override_reason = override_reason
    invoice.status = SupplierInvoice.Status.PENDING_APPROVAL
    invoice.save(update_fields=["internal_number", "override_reason", "status", "updated_at"])

    approval = request_approval(
        resource_type=RES_SUPPLIER_INVOICE,
        resource_id=str(invoice.pk),
        organization=invoice.organization,
        requested_by=user,
        payload={
            "invoice_number": invoice.invoice_number,
            "supplier": invoice.supplier.name,
            "currency": invoice.currency,
            "total_amount": str(invoice.total_amount),
            "total_amount_base": str(invoice.total_amount_base),
            "match_result": invoice.match_result,
            "override_reason": override_reason,
            "po_number": invoice.order.po_number if invoice.order else None,
        },
        reason=(
            f"Supplier invoice {invoice.invoice_number} — {invoice.supplier.name} "
            f"({invoice.get_match_result_display()})"
        ),
    )
    record_audit(
        action="SUPPLIER_INVOICE_SUBMIT",
        user=user,
        organization=invoice.organization,
        entity_type="supplier_invoice",
        entity_id=str(invoice.pk),
        changes={"invoice": invoice.invoice_number, "match": invoice.match_result},
    )
    return approval


@registry.register(RES_SUPPLIER_INVOICE)
def _apply_invoice_approval(approval: ApprovalRequest) -> None:
    invoice = SupplierInvoice.objects.filter(pk=approval.resource_id).first()
    if invoice is None or invoice.status != SupplierInvoice.Status.PENDING_APPROVAL:
        return
    post_supplier_invoice(invoice=invoice, user=approval.decided_by)


@transaction.atomic
def post_supplier_invoice(*, invoice: SupplierInvoice, user: User | None) -> SupplierInvoice:
    """Recognise the payable: create the finance bill and post the purchase journal."""
    if invoice.finance_bill_id:
        return invoice

    total = invoice.total_amount_base
    tax = _q(invoice.tax_total * invoice.exchange_rate)
    net = _q(total - tax)
    due = invoice.due_date or (
        invoice.invoice_date
        + timedelta(days=invoice.order.payment_terms_days if invoice.order else 30)
    )

    bill = SupplierBill.objects.create(
        organization=invoice.organization,
        supplier=invoice.supplier,
        bill_number=invoice.invoice_number,
        bill_date=invoice.invoice_date,
        due_date=due,
        total_amount=total,
        vat_amount=tax,
        tax_class=invoice.tax_class,
        reference_type="procurement.supplier_invoice",
        reference_id=str(invoice.pk),
        notes=invoice.notes,
        created_by=user,
    )

    accounts, grni = _grni_account(invoice.organization)
    receipt = invoice.receipt
    goods_received_value = receipt.goods_value_base if receipt else ZERO
    if goods_received_value > net:
        goods_received_value = net
    variance = _q(net - goods_received_value)

    lines: list[dict[str, Any]] = []
    if goods_received_value > 0:
        lines.append(
            {
                "account": grni,
                "side": JournalLine.Side.DEBIT,
                "amount": goods_received_value,
                "memo": f"Clears GRNI for {receipt.grn_number}" if receipt else "Clears GRNI",
            }
        )
    if variance > 0:
        lines.append(
            {
                "account": accounts["5000"],
                "side": JournalLine.Side.DEBIT,
                "amount": variance,
                "memo": "Purchase price / uninvoiced-goods variance",
            }
        )
    elif variance < 0:
        lines.append(
            {
                "account": accounts["5000"],
                "side": JournalLine.Side.CREDIT,
                "amount": -variance,
                "memo": "Purchase price variance (credit)",
            }
        )
    if tax > 0:
        lines.append(
            {
                "account": accounts["1350"],
                "side": JournalLine.Side.DEBIT,
                "amount": tax,
                "memo": f"VAT input (class {invoice.tax_class or '?'})",
            }
        )
    lines.append(
        {
            "account": accounts["2100"],
            "side": JournalLine.Side.CREDIT,
            "amount": total,
            "memo": f"Payable to {invoice.supplier.name}",
        }
    )
    post_journal(
        organization=invoice.organization,
        entry_date=invoice.invoice_date,
        description=f"Supplier invoice {invoice.invoice_number} — {invoice.supplier.name}",
        lines=cast(list[JournalLineInput], lines),
        reference_type="supplier_invoice",
        reference_id=str(invoice.pk),
        user=user,
    )

    for line in invoice.lines.select_related("order_line").all():
        order_line = line.order_line
        if order_line is not None:
            order_line.quantity_invoiced += int(line.quantity)
            order_line.save(update_fields=["quantity_invoiced"])

    invoice.finance_bill = bill
    invoice.status = SupplierInvoice.Status.APPROVED
    invoice.approved_by = user
    invoice.approved_at = timezone.now()
    invoice.save(
        update_fields=["finance_bill", "status", "approved_by", "approved_at", "updated_at"]
    )
    record_audit(
        action="SUPPLIER_INVOICE_APPROVED",
        user=user,
        organization=invoice.organization,
        entity_type="supplier_invoice",
        entity_id=str(invoice.pk),
        changes={
            "invoice": invoice.invoice_number,
            "bill_id": bill.pk,
            "total": str(total),
            "match": invoice.match_result,
            "override_reason": invoice.override_reason,
        },
    )
    return invoice


# ---------------------------------------------------------------------------
# Debit / credit notes & statements
# ---------------------------------------------------------------------------


@transaction.atomic
def issue_supplier_note(*, note: SupplierNote, user: User | None) -> SupplierNote:
    """Issue a debit/credit note: reduce the payable and reverse the cost."""
    if note.status != SupplierNote.Status.DRAFT:
        raise ProcurementError("Only a draft note can be issued.")
    if note.amount <= 0:
        raise ProcurementError("A note amount must be positive.")
    kind = SupplierNote.Kind(note.kind)
    if not note.note_number:
        note.note_number = next_document_number(
            note.organization,
            (
                NumberSequence.Kind.DEBIT_NOTE
                if kind == SupplierNote.Kind.DEBIT
                else NumberSequence.Kind.CREDIT_NOTE
            ),
        )
    note.status = SupplierNote.Status.ISSUED
    note.save(update_fields=["note_number", "status", "updated_at"])

    amount = note.total_amount
    accounts = ensure_default_accounts(note.organization)
    post_journal(
        organization=note.organization,
        entry_date=note.note_date,
        description=f"{note.get_kind_display()} {note.note_number} — {note.supplier.name}",
        lines=[
            {
                "account": accounts["2100"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": note.get_reason_display(),
            },
            {
                "account": accounts["5000"],
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": note.description[:200],
            },
        ],
        reference_type="supplier_note",
        reference_id=str(note.pk),
        user=user,
    )

    # Keep the payable honest: a note reduces what is actually owed on the bill.
    invoice = note.invoice
    bill = invoice.finance_bill if invoice is not None else None
    if bill is not None:
        bill.total_amount = max(Decimal("0.00"), _q(bill.total_amount - amount))
        if bill.amount_paid >= bill.total_amount:
            bill.status = SupplierBill.Status.PAID
        elif bill.amount_paid > 0:
            bill.status = SupplierBill.Status.PARTIAL
        bill.save(update_fields=["total_amount", "status", "updated_at"])

    record_audit(
        action="SUPPLIER_NOTE_ISSUED",
        user=user,
        organization=note.organization,
        entity_type="supplier_note",
        entity_id=str(note.pk),
        changes={"number": note.note_number, "kind": note.kind, "amount": str(amount)},
    )
    return note


def supplier_statement(
    *,
    organization: Organization,
    supplier: Any,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    """A reconcilable statement of account for one supplier.

    Invoices increase the balance; notes and payments reduce it. The closing
    balance is what we should agree with the supplier's own ledger.
    """
    invoices = (
        SupplierInvoice.objects.filter(
            organization=organization,
            supplier=supplier,
            status=SupplierInvoice.Status.APPROVED,
            invoice_date__gte=date_from,
            invoice_date__lte=date_to,
        )
        .select_related("finance_bill", "order")
        .order_by("invoice_date", "pk")
    )
    notes = SupplierNote.objects.filter(
        organization=organization,
        supplier=supplier,
        status__in=[SupplierNote.Status.ISSUED, SupplierNote.Status.SETTLED],
        note_date__gte=date_from,
        note_date__lte=date_to,
    ).order_by("note_date", "pk")
    bills = SupplierBill.objects.filter(
        organization=organization, supplier=supplier
    ).prefetch_related("payments")

    entries: list[dict[str, Any]] = []
    for invoice in invoices:
        entries.append(
            {
                "date": invoice.invoice_date,
                "type": "INVOICE",
                "reference": invoice.invoice_number,
                "description": f"PO {invoice.order.po_number}" if invoice.order else "Invoice",
                "debit": ZERO,
                "credit": invoice.total_amount_base,
            }
        )
    for note in notes:
        entries.append(
            {
                "date": note.note_date,
                "type": note.kind,
                "reference": note.note_number,
                "description": note.get_reason_display(),
                "debit": note.total_amount,
                "credit": ZERO,
            }
        )
    for bill in bills:
        for payment in bill.payments.all():
            paid_on = payment.paid_at.date()
            if date_from <= paid_on <= date_to:
                entries.append(
                    {
                        "date": paid_on,
                        "type": "PAYMENT",
                        "reference": payment.reference or bill.bill_number,
                        "description": payment.get_method_display(),
                        "debit": payment.amount,
                        "credit": ZERO,
                    }
                )
    entries.sort(key=lambda e: (e["date"], e["type"]))

    balance = ZERO
    rows: list[dict[str, Any]] = []
    for entry in entries:
        balance += entry["credit"] - entry["debit"]
        rows.append(
            {
                **{k: v for k, v in entry.items() if k != "date"},
                "date": entry["date"],
                "debit": str(_q(entry["debit"])),
                "credit": str(_q(entry["credit"])),
                "balance": str(_q(balance)),
            }
        )

    outstanding = sum(
        (b.amount_due for b in bills if b.status != SupplierBill.Status.PAID), Decimal("0")
    )
    return {
        "supplier_id": supplier.pk,
        "supplier_name": supplier.name,
        "organization_id": organization.pk,
        "date_from": date_from,
        "date_to": date_to,
        "entries": rows,
        "closing_balance": str(_q(balance)),
        "total_outstanding": str(_q(Decimal(outstanding))),
    }


def open_purchase_orders(organizations: QuerySet[Organization]) -> QuerySet[PurchaseOrder]:
    """POs still awaiting goods — the buyer's follow-up list."""
    return PurchaseOrder.objects.filter(
        organization__in=organizations, status__in=list(PurchaseOrder.RECEIVABLE)
    ).select_related("supplier", "organization")
