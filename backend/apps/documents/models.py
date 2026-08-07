"""Document engine models: gapless numbering + an immutable, hashed document vault.

See docs/design/08-document-design-and-authenticity.md. Finalized documents are
write-once (append-only) and tamper-evident via a SHA-256 content hash + QR token.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models


class DocType(models.TextChoices):
    PURCHASE_ORDER = "PURCHASE_ORDER", "Purchase order"
    PACKING_SLIP = "PACKING_SLIP", "Packing slip"
    DELIVERY_NOTE = "DELIVERY_NOTE", "Delivery note"
    GRN = "GRN", "Goods received note"
    TAX_INVOICE = "TAX_INVOICE", "Tax invoice"
    CREDIT_NOTE = "CREDIT_NOTE", "Credit note"
    RECEIPT = "RECEIPT", "Receipt"
    PAYSLIP = "PAYSLIP", "Payslip"
    # Finance. A report you can only look at is not a document you can send,
    # file, and later prove was not altered — these close that gap.
    DEBIT_NOTE = "DEBIT_NOTE", "Debit note"
    STATEMENT = "STATEMENT", "Statement of account"
    REMITTANCE_ADVICE = "REMITTANCE_ADVICE", "Remittance advice"
    PAYMENT_VOUCHER = "PAYMENT_VOUCHER", "Payment voucher"
    JOURNAL_VOUCHER = "JOURNAL_VOUCHER", "Journal voucher"
    FINANCIAL_STATEMENT = "FINANCIAL_STATEMENT", "Financial statements"
    VAT_RETURN = "VAT_RETURN", "VAT return"


# Per-type human prefix for the document number.
DOC_PREFIX: dict[str, str] = {
    DocType.PURCHASE_ORDER: "PO",
    DocType.PACKING_SLIP: "PS",
    DocType.DELIVERY_NOTE: "DN",
    DocType.GRN: "GRN",
    DocType.TAX_INVOICE: "INV",
    DocType.CREDIT_NOTE: "CN",
    DocType.RECEIPT: "RCT",
    DocType.PAYSLIP: "PAY",
    DocType.DEBIT_NOTE: "DBN",
    DocType.STATEMENT: "STMT",
    DocType.REMITTANCE_ADVICE: "RA",
    DocType.PAYMENT_VOUCHER: "PV",
    DocType.JOURNAL_VOUCHER: "JV",
    DocType.FINANCIAL_STATEMENT: "FS",
    DocType.VAT_RETURN: "VAT",
}


class DocumentSequence(models.Model):
    """Gapless per-organization, per-type, per-year document numbering."""

    organization = models.ForeignKey("iam.Organization", on_delete=models.CASCADE)
    doc_type = models.CharField(max_length=30, choices=DocType.choices)
    year = models.IntegerField()
    next_number = models.BigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "doc_type", "year"], name="uniq_doc_sequence"
            )
        ]

    def __str__(self) -> str:
        return f"{self.doc_type} {self.year}: next {self.next_number}"


class Document(models.Model):
    """A generated, hashed, write-once document in the vault."""

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="documents"
    )
    doc_type = models.CharField(max_length=30, choices=DocType.choices)
    # Numbering is allocated per organization (see DocumentSequence), so the number
    # is unique *within a tenant* — not globally. A global unique made the second
    # organization to issue a PO collide with the first one's PO-YYYY-00001.
    doc_number = models.CharField(max_length=40)
    reference_type = models.CharField(max_length=50, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="")
    file = models.FileField(upload_to="documents/%Y/%m/")
    content_hash = models.CharField(max_length=64)  # SHA-256 of the PDF bytes
    qr_token = models.CharField(max_length=32, unique=True)  # public verification handle
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "doc_number"], name="uniq_document_number_per_org"
            )
        ]
        indexes = [
            models.Index(fields=["reference_type", "reference_id"]),
            models.Index(fields=["organization", "doc_type"]),
        ]

    def __str__(self) -> str:
        return self.doc_number

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Write-once: a finalized document is never modified.
        if not self._state.adding:
            raise ValueError("Documents are write-once and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("Documents are write-once and cannot be deleted.")
