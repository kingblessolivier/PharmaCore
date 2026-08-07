"""Generating finance documents.

One endpoint per document rather than a generic "render anything" route: each
document needs a different source record and a different set of guards, and a
single polymorphic endpoint would hide that behind a `type` string.

Generation is idempotent through the documents engine's reference pair, so asking
twice for the same statement returns the same numbered PDF instead of burning a
document number every time someone clicks.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.documents.serializers import DocumentSerializer
from apps.finance.documents import (
    credit_note_document,
    customer_invoice_document,
    customer_receipt_document,
    financial_statements_document,
    journal_voucher_document,
    payment_voucher_document,
    remittance_advice_document,
    statement_document,
    vat_return_document,
)
from apps.finance.models import (
    CustomerCredit,
    CustomerInvoice,
    CustomerReceipt,
    JournalEntry,
    PaymentRun,
    SupplierBillPayment,
)
from apps.finance.views import _date_param, _require_finance_manage, _resolve_org
from apps.iam.models import Organization, User
from apps.iam.scoping import organizations_visible_to


def _visible(user: User, organization: Organization) -> None:
    if not (
        user.is_superuser
        or user.has_role("SYS_ADMIN")
        or organization in organizations_visible_to(user)
    ):
        raise ValidationError("You may not generate documents for that organization.")


def _created(document: Any) -> Response:
    return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


def _lookup(model: Any, pk: Any, label: str) -> Any:
    record = model.objects.filter(pk=pk).first() if pk else None
    if record is None:
        raise ValidationError(f"A valid '{label}' is required.")
    return record


class FinanceDocumentsView(viewsets.ViewSet):
    """Turn finance records into numbered, hashed, QR-verified PDFs."""

    @action(detail=False, methods=["post"], url_path="invoice")
    def invoice(self, request: Request) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        invoice = _lookup(CustomerInvoice, request.data.get("invoice"), "invoice")
        _visible(user, invoice.organization)
        return _created(customer_invoice_document(invoice=invoice, user=user))

    @action(detail=False, methods=["post"], url_path="receipt")
    def receipt(self, request: Request) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        receipt = _lookup(CustomerReceipt, request.data.get("receipt"), "receipt")
        _visible(user, receipt.invoice.organization)
        return _created(customer_receipt_document(receipt=receipt, user=user))

    @action(detail=False, methods=["post"], url_path="credit-note")
    def credit_note(self, request: Request) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        credit = _lookup(CustomerCredit, request.data.get("credit"), "credit")
        _visible(user, credit.organization)
        return _created(credit_note_document(credit=credit, user=user))

    @action(detail=False, methods=["post"], url_path="statement")
    def statement(self, request: Request) -> Response:
        """The statement of account — what a customer disputing a balance needs."""
        user = cast(User, request.user)
        _require_finance_manage(user)
        organization = _resolve_org(request, user)
        customer = _lookup(Organization, request.data.get("customer"), "customer")
        try:
            start = date.fromisoformat(str(request.data["start"]))
            end = date.fromisoformat(str(request.data["end"]))
        except (KeyError, ValueError) as exc:
            raise ValidationError("'start' and 'end' must be ISO dates.") from exc
        return _created(
            statement_document(
                organization=organization, customer=customer, start=start, end=end, user=user
            )
        )

    @action(detail=False, methods=["post"], url_path="remittance-advice")
    def remittance_advice(self, request: Request) -> Response:
        """Tell a supplier which invoices a bulk payment settled."""
        user = cast(User, request.user)
        _require_finance_manage(user)
        run = _lookup(PaymentRun, request.data.get("run"), "run")
        _visible(user, run.organization)
        supplier = None
        if request.data.get("supplier"):
            supplier = run.lines.filter(bill__supplier_id=request.data["supplier"]).first()
            supplier = supplier.bill.supplier if supplier else None
        return _created(remittance_advice_document(run=run, supplier=supplier, user=user))

    @action(detail=False, methods=["post"], url_path="payment-voucher")
    def payment_voucher(self, request: Request) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        payment = _lookup(SupplierBillPayment, request.data.get("payment"), "payment")
        _visible(user, payment.bill.organization)
        return _created(payment_voucher_document(payment=payment, user=user))

    @action(detail=False, methods=["post"], url_path="journal-voucher")
    def journal_voucher(self, request: Request) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        entry = _lookup(JournalEntry, request.data.get("entry"), "entry")
        _visible(user, entry.organization)
        return _created(journal_voucher_document(entry=entry, user=user))

    @action(detail=False, methods=["post"], url_path="financial-statements")
    def financial_statements(self, request: Request) -> Response:
        """P&L, balance sheet and trial balance as one filed pack."""
        user = cast(User, request.user)
        _require_finance_manage(user)
        organization = _resolve_org(request, user)
        start, end = _period(request)
        return _created(
            financial_statements_document(
                organization=organization, start=start, end=end, user=user
            )
        )

    @action(detail=False, methods=["post"], url_path="vat-return")
    def vat_return(self, request: Request) -> Response:
        """The filed copy — a CSV draft proves nothing after the fact."""
        user = cast(User, request.user)
        _require_finance_manage(user)
        organization = _resolve_org(request, user)
        start, end = _period(request)
        return _created(
            vat_return_document(organization=organization, start=start, end=end, user=user)
        )


def _period(request: Request) -> tuple[date, date]:
    from django.utils import timezone

    today = timezone.localdate()
    first = today.replace(day=1)
    return _date_param(request, "start", first), _date_param(request, "end", today)
