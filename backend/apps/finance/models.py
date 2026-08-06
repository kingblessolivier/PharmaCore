"""Finance foundation: chart of accounts, the general ledger (journals), and
per-partner customer-credit management (limits/terms/holds).

See ROADMAP.md "9. Finance" (Phase 8) and docs/02-data-model.md. Each organization
keeps its own books; a journal entry must always balance (Σdebits = Σcredits) —
corrections are new reversing entries, never edits (immutable once posted).
"""

from __future__ import annotations

from datetime import date
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
        constraints = [
            # ADR-011 idempotency contract: every handler in
            # JournalPostingService is idempotent on (source_doc,
            # source_line). For top-level journal entries that means a unique
            # (org, reference_type, reference_id) per posted entry. Conditional
            # because manual / adjustment entries legitimately share a single
            # empty reference.
            models.UniqueConstraint(
                fields=["organization", "reference_type", "reference_id"],
                condition=models.Q(reference_type__gt=""),
                name="uniq_journal_reference_per_org",
            )
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
    # Bank reconciliation: matched against a bank/MoMo statement line.
    is_reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    statement_reference = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.side} {self.amount} {self.account.code}"


class AccountingPeriod(models.Model):
    """An EOD/EOM closeout. Closing a period freezes it: no new entry may be dated
    inside a closed window, so last month's trial balance can never move after it
    has been reported. Reopening is a deliberate, audited act.

    ROADMAP "9. Finance" — *"Period close — EOD/EOM closeout, trial balance, P&L,
    balance sheet, cash-flow"*.
    """

    class Kind(models.TextChoices):
        DAY = "DAY", "Day (EOD)"
        MONTH = "MONTH", "Month (EOM)"
        YEAR = "YEAR", "Year"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="accounting_periods"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.MONTH)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    # Snapshot of the headline figures at the moment of closing, so the closed
    # period reports the same numbers forever even if later code changes.
    closing_totals = models.JSONField(default=dict, blank=True)
    closed_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    reopened_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reopened_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "kind", "start_date", "end_date"],
                name="uniq_accounting_period",
            )
        ]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"{self.organization.name} {self.kind} {self.start_date}–{self.end_date}"

    def covers(self, day: date) -> bool:
        return self.start_date <= day <= self.end_date


class BankAccount(models.Model):
    """A bank/MoMo/Airtel/cash account an organization holds. Each gets its own
    chart-of-accounts sub-ledger (a child of the "1000 Cash & Bank" control
    account) so its cash-book and reconciliation are tracked separately —
    ROADMAP "9. Finance": "bank/MoMo/Airtel accounts, reconciliation, ... cash-book"."""

    class Kind(models.TextChoices):
        BANK = "BANK", "Bank"
        MOMO = "MOMO", "Mobile money (MTN MoMo)"
        AIRTEL = "AIRTEL", "Mobile money (Airtel)"
        CASH = "CASH", "Cash on hand"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="bank_accounts"
    )
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.BANK)
    bank_name = models.CharField(max_length=150, blank=True, default="")
    account_number = models.CharField(max_length=50, blank=True, default="")
    currency = models.CharField(max_length=3, default="RWF")
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # The dedicated GL sub-account this bank account's postings hit (auto-created).
    gl_account = models.OneToOneField(
        Account, on_delete=models.PROTECT, related_name="bank_account"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.kind})"


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
    # VAT-inclusive default for backwards compatibility. If vat_amount is set,
    # the bill posts to the GL as: Dr Expense(net) + Dr VAT Input(vat_amount) /
    # Cr AP(total_amount). If vat_amount is 0, the whole amount posts to Dr
    # Expense / Cr AP (zero-rated supplier or non-VAT-able import).
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_class = models.CharField(max_length=4, blank=True, default="")
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


class FixedAsset(models.Model):
    """Fixed asset register & straight-line depreciation schedule. ROADMAP '9. Finance'."""

    class Category(models.TextChoices):
        EQUIPMENT = "EQUIPMENT", "Medical & Cold-Chain Equipment"
        FURNITURE = "FURNITURE", "Pharmacy Furniture & Fixtures"
        VEHICLE = "VEHICLE", "Delivery Vehicle"
        IT_HARDWARE = "IT_HARDWARE", "IT & POS Hardware"
        LEASEHOLD = "LEASEHOLD", "Leasehold Improvements"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="fixed_assets"
    )
    asset_number = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.EQUIPMENT)
    acquisition_date = models.DateField()
    acquisition_cost = models.DecimalField(max_digits=14, decimal_places=2)
    useful_life_years = models.PositiveIntegerField(default=5)
    salvage_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    accumulated_depreciation = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-acquisition_date"]

    def __str__(self) -> str:
        return f"{self.asset_number} · {self.name}"

    @property
    def net_book_value(self) -> Decimal:
        return self.acquisition_cost - self.accumulated_depreciation

    @property
    def annual_depreciation(self) -> Decimal:
        if self.useful_life_years == 0:
            return Decimal("0")
        return (self.acquisition_cost - self.salvage_value) / Decimal(str(self.useful_life_years))


class TaxRecord(models.Model):
    """EBM Fiscalization & VAT audit trail record. ROADMAP '9. Finance'."""

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="tax_records"
    )
    receipt_number = models.CharField(max_length=50, unique=True)
    sdc_id = models.CharField(max_length=50, blank=True, default="")
    mrc_number = models.CharField(max_length=50, blank=True, default="")
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2)
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2)
    tax_class_a = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # Exempt
    tax_class_b = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # 18% Standard VAT
    tax_class_c = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # Zero Rated
    qr_code_payload = models.TextField(blank=True, default="")
    fiscalized_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fiscalized_at"]

    def __str__(self) -> str:
        return f"EBM-{self.receipt_number} ({self.vat_amount} VAT)"


