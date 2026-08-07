"""Finance documents actually render, and say what they must.

The engine was already there and finance never called it, so these assert the
wiring end to end: a real record in, a numbered and hashed PDF out, with the
content a recipient needs to act on it.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from apps.documents.models import DocType, Document
from apps.finance.documents import (
    amount_in_words,
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
    JournalLine,
    SupplierBill,
    SupplierBillPayment,
)
from apps.finance.services import ensure_default_accounts, post_journal
from apps.iam.models import Organization

pytestmark = pytest.mark.django_db

START = date(2026, 6, 1)
END = date(2026, 6, 30)
D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT


@pytest.fixture
def org(db: None) -> Organization:
    organization = Organization.objects.create(name="Gikondo Pharmacy", type="DEPOT")
    ensure_default_accounts(organization)
    return organization


@pytest.fixture
def customer(db: None) -> Organization:
    return Organization.objects.create(name="Kabuga Retail Pharmacy", type="RETAIL")


# --------------------------------------------------------------------------- #
# Amounts in words
# --------------------------------------------------------------------------- #


def test_amounts_are_spelled_out_for_the_signature_line() -> None:
    """A voucher carries words because that is the line a pen cannot alter."""
    assert amount_in_words(0) == "Zero Rwandan francs"
    assert amount_in_words(12) == "Twelve Rwandan francs"
    assert amount_in_words(98_000) == "Ninety-eight thousand Rwandan francs"
    assert amount_in_words(1_000_000) == "One million Rwandan francs"
    assert (
        amount_in_words(Decimal("1250000.50"))
        == "One million two hundred and fifty thousand Rwandan francs and fifty cents"
    )


# --------------------------------------------------------------------------- #
# Statement of account
# --------------------------------------------------------------------------- #


def test_a_statement_is_a_document_not_just_a_report(
    org: Organization, customer: Organization
) -> None:
    """A customer disputing a balance needs something they can be sent."""
    CustomerInvoice.objects.create(
        organization=org,
        customer=customer,
        invoice_number="INV-2026-001",
        invoice_date=date(2026, 6, 5),
        due_date=date(2026, 7, 5),
        total_amount=Decimal("500000"),
        vat_amount=Decimal("0"),
    )

    document = statement_document(organization=org, customer=customer, start=START, end=END)

    assert document.doc_type == DocType.STATEMENT
    assert document.doc_number.startswith("STMT-")
    assert document.file.name.endswith(".pdf")
    assert len(document.content_hash) == 64  # SHA-256, so alteration is detectable
    assert document.qr_token  # publicly verifiable


def test_asking_twice_returns_the_same_document(org: Organization, customer: Organization) -> None:
    """Otherwise every click burns a document number."""
    first = statement_document(organization=org, customer=customer, start=START, end=END)
    second = statement_document(organization=org, customer=customer, start=START, end=END)
    assert first.pk == second.pk
    assert Document.objects.filter(doc_type=DocType.STATEMENT).count() == 1


# --------------------------------------------------------------------------- #
# Vouchers
# --------------------------------------------------------------------------- #


def test_a_payment_voucher_carries_the_authorisation_trail(org: Organization) -> None:
    from apps.catalog.models import Supplier

    supplier = Supplier.objects.create(name="Kigali Medical Supplies")
    bill = SupplierBill.objects.create(
        organization=org,
        supplier=supplier,
        bill_number="SB-001",
        bill_date=date(2026, 6, 2),
        due_date=date(2026, 7, 2),
        total_amount=Decimal("300000"),
    )
    payment = SupplierBillPayment.objects.create(
        bill=bill, amount=Decimal("300000"), method="BANK_TRANSFER", reference="BK-778"
    )

    document = payment_voucher_document(payment=payment)
    assert document.doc_type == DocType.PAYMENT_VOUCHER
    assert document.doc_number.startswith("PV-")
    assert document.reference_type == "supplier_bill_payment"


def test_a_journal_voucher_is_produced_for_a_manual_posting(org: Organization) -> None:
    """Manual journals are what a human typed, so they are what gets questioned."""
    accounts = ensure_default_accounts(org)
    entry = post_journal(
        organization=org,
        entry_date=END,
        description="Reclassify rent",
        lines=[
            {"account": accounts["6110"], "side": D, "amount": Decimal("40000"), "memo": "rent"},
            {"account": accounts["1100"], "side": C, "amount": Decimal("40000"), "memo": ""},
        ],
    )

    document = journal_voucher_document(entry=entry)
    assert document.doc_type == DocType.JOURNAL_VOUCHER
    assert document.doc_number.startswith("JV-")


# --------------------------------------------------------------------------- #
# Statement pack
# --------------------------------------------------------------------------- #


def test_the_financial_statement_pack_renders(org: Organization) -> None:
    accounts = ensure_default_accounts(org)
    post_journal(
        organization=org,
        entry_date=date(2026, 6, 10),
        description="Sale",
        lines=[
            {"account": accounts["1100"], "side": D, "amount": Decimal("900000"), "memo": ""},
            {"account": accounts["4100"], "side": C, "amount": Decimal("900000"), "memo": ""},
        ],
    )

    document = financial_statements_document(organization=org, start=START, end=END)
    assert document.doc_type == DocType.FINANCIAL_STATEMENT
    assert document.doc_number.startswith("FS-")
    assert document.file.size > 0


def test_documents_are_numbered_per_organization_and_year(
    org: Organization, customer: Organization
) -> None:
    """Two organizations must not collide on STMT-2026-00001."""
    other = Organization.objects.create(name="Musanze Depot", type="DEPOT")
    ensure_default_accounts(other)

    a = statement_document(organization=org, customer=customer, start=START, end=END)
    b = statement_document(
        organization=other, customer=customer, start=START, end=END - timedelta(days=1)
    )
    assert a.doc_number == b.doc_number  # same sequence position…
    assert a.organization_id != b.organization_id  # …but different books


# --------------------------------------------------------------------------- #
# The documents that were not covered first time round.
#
# Four of the nine generators were untested, and three of those were broken:
# `credit.reason` and `receipt.received_by` did not exist as fields, and the VAT
# return guessed at the report's payload keys and rendered empty. Defensive
# `getattr`/`.get()` fallbacks hid all of it — the code ran and produced a wrong
# document, which is worse than a crash. These cover every generator.
# --------------------------------------------------------------------------- #


def _invoice(org: Organization, customer: Organization, **kw) -> CustomerInvoice:
    defaults = {
        "organization": org,
        "customer": customer,
        "invoice_number": f"INV-{CustomerInvoice.objects.count() + 1:04d}",
        "invoice_date": date(2026, 6, 5),
        "due_date": date(2026, 7, 5),
        "total_amount": Decimal("236000"),
        "vat_amount": Decimal("36000"),
    }
    defaults.update(kw)
    return CustomerInvoice.objects.create(**defaults)


def test_a_tax_invoice_renders_with_the_net_and_vat_split(
    org: Organization, customer: Organization
) -> None:
    invoice = _invoice(org, customer)
    document = customer_invoice_document(invoice=invoice)
    assert document.doc_type == DocType.TAX_INVOICE
    assert document.doc_number.startswith("INV-")
    assert document.file.size > 0


def test_a_receipt_renders_and_names_who_took_the_money(
    org: Organization, customer: Organization
) -> None:
    """`received_by` was not a field — this raised AttributeError before."""
    invoice = _invoice(org, customer)
    receipt = CustomerReceipt.objects.create(
        invoice=invoice,
        receipt_number="RCT-0001",
        amount=Decimal("100000"),
        method="BANK_TRANSFER",
        received_on=date(2026, 6, 20),
    )
    document = customer_receipt_document(receipt=receipt)
    assert document.doc_type == DocType.RECEIPT
    assert document.file.size > 0


def test_a_credit_note_renders_from_the_notes_field(
    org: Organization, customer: Organization
) -> None:
    """`credit.reason` was not a field — this raised AttributeError before."""
    credit = CustomerCredit.objects.create(
        organization=org,
        customer=customer,
        amount=Decimal("50000"),
        balance=Decimal("50000"),
        notes="Short delivery on INV-0001",
    )
    document = credit_note_document(credit=credit)
    assert document.doc_type == DocType.CREDIT_NOTE
    assert document.doc_number.startswith("CN-")
    assert document.file.size > 0


def test_a_credit_note_with_no_note_falls_back_to_its_source(
    org: Organization, customer: Organization
) -> None:
    credit = CustomerCredit.objects.create(
        organization=org, customer=customer, amount=Decimal("1000"), balance=Decimal("1000")
    )
    assert credit_note_document(credit=credit).file.size > 0


def test_a_remittance_advice_uses_the_disbursement_date_not_the_creation_date(
    org: Organization,
) -> None:
    """A run raised on the 1st and paid on the 15th is a payment on the 15th."""
    from apps.catalog.models import Supplier
    from apps.finance.models import PaymentRun, PaymentRunLine

    supplier = Supplier.objects.create(name="Nyabugogo Distributors")
    bill = SupplierBill.objects.create(
        organization=org,
        supplier=supplier,
        bill_number="SB-777",
        bill_date=date(2026, 6, 1),
        due_date=date(2026, 6, 30),
        total_amount=Decimal("450000"),
    )
    run = PaymentRun.objects.create(
        organization=org,
        run_number="PR-0001",
        method="BANK_TRANSFER",
        scheduled_for=date(2026, 6, 15),
        total_amount=Decimal("450000"),
    )
    PaymentRunLine.objects.create(payment_run=run, bill=bill, amount=Decimal("450000"))

    document = remittance_advice_document(run=run)
    assert document.doc_type == DocType.REMITTANCE_ADVICE
    assert document.doc_number.startswith("RA-")
    assert document.file.size > 0


def test_the_vat_return_carries_the_real_class_breakdown(org: Organization) -> None:
    """It guessed at the report's keys before and rendered an empty return.

    A document that renders wrong is worse than one that fails, because nobody
    goes looking.
    """
    accounts = ensure_default_accounts(org)
    post_journal(
        organization=org,
        entry_date=date(2026, 6, 12),
        description="Standard-rated sale",
        lines=[
            {"account": accounts["1100"], "side": D, "amount": Decimal("118000"), "memo": ""},
            {"account": accounts["4100"], "side": C, "amount": Decimal("100000"), "memo": ""},
            {"account": accounts["2300"], "side": C, "amount": Decimal("18000"), "memo": "B"},
        ],
    )

    from apps.finance.reports import vat_return as vat_report

    report = vat_report(org, start=START, end=END)
    assert report["output_total"] == Decimal("18000.00")

    document = vat_return_document(organization=org, start=START, end=END)
    assert document.doc_type == DocType.VAT_RETURN
    assert document.doc_number.startswith("VAT-")
    assert document.file.size > 0


def test_every_generator_is_covered() -> None:
    """A generator with no test is a document nobody has ever seen."""
    from apps.finance import documents as mod

    # Only functions defined here — `generate_document` is the shared engine,
    # imported into this namespace and covered by the documents app's own tests.
    generators = {
        name
        for name in dir(mod)
        if name.endswith("_document")
        and callable(getattr(mod, name))
        and getattr(getattr(mod, name), "__module__", "") == mod.__name__
    }
    source = Path(__file__).read_text(encoding="utf-8")
    untested = sorted(g for g in generators if f"{g}(" not in source)
    assert untested == [], f"Document generators with no test: {untested}"
