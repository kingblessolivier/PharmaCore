"""Which documents a person may see.

The vault was scoped to the organizations you can see and no further, so a
cashier at a branch could list and download every document that branch had ever
generated — including **payslips** and the financial statements. Org scoping is
the right first cut and the wrong last one: a document's *type* decides who may
read it, not only which pharmacy produced it.

Rather than denying the whole vault to everyone without `finance.view` — which
would stop a warehouse clerk fetching the delivery note they need — the queryset
is filtered by type. You see the documents your job produces and consumes.
"""

from __future__ import annotations

from apps.documents.models import DocType

#: Document types that reveal pay. Restricted to whoever may view employees.
PAYROLL_TYPES = {DocType.PAYSLIP}

#: Document types that reveal the company's financial position.
FINANCE_TYPES = {
    DocType.PAYMENT_VOUCHER,
    DocType.JOURNAL_VOUCHER,
    DocType.FINANCIAL_STATEMENT,
    DocType.VAT_RETURN,
    DocType.STATEMENT,
    DocType.REMITTANCE_ADVICE,
}


def visible_doc_types(user) -> set[str] | None:  # type: ignore[no-untyped-def]
    """The document types ``user`` may read. ``None`` means all of them.

    Everything not named above — delivery notes, packing slips, GRNs, tax
    invoices, receipts, credit notes — is operational paperwork that the people
    handling the goods legitimately need.
    """
    if user.is_superuser or user.has_role("SYS_ADMIN"):
        return None

    everything = {choice.value for choice in DocType}
    hidden: set[str] = set()
    if not user.has_permission("employee.view"):
        hidden |= {t.value for t in PAYROLL_TYPES}
    if not user.has_permission("finance.view"):
        hidden |= {t.value for t in FINANCE_TYPES}
    return everything - hidden