class Budget(models.Model):
    """Departmental budget vs actual variance tracking. ROADMAP '9. Finance'."""

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="budgets"
    )
    department = models.ForeignKey(
        "iam.Department", on_delete=models.CASCADE, related_name="budgets"
    )
    financial_year = models.PositiveIntegerField(default=2026)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="budgets")
    budgeted_amount = models.DecimalField(max_digits=14, decimal_places=2)
    actual_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["financial_year", "department"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "department", "financial_year", "account"],
                name="uniq_budget_line",
            )
        ]

    def __str__(self) -> str:
        return f"Budget FY{self.financial_year} · {self.department.name} · {self.account.code}"

    @property
    def variance(self) -> Decimal:
        return self.budgeted_amount - self.actual_amount


class TaxCode(models.Model):
    """A Rwanda VAT tax class (A/B/C/D) with its effective-dated rate and an
    optional withholding-tax flag. Versions are rows, not code: a new Finance
    Law = one new row with effective_from set, never a migration.

    Rwanda 2025:
      A — Exempt (e.g. certain medical services)
      B — Standard 18% (e.g. cosmetics, non-medical sundries)
      C — Zero-rated (e.g. medicines, medical supplies)
      D — Special handling (e.g. exported services)
    """

    class Class(models.TextChoices):
        A = "A", "Class A — Exempt"
        B = "B", "Class B — Standard 18%"
        C = "C", "Class C — Zero-rated"
        D = "D", "Class D — Special"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="tax_codes"
    )
    code = models.CharField(max_length=4, choices=Class.choices)
    description = models.CharField(max_length=255, blank=True, default="")
    rate_pct = models.DecimalField(max_digits=5, decimal_places=2)
    withholding_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Withholding tax rate applied to this class (0 if not subject to WHT).",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    source_reference = models.CharField(
        max_length=255, blank=True, default="",
        help_text="RRA circular / Finance Law / Gazette reference that justifies the rate.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code", "-effective_from"]
        constraints = [
            # A given code's effective-from dates must be unique per org — you
            # can't have two "B @ 18%" both starting 2025-01-01.
            models.UniqueConstraint(
                fields=["organization", "code", "effective_from"],
                name="uniq_tax_code_per_effective_from",
            ),
        ]
        indexes = [models.Index(fields=["organization", "code", "effective_from"])]

    def __str__(self) -> str:
        span = f"{self.effective_from}" + (f"→{self.effective_to}" if self.effective_to else "→open")
        return f"{self.code} {self.rate_pct}% ({span})"


class TaxPayment(models.Model):
    """A remittance to RRA — pays down the outstanding VAT Output / withholding
    liability. Approval-gated because money leaves the bank."""

    class Method(models.TextChoices):
        BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
        CHEQUE = "CHEQUE", "Cheque"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="tax_payments"
    )
    payment_number = models.CharField(max_length=30, blank=True, default="")
    paid_on = models.DateField()
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.BANK_TRANSFER)
    rra_reference = models.CharField(
        max_length=100, blank=True, default="",
        help_text="RRA e-Tax receipt / bank confirmation reference.",
    )
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on"]
        indexes = [models.Index(fields=["organization", "paid_on"])]

    def __str__(self) -> str:
        return f"{self.payment_number or f'TAX#{self.pk}'} · {self.amount}"


class TenantSettings(models.Model):
    """Per-tenant configuration that lives **in the database, not in code**.

    ADR-014 makes these first-class. Everything that varies by tenant —
    inventory costing method, FX provider, pay-period cadence, statutory
    remittance day, PIT filing deadline — is read by the service layer
    via :func:`apps.finance.services.tenant_settings_for`. There is exactly
    one row per organization, lazily created the first time it's needed.
    """

    class CostingMethod(models.TextChoices):
        WAC = "WAC", "Weighted average cost"
        FEFO_LOT = "FEFO_LOT", "FEFO at the lot level (batch cost)"

    class PayPeriod(models.TextChoices):
        DAILY = "DAILY", "Daily"
        WEEKLY = "WEEKLY", "Weekly"
        FORTNIGHTLY = "FORTNIGHTLY", "Fortnightly"
        MONTHLY = "MONTHLY", "Monthly"

    organization = models.OneToOneField(
        "iam.Organization",
        on_delete=models.CASCADE,
        related_name="tenant_settings",
    )

    # Money & FX
    base_currency = models.CharField(max_length=3, default="RWF")
    fx_provider = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Identifier for the FX rate provider (e.g. 'BNR', 'manual').",
    )

    # Inventory valuation
    costing_method = models.CharField(
        max_length=10,
        choices=CostingMethod.choices,
        default=CostingMethod.FEFO_LOT,
    )

    # HR / payroll
    pay_period = models.CharField(
        max_length=12,
        choices=PayPeriod.choices,
        default=PayPeriod.MONTHLY,
    )
    statutory_remittance_day = models.PositiveSmallIntegerField(
        default=15,
        help_text="Day-of-month statutory remittances are paid (Rwanda default: 15).",
    )

    # PIT filing deadline — Rwanda personal-income-tax declaration
    pit_filing_deadline_month = models.PositiveSmallIntegerField(default=3)  # March
    pit_filing_deadline_day = models.PositiveSmallIntegerField(default=31)

    # Locale & display
    default_country = models.CharField(max_length=2, default="RW")
    timezone = models.CharField(max_length=50, default="Africa/Kigali")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name"]

    def __str__(self) -> str:
        return f"TenantSettings({self.organization.name})"

