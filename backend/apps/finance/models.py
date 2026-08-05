"""Finance foundation: chart of accounts, the general ledger (journals), and
per-partner customer-credit management (limits/terms/holds).

See ROADMAP.md "9. Finance" (Phase 8) and docs/02-data-model.md. Each organization
keeps its own books; a journal entry must always balance (Σdebits = Σcredits) —
corrections are new reversing entries, never edits (immutable once posted).
"""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Account(models.Model):
    """A chart-of-accounts line for one organization's books."""

    class Type(models.TextChoices):
        ASSET = "ASSET", "Asset"
        LIABILITY = "LIABILITY", "Liability"
        EQUITY = "EQUITY", "Equity"
        REVENUE = "REVENUE", "Revenue"
        EXPENSE = "EXPENSE", "Expense"

    class Balance(models.TextChoices):
        DEBIT = "DEBIT", "Debit"
        CREDIT = "CREDIT", "Credit"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="accounts"
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=20, choices=Type.choices)
    normal_balance = models.CharField(max_length=10, choices=Balance.choices)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    # System control accounts (Cash & Bank, AR, AP, …) are auto-created and
    # protected from deletion, per the auto-posting rules.
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="uniq_account_code_per_org"
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class JournalEntry(models.Model):
    """A balanced double-entry posting. Immutable once created — a correction is a
    new reversing entry, never an edit (see docs/06-workflows-state-machines.md §9)."""

    class Status(models.TextChoices):
        POSTED = "POSTED", "Posted"
        REVERSED = "REVERSED", "Reversed"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="journal_entries"
    )
    entry_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    entry_date = models.DateField()
    description = models.CharField(max_length=255, blank=True, default="")
    reference_type = models.CharField(max_length=50, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.POSTED)
    reversal_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reversals"
    )
    posted_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-entry_date", "-id"]
        indexes = [
            models.Index(fields=["organization", "entry_date"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]

    def __str__(self) -> str:
        return self.entry_number or f"JE#{self.pk}"

    @property
    def total_debit(self) -> float:
        return float(sum(ln.amount for ln in self.lines.all() if ln.side == JournalLine.Side.DEBIT))

    @property
    def total_credit(self) -> float:
        return float(
            sum(ln.amount for ln in self.lines.all() if ln.side == JournalLine.Side.CREDIT)
        )


class JournalLine(models.Model):
    class Side(models.TextChoices):
        DEBIT = "DEBIT", "Debit"
        CREDIT = "CREDIT", "Credit"

    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")
    side = models.CharField(max_length=10, choices=Side.choices)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    memo = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.side} {self.amount} {self.account.code}"


class CreditProfile(models.Model):
    """Credit terms one organization (the creditor, usually a depot) extends to
    another (the debtor, usually a retail buyer). Limit/terms/hold changes are
    approval-gated — see services.request_credit_override()."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        HOLD = "HOLD", "On hold"

    creditor = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="credit_extended"
    )
    debtor = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="credit_received"
    )
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    terms_days = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    hold_reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["creditor", "debtor"], name="uniq_credit_profile_pair")
        ]

    def __str__(self) -> str:
        return f"{self.debtor.name} credit from {self.creditor.name}"


class SupplierBill(models.Model):
    """An invoice from an external supplier (AP). ROADMAP "9. Finance" calls for a
    full **3-way match** (PO ↔ GRN ↔ invoice) — that needs the Procurement
    subsystem's Purchase Order + goods-receipt-against-PO models, which don't exist
    yet (ROADMAP "4. Procurement & imports" is still entirely ⬜). This is the
    2-way bill↔payment flow that *is* buildable today; ``reference_type``/
    ``reference_id`` lets a bill optionally point at a GRN for manual reconciliation
    until the PO module lands and the match can be made real and enforced."""

    class Status(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PARTIAL = "PARTIAL", "Partially paid"
        PAID = "PAID", "Paid"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="supplier_bills"
    )
    supplier = models.ForeignKey("catalog.Supplier", on_delete=models.PROTECT, related_name="bills")
    bill_number = models.CharField(max_length=50, blank=True, default="")
    bill_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNPAID)
    reference_type = models.CharField(max_length=50, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-bill_date"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"{self.bill_number or f'Bill#{self.pk}'} · {self.supplier.name}"

    @property
    def amount_due(self) -> Decimal:
        return self.total_amount - self.amount_paid


class SupplierBillPayment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
        CHEQUE = "CHEQUE", "Cheque"

    bill = models.ForeignKey(SupplierBill, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.BANK_TRANSFER)
    reference = models.CharField(max_length=100, blank=True, default="")
    recorded_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    paid_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.amount} for {self.bill}"
