"""Helper that hooks :func:`apps.events.outbox.publish` into the existing
business actions across modules.

Each helper writes its event inside the **caller's transaction** via
``transaction.on_commit`` — so the journal / doc / status update and its
event are atomic together.

Why a separate module instead of Django signals: signals are easy to forget
and hard to grep for. Keeping the publish calls in named helpers (called
from the service methods that already do the work) makes the contract
explicit and the audit trail obvious.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.events.events import EventType
from apps.events.outbox import publish
from apps.iam.models import Organization, User


def publish_sale_finalised(
    *,
    sale_id: int | str,
    organization: Organization,
    user: User | None,
    payload: dict[str, Any] | None = None,
) -> None:
    body = {
        "sale_id": str(sale_id),
        "total": payload.get("total") if payload else None,
        "payment_status": payload.get("payment_status") if payload else None,
        "branch_id": payload.get("branch_id") if payload else None,
    }
    publish(
        event_type=EventType.SALE_FINALISED,
        payload=body,
        source_doc_type="retail.Sale",
        source_doc_id=sale_id,
        organization_id=organization.pk,
        user=user,
    )


def publish_purchase_order_approved(
    *,
    po_id: int | str,
    organization: Organization,
    user: User | None,
    supplier_id: int | str | None = None,
    total_amount: Decimal | None = None,
) -> None:
    publish(
        event_type=EventType.PURCHASE_ORDER_APPROVED,
        payload={
            "po_id": str(po_id),
            "supplier_id": str(supplier_id) if supplier_id else None,
            "total_amount": str(total_amount) if total_amount is not None else None,
        },
        source_doc_type="procurement.PurchaseOrder",
        source_doc_id=po_id,
        organization_id=organization.pk,
        user=user,
    )


def publish_goods_received_note_posted(
    *,
    grn_id: int | str,
    organization: Organization,
    user: User | None,
    po_id: int | str | None = None,
    total_value_base: Decimal | None = None,
) -> None:
    publish(
        event_type=EventType.GOODS_RECEIVED_NOTE_POSTED,
        payload={
            "grn_id": str(grn_id),
            "po_id": str(po_id) if po_id else None,
            "total_value_base": str(total_value_base) if total_value_base is not None else None,
        },
        source_doc_type="procurement.GoodsReceipt",
        source_doc_id=grn_id,
        organization_id=organization.pk,
        user=user,
    )


def publish_approval_requested(
    *,
    approval_id: int | str,
    organization: Organization,
    requested_by: User | None,
    resource_type: str,
    resource_id: int | str,
) -> None:
    publish(
        event_type=EventType.APPROVAL_REQUESTED,
        payload={
            "approval_id": str(approval_id),
            "resource_type": resource_type,
            "resource_id": str(resource_id),
        },
        source_doc_type="approvals.ApprovalRequest",
        source_doc_id=approval_id,
        organization_id=organization.pk,
        user=requested_by,
    )


def publish_approval_decided(
    *,
    approval_id: int | str,
    organization: Organization,
    user: User | None,
    approve: bool,
) -> None:
    event = EventType.APPROVAL_GRANTED if approve else EventType.APPROVAL_REJECTED
    publish(
        event_type=event,
        payload={"approval_id": str(approval_id), "decision": "approve" if approve else "reject"},
        source_doc_type="approvals.ApprovalRequest",
        source_doc_id=approval_id,
        organization_id=organization.pk,
        user=user,
    )


def publish_payroll_run_approved(
    *,
    payroll_run_id: int | str,
    organization: Organization,
    user: User | None,
    period: str,
    employee_count: int,
) -> None:
    publish(
        event_type=EventType.PAYROLL_RUN_APPROVED,
        payload={
            "payroll_run_id": str(payroll_run_id),
            "period": period,
            "employee_count": employee_count,
        },
        source_doc_type="hr.PayrollRun",
        source_doc_id=payroll_run_id,
        organization_id=organization.pk,
        user=user,
    )


def publish_fiscal_period_event(
    *,
    event: str,  # one of EventType.FISCAL_PERIOD_OPENED / FISCAL_PERIOD_CLOSED / PERIOD_REOPENED
    period_id: int | str,
    organization: Organization,
    user: User | None,
    kind: str,  # DAY / MONTH / YEAR
    start_date: str,
    end_date: str,
) -> None:
    publish(
        event_type=event,
        payload={
            "period_id": str(period_id),
            "kind": kind,
            "start_date": start_date,
            "end_date": end_date,
        },
        source_doc_type="finance.AccountingPeriod",
        source_doc_id=period_id,
        organization_id=organization.pk,
        user=user,
    )


def publish_inventory_adjusted(
    *,
    organization: Organization,
    user: User | None,
    batch_id: int | str,
    product_id: int | str | None,
    delta: int,
    amount: Decimal | None,
    reason: str,
    reference_type: str,
    reference_id: str,
) -> None:
    """An approved stock-count variance has been reconciled into the books.

    Emitted from the same call site that posts the journal leg so the
    downstream Reporting / Insights rebuild gets the same picture.
    """
    publish(
        event_type=EventType.INVENTORY_ADJUSTED,
        payload={
            "batch_id": str(batch_id),
            "product_id": str(product_id) if product_id else None,
            "delta": int(delta),
            "amount": str(amount) if amount is not None else None,
            "reason": reason,
            "reference_type": reference_type,
            "reference_id": str(reference_id),
        },
        source_doc_type=reference_type or "stock_count",
        source_doc_id=reference_id,
        organization_id=organization.pk,
        user=user,
    )


def publish_stock_disposed(
    *,
    organization: Organization,
    user: User | None,
    batch_id: int | str,
    product_id: int | str | None,
    quantity: int,
    amount: Decimal | None,
    reason: str,
    reference_type: str,
    reference_id: str,
) -> None:
    """Wastage / destruction / recall-driven writeoff posted to the GL."""
    publish(
        event_type=EventType.STOCK_DISPOSED,
        payload={
            "batch_id": str(batch_id),
            "product_id": str(product_id) if product_id else None,
            "quantity": int(quantity),
            "amount": str(amount) if amount is not None else None,
            "reason": reason,
            "reference_type": reference_type,
            "reference_id": str(reference_id),
        },
        source_doc_type=reference_type or "wastage",
        source_doc_id=reference_id,
        organization_id=organization.pk,
        user=user,
    )


def publish_statutory_payment_confirmed(
    *,
    organization: Organization,
    user: User | None,
    payment_id: int | str,
    amount: Decimal,
    period_start: str,
    period_end: str,
    rra_reference: str = "",
) -> None:
    """An RRA remittance (or other statutory liability payment) was applied
    successfully and posted Dr Statutory Payable / Cr Cash & Bank.
    """
    publish(
        event_type=EventType.STATUTORY_PAYMENT_CONFIRMED,
        payload={
            "payment_id": str(payment_id),
            "amount": str(amount),
            "period_start": period_start,
            "period_end": period_end,
            "rra_reference": rra_reference,
        },
        source_doc_type="finance.TaxPayment",
        source_doc_id=payment_id,
        organization_id=organization.pk,
        user=user,
    )
