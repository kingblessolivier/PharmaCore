"""Finance documents — the things a customer, supplier, auditor or bank is handed.

The documents engine (`apps/documents`) numbers a PDF, hashes it SHA-256, attaches
a QR verification token and stores it write-once. Retail, distribution and
procurement all used it. Finance — the most document-heavy function in the
business — called it zero times, so every finance output existed only as a screen.

That is not a cosmetic gap. A report you can look at is not the same as a document
you can send, file, and later prove was not altered:

* a customer disputing a balance needs a **statement**, not a screenshot;
* a supplier receiving a bulk payment needs a **remittance advice**, or they cannot
  tell which invoices were settled;
* a cash payment needs a **voucher** with a signature block, because that is the
  authorisation record an auditor asks for;
* a manual journal needs a **voucher** for the same reason — it is the one posting
  a human typed, and the one most worth being able to defend later.

Every function here is a thin adapter: gather the context the template needs, then
hand it to `generate_document`. The numbering, hashing and verification stay in one
place rather than being reimplemented per document.

All of them pass ``reuse_existing=True``: a statement for a period, or a voucher
for a payment, *is* the record for that thing, so asking twice must return the
same numbered PDF rather than issuing a second original.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.documents import invoicing
from apps.documents.models import DocType, Document
from apps.documents.services import generate_document
from apps.iam.models import Organization, User

from .models import (
    CustomerCredit,
    CustomerInvoice,
    CustomerReceipt,
    JournalEntry,
    JournalLine,
    PaymentRun,
    SupplierBillPayment,
)

ZERO = Decimal("0.00")

_UNITS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "  twenty thirty forty fifty sixty seventy eighty ninety".split(" ")


def amount_in_words(amount: Decimal | int | float, currency: str = "Rwandan francs") -> str:
    """Spell an amount out.

    A voucher carries the figure in words because that is the line that cannot be
    altered with a pen after it has been signed.
    """

    def under_thousand(n: int) -> str:
        if n < 20:
            return _UNITS[n]
        if n < 100:
            return _TENS[n // 10] + ("-" + _UNITS[n % 10] if n % 10 else "")
        return (
            _UNITS[n // 100] + " hundred" + (" and " + under_thousand(n % 100) if n % 100 else "")
        )

    value = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    whole = int(value)
    cents = int((value - whole) * 100)

    if whole == 0:
        words = "zero"
    else:
        parts: list[str] = []
        for scale, name in (
            (1_000_000_000, "billion"),
            (1_000_000, "million"),
            (1_000, "thousand"),
        ):
            if whole >= scale:
                parts.append(f"{under_thousand(whole // scale)} {name}")
                whole %= scale
        if whole:
            parts.append(under_thousand(whole))
        words = " ".join(parts)

    text = f"{words} {currency}"
    if cents:
        text += f" and {under_thousand(cents)} cents"
    return text[0].upper() + text[1:]


def _ledger_lines(entry: JournalEntry | None) -> list[dict[str, str]]:
    if entry is None:
        return []
    return [
        {
            "account": f"{line.account.code} {line.account.name}",
            "cost_centre": line.cost_centre.code if line.cost_centre else "—",
            "memo": line.memo,
            "debit": str(line.amount) if line.side == JournalLine.Side.DEBIT else "",
            "credit": str(line.amount) if line.side == JournalLine.Side.CREDIT else "",
        }
        for line in entry.lines.select_related("account", "cost_centre")
    ]


def _entry_for(organization: Organization, reference_type: str, reference_id: Any) -> Any:
    return JournalEntry.objects.filter(
        organization=organization, reference_type=reference_type, reference_id=str(reference_id)
    ).first()


# --------------------------------------------------------------------------- #
# Customer-facing
# --------------------------------------------------------------------------- #


@transaction.atomic
def customer_invoice_document(*, invoice: CustomerInvoice, user: User | None = None) -> Document:
    """The tax invoice the customer is actually sent."""
    net = invoice.total_amount - invoice.vat_amount
    return generate_document(
        organization=invoice.organization,
        doc_type=DocType.TAX_INVOICE,
        reference_type="customer_invoice",
        reference_id=str(invoice.pk),
        user=user,
        reuse_existing=True,
        context=invoicing.invoice_context(
            seller=invoice.organization,
            buyer=invoice.customer,
            lines=[
                {
                    "name": invoice.notes or "Goods supplied",
                    "tax_class": "B",
                    "tax_amount": invoice.vat_amount,
                    "net": net,
                    "qty": 1,
                    "unit_label": "",
                    "price": invoicing.money(net),
                    "total": invoicing.money(net),
                }
            ],
            subtotal=net,
            tax_total=invoice.vat_amount,
            total=invoice.total_amount,
            currency=invoice.organization.currency or "RWF",
            invoice_number=invoice.invoice_number,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            payment_terms=(f"Payable by {invoice.due_date:%d %b %Y}." if invoice.due_date else ""),
        ),
    )


@transaction.atomic
def customer_receipt_document(*, receipt: CustomerReceipt, user: User | None = None) -> Document:
    """Proof the customer paid — the thing they file against their own records."""
    invoice = receipt.invoice
    return generate_document(
        organization=invoice.organization,
        doc_type=DocType.RECEIPT,
        reference_type="customer_receipt",
        reference_id=str(receipt.pk),
        user=user,
        reuse_existing=True,
        context={
            "seller_name": invoice.organization.name,
            "sale_number": f"{receipt.receipt_number} against {invoice.invoice_number}",
            "cashier": receipt.created_by.get_full_name() if receipt.created_by else "",
            "lines": [
                {
                    "name": f"Payment against {invoice.invoice_number}",
                    "tax_class": "—",
                    "qty": 1,
                    "price": str(receipt.amount),
                    "total": str(receipt.amount),
                }
            ],
            "subtotal": str(receipt.amount),
            "tax_total": "0.00",
            "total": str(receipt.amount),
            "tendered": str(receipt.amount),
            "change": "0.00",
        },
    )


@transaction.atomic
def credit_note_document(*, credit: CustomerCredit, user: User | None = None) -> Document:
    """A credit note reduces what the customer owes, and they need it in writing."""
    return generate_document(
        organization=credit.organization,
        doc_type=DocType.CREDIT_NOTE,
        reference_type="customer_credit",
        reference_id=str(credit.pk),
        user=user,
        reuse_existing=True,
        context={
            "buyer_name": credit.customer.name,
            "seller_name": credit.organization.name,
            "reason": credit.notes or credit.get_source_display(),
            "lines": [
                {
                    "description": credit.notes or credit.get_source_display(),
                    "amount": str(credit.amount),
                }
            ],
            "subtotal": str(credit.amount),
            "tax_total": "0.00",
            "total": str(credit.amount),
        },
    )


@transaction.atomic
def statement_document(
    *,
    organization: Organization,
    customer: Organization,
    start: date,
    end: date,
    user: User | None = None,
) -> Document:
    """The statement of account — previously a report you could only look at.

    Carries the aging strip as well as the ledger, because "how old" is the part
    that decides whether a conversation about payment is polite or urgent.
    """
    from .reports import ar_aging, statement_of_account

    statement = statement_of_account(organization, customer=customer, start=start, end=end)
    aging_rows = ar_aging(organization, as_of=end)["customers"]
    aging = next((r for r in aging_rows if r["customer_id"] == customer.pk), None)

    return generate_document(
        organization=organization,
        doc_type=DocType.STATEMENT,
        reference_type="customer_statement",
        reference_id=f"{customer.pk}:{start}:{end}",
        user=user,
        reuse_existing=True,
        context={
            "customer_name": statement["customer_name"],
            "start": start,
            "end": end,
            "opening_balance": statement["opening_balance"],
            "closing_balance": statement["closing_balance"],
            "lines": statement["lines"],
            "aging": aging,
        },
    )


# --------------------------------------------------------------------------- #
# Supplier-facing and internal
# --------------------------------------------------------------------------- #


@transaction.atomic
def remittance_advice_document(
    *, run: PaymentRun, supplier: Any = None, user: User | None = None
) -> Document:
    """Tell a supplier which invoices a bulk payment settled.

    Without it a payment run arrives as one unexplained amount and the supplier
    applies it to the wrong invoices, which is where reconciliation disputes start.
    """
    lines = run.lines.select_related("bill", "bill__supplier")
    if supplier is not None:
        lines = lines.filter(bill__supplier=supplier)
    rows = list(lines)
    total = sum((row.amount for row in rows), ZERO)
    supplier_name = (
        supplier.name
        if supplier is not None
        else (rows[0].bill.supplier.name if rows else "Multiple suppliers")
    )

    return generate_document(
        organization=run.organization,
        doc_type=DocType.REMITTANCE_ADVICE,
        reference_type="payment_run",
        reference_id=f"{run.pk}:{getattr(supplier, 'pk', 'all')}",
        user=user,
        reuse_existing=True,
        context={
            "supplier_name": supplier_name,
            "run_number": run.run_number,
            # Disbursement date if it has gone out, else the date it is scheduled
            # for. Creation date would be wrong: a run raised on the 1st and paid
            # on the 15th is a payment on the 15th.
            "value_date": (run.disbursed_at.date() if run.disbursed_at else run.scheduled_for),
            "currency": "RWF",
            "method": run.get_method_display(),
            "reference": run.run_number,
            "total": str(total),
            "lines": [
                {
                    "bill_number": row.bill.bill_number,
                    "bill_date": row.bill.bill_date,
                    "total": str(row.bill.total_amount),
                    "amount": str(row.amount),
                }
                for row in rows
            ],
        },
    )


@transaction.atomic
def payment_voucher_document(*, payment: SupplierBillPayment, user: User | None = None) -> Document:
    """The authorisation record for a payment, with a signature block."""
    bill = payment.bill
    entry = _entry_for(bill.organization, "supplier_bill_payment", payment.pk)
    return generate_document(
        organization=bill.organization,
        doc_type=DocType.PAYMENT_VOUCHER,
        reference_type="supplier_bill_payment",
        reference_id=str(payment.pk),
        user=user,
        reuse_existing=True,
        context={
            "payee": bill.supplier.name,
            "paid_on": payment.paid_at.date(),
            "purpose": f"Settlement of invoice {bill.bill_number}",
            "reference": payment.reference or "—",
            "currency": "RWF",
            "amount": str(payment.amount),
            "amount_words": amount_in_words(payment.amount),
            "prepared_by": getattr(payment.recorded_by, "get_full_name", lambda: "—")() or "—",
            "lines": _ledger_lines(entry),
        },
    )


@transaction.atomic
def journal_voucher_document(*, entry: JournalEntry, user: User | None = None) -> Document:
    """A signed slip for a posting.

    Manual journals are the entries a human typed, so they are the ones most worth
    being able to defend later.
    """
    lines = _ledger_lines(entry)
    return generate_document(
        organization=entry.organization,
        doc_type=DocType.JOURNAL_VOUCHER,
        reference_type="journal_entry",
        reference_id=str(entry.pk),
        user=user,
        reuse_existing=True,
        context={
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date,
            "description": entry.description,
            "source": entry.get_source_module_display(),
            "lines": lines,
            "total_debit": f"{entry.total_debit:.2f}",
            "total_credit": f"{entry.total_credit:.2f}",
            "posted_by": getattr(entry.posted_by, "get_full_name", lambda: "—")() or "—",
        },
    )


# --------------------------------------------------------------------------- #
# Statutory and management packs
# --------------------------------------------------------------------------- #


@transaction.atomic
def financial_statements_document(
    *, organization: Organization, start: date, end: date, user: User | None = None
) -> Document:
    """The P&L, balance sheet and trial balance as one filed pack."""
    from .reports import balance_sheet, profit_and_loss, trial_balance

    return generate_document(
        organization=organization,
        doc_type=DocType.FINANCIAL_STATEMENT,
        reference_type="financial_statements",
        reference_id=f"{start}:{end}",
        user=user,
        reuse_existing=True,
        context={
            "start": start,
            "end": end,
            "pnl": profit_and_loss(organization, start=start, end=end),
            "bs": balance_sheet(organization, as_of=end),
            "tb": trial_balance(organization, as_of=end),
            "prepared_by": getattr(user, "get_full_name", lambda: "—")() or "—",
        },
    )


@transaction.atomic
def vat_return_document(
    *, organization: Organization, start: date, end: date, user: User | None = None
) -> Document:
    """The filed copy of a VAT return — the CSV draft alone proves nothing later."""
    from .reports import vat_return

    data = vat_return(organization, start=start, end=end)

    # The report is keyed by tax class on each side; the filed copy needs one row
    # per class showing both. Rwanda: A exempt, B standard-rated 18%, C zero-rated.
    output_by_class = data["output_by_class"]
    input_by_class = data["input_by_class"]
    basis = {
        "A": "Exempt — no VAT charged",
        "B": "Standard rated — 18%",
        "C": "Zero rated — 0%",
        "D": "Out of scope",
    }
    rows = [
        {
            "tax_class": tax_class,
            "basis": basis.get(tax_class, ""),
            "output": str(output_by_class.get(tax_class, ZERO)),
            "input": str(input_by_class.get(tax_class, ZERO)),
            "net": str(
                Decimal(str(output_by_class.get(tax_class, ZERO)))
                - Decimal(str(input_by_class.get(tax_class, ZERO)))
            ),
        }
        for tax_class in sorted(set(output_by_class) | set(input_by_class))
    ]

    return generate_document(
        organization=organization,
        doc_type=DocType.VAT_RETURN,
        reference_type="vat_return",
        reference_id=f"{start}:{end}",
        user=user,
        reuse_existing=True,
        context={
            "start": start,
            "end": end,
            "rows": rows,
            "total_output": str(data["output_total"]),
            "total_input": str(data["input_total"]),
            "net_payable": str(data["net_payable"]),
            "withholding": str(data["withholding_total"]),
            "prepared_by": getattr(user, "get_full_name", lambda: "—")() or "—",
        },
    )
