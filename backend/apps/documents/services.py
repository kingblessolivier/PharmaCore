"""Document generation: number → render → hash → QR → store, in one shot."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.documents.models import DOC_PREFIX, Document, DocumentSequence
from apps.documents.renderer import qr_data_uri, render_pdf
from apps.iam.models import Organization, User

_TEMPLATES = {
    "PURCHASE_ORDER": "documents/purchase_order.html",
    "DELIVERY_NOTE": "documents/delivery_note.html",
    "GRN": "documents/grn.html",
    "TAX_INVOICE": "documents/tax_invoice.html",
    "RECEIPT": "documents/receipt.html",
    "CREDIT_NOTE": "documents/credit_note.html",
    "PAYSLIP": "documents/payslip.html",
    "DEBIT_NOTE": "documents/debit_note.html",
    "STATEMENT": "documents/statement.html",
    "REMITTANCE_ADVICE": "documents/remittance_advice.html",
    "PAYMENT_VOUCHER": "documents/payment_voucher.html",
    "JOURNAL_VOUCHER": "documents/journal_voucher.html",
    "FINANCIAL_STATEMENT": "documents/financial_statement.html",
    "VAT_RETURN": "documents/vat_return.html",
}


def _allocate_number(organization: Organization, doc_type: str) -> str:
    year = timezone.now().year
    seq, _ = DocumentSequence.objects.select_for_update().get_or_create(
        organization=organization, doc_type=doc_type, year=year
    )
    number = seq.next_number
    seq.next_number += 1
    seq.save(update_fields=["next_number"])
    return f"{DOC_PREFIX.get(doc_type, 'DOC')}-{year}-{number:05d}"


@transaction.atomic
def generate_document(
    *,
    organization: Organization,
    doc_type: str,
    context: dict[str, Any],
    reference_type: str = "",
    reference_id: str = "",
    user: User | None = None,
    reuse_existing: bool = False,
) -> Document:
    """Generate a numbered, hashed, QR-verified PDF and store it write-once.

    ``reuse_existing`` returns the document already issued for this
    ``(organization, doc_type, reference_type, reference_id)`` instead of issuing
    a new one. Callers whose document *is* the record — a statement of account for
    a period, a voucher for a payment — want that, because clicking twice would
    otherwise burn a number out of a gapless sequence and leave two numbered
    originals of the same thing in circulation.

    It is opt-in rather than the default: a purchase order reissued after the
    order was amended is genuinely a new document, and silently handing back the
    stale PDF would be worse than an extra number.
    """
    if reuse_existing and reference_type:
        existing = Document.objects.filter(
            organization=organization,
            doc_type=doc_type,
            reference_type=reference_type,
            reference_id=reference_id,
        ).first()
        if existing is not None:
            return existing

    doc_number = _allocate_number(organization, doc_type)
    qr_token = uuid.uuid4().hex
    base_url = getattr(settings, "DOCUMENT_VERIFY_BASE_URL", "https://pharmacore.local/verify")
    verify_url = f"{base_url}/{qr_token}"

    html = render_to_string(
        _TEMPLATES[doc_type],
        {
            **context,
            "organization": organization,
            "doc_number": doc_number,
            "doc_type_label": doc_type.replace("_", " ").title(),
            "generated_at": timezone.now(),
            "qr": qr_data_uri(verify_url),
        },
    )
    pdf_bytes = render_pdf(html)
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()

    doc = Document(
        organization=organization,
        doc_type=doc_type,
        doc_number=doc_number,
        reference_type=reference_type,
        reference_id=reference_id,
        content_hash=content_hash,
        qr_token=qr_token,
        generated_by=user,
    )
    doc.file.save(f"{doc_number}.pdf", ContentFile(pdf_bytes), save=False)
    doc.save()
    return doc
