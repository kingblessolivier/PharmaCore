"""People (§10) — the entities the Employee master hangs off that were missing.

Split into its own module (imported from ``models.py``) purely so the HR model
layer stays readable; Django resolves the ``hr`` app label from the package path,
so these are ordinary ``hr`` models.

What this adds, and why each one has to exist:

* **Contract & pay structure** — ``base_salary`` as a single number cannot express
  a Rwandan payslip. Transport allowance sits *inside* the RSSB pension base but
  *outside* the maternity base, and CBHI is charged on net; without itemised,
  effective-dated components the gross→net engine cannot be correct, only close.
* **Leave types, balances, accrual** — a leave request is meaningless without a
  balance to check it against, and unpaid leave has to reach payroll.
* **Timesheets** — attendance is raw punches; a timesheet is the approved,
  overtime-calculated artefact payroll is allowed to read.
* **Loans & advances** — deducted by the payroll engine, with a real schedule.
* **Payroll adjustments** — a locked run is immutable, so arrears and back-pay
  must land as their own adjustment in a later run.
* **Recruitment → onboarding → offboarding** — the employee lifecycle either side
  of employment, including the final settlement the Labour Code requires.
* **Training, CPD, competency, discipline, performance** — the compliance record
  that gates dispensing (an expired licence must revoke it) and controlled-drug
  handling.
* **Statutory filings** — PAYE/RSSB/CBHI returns are due on the 15th; the filing
  is a first-class document that must tie to the GL sub-ledger.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import models

ZERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Contract & salary structure
# ---------------------------------------------------------------------------


class EmploymentContract(models.Model):
    """A signed agreement between the org and an employee.

    An employee can hold several over time (renewal, promotion, conversion from
    fixed-term to permanent); exactly one is current.
    """

    class Kind(models.TextChoices):
        PERMANENT = "PERMANENT", "Permanent (CDI)"
        FIXED_TERM = "FIXED_TERM", "Fixed term (CDD)"
        CASUAL = "CASUAL", "Casual / daily"
        INTERNSHIP = "INTERNSHIP", "Internship"
        CONSULTANCY = "CONSULTANCY", "Consultancy"
        APPRENTICESHIP = "APPRENTICESHIP", "Apprenticeship"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        RENEWED = "RENEWED", "Renewed (superseded)"
        EXPIRED = "EXPIRED", "Expired"
        TERMINATED = "TERMINATED", "Terminated"

    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="contracts")
    reference = models.CharField(max_length=40, blank=True, default="")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PERMANENT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    job_title = models.CharField(max_length=150)
    grade = models.CharField(max_length=50, blank=True, default="")
    step = models.CharField(max_length=20, blank=True, default="")
    department = models.ForeignKey(
        "iam.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reports_to = models.ForeignKey(
        "hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    start_date = models.DateField()
    end_date = models.DateField(
        null=True, blank=True, help_text="Fixed-term only; blank for permanent."
    )
    probation_months = models.PositiveIntegerField(default=3)
    probation_end = models.DateField(null=True, blank=True)
    notice_period_days = models.PositiveIntegerField(
        default=30, help_text="Notice either party must give (Law 66/2018 Art. 24)."
    )
    working_hours_per_week = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("45.00"),
        help_text="Statutory maximum is 45h/week (Law 66/2018 Art. 50).",
    )
    annual_leave_days = models.PositiveIntegerField(
        default=18, help_text="18 working days by default; 21 after 3 years' service."
    )
    is_current = models.BooleanField(default=True)
    signed_on = models.DateField(null=True, blank=True)
    signed_document_url = models.CharField(max_length=255, blank=True, default="")
    terms = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=models.Q(is_current=True),
                name="uniq_current_contract_per_employee",
            )
        ]
        indexes = [models.Index(fields=["employee", "status"])]

    def __str__(self) -> str:
        return f"{self.employee} · {self.kind} from {self.start_date}"

    @property
    def is_expiring(self) -> bool:
        return bool(self.end_date and (self.end_date - date.today()).days <= 60)


class SalaryStructure(models.Model):
    """An effective-dated set of pay components for one employee.

    Payroll resolves the structure in force on the period end, so a mid-year
    raise re-runs correctly and history is never rewritten.
    """

    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.CASCADE, related_name="salary_structures"
    )
    contract = models.ForeignKey(
        EmploymentContract,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="salary_structures",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="RWF")
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "effective_from"], name="uniq_salary_structure_per_date"
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee} salary from {self.effective_from}"

    def covers(self, day: date) -> bool:
        return self.effective_from <= day and (
            self.effective_to is None or day <= self.effective_to
        )

    @property
    def gross(self) -> Decimal:
        return sum((c.amount for c in self.components.all()), ZERO)

    @property
    def pension_base(self) -> Decimal:
        """Gross *including* transport — the RSSB pension base."""
        return sum((c.amount for c in self.components.all() if c.in_pension_base), ZERO)

    @property
    def maternity_base(self) -> Decimal:
        """Gross *excluding* transport — the RSSB maternity base."""
        return sum((c.amount for c in self.components.all() if c.in_maternity_base), ZERO)

    @property
    def taxable_base(self) -> Decimal:
        return sum((c.amount for c in self.components.all() if c.is_taxable), ZERO)


class SalaryComponent(models.Model):
    """One line of pay, with the flags that decide which statutory base it enters.

    These flags are the whole reason the model exists: transport allowance is
    pensionable but not in the maternity base, and a per-diem is neither taxable
    nor contributory.
    """

    class Code(models.TextChoices):
        BASIC = "BASIC", "Basic salary"
        HOUSING = "HOUSING", "Housing allowance"
        TRANSPORT = "TRANSPORT", "Transport allowance"
        RESPONSIBILITY = "RESPONSIBILITY", "Responsibility allowance"
        COMMUNICATION = "COMMUNICATION", "Communication allowance"
        RISK = "RISK", "Risk / hardship allowance"
        ACTING = "ACTING", "Acting allowance"
        PER_DIEM = "PER_DIEM", "Per diem (non-taxable)"
        OTHER = "OTHER", "Other allowance"

    structure = models.ForeignKey(
        SalaryStructure, on_delete=models.CASCADE, related_name="components"
    )
    code = models.CharField(max_length=20, choices=Code.choices, default=Code.BASIC)
    label = models.CharField(max_length=100, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_taxable = models.BooleanField(default=True, help_text="Enters the PAYE base.")
    in_pension_base = models.BooleanField(
        default=True, help_text="Enters the RSSB pension base (gross incl. transport)."
    )
    in_maternity_base = models.BooleanField(
        default=True, help_text="Enters the RSSB maternity base (gross excl. transport)."
    )
    is_prorated = models.BooleanField(
        default=True, help_text="Pro-rated for joiners, leavers and unpaid leave."
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["structure", "code", "label"], name="uniq_salary_component"
            )
        ]

    def __str__(self) -> str:
        return f"{self.label or self.get_code_display()} {self.amount}"


class SalaryRevision(models.Model):
    """An audited change of pay — the paper trail behind a new SalaryStructure."""

    class Reason(models.TextChoices):
        PROMOTION = "PROMOTION", "Promotion"
        ANNUAL_REVIEW = "ANNUAL_REVIEW", "Annual review"
        CONFIRMATION = "CONFIRMATION", "Probation confirmation"
        MARKET_ADJUSTMENT = "MARKET_ADJUSTMENT", "Market adjustment"
        DEMOTION = "DEMOTION", "Demotion"
        CORRECTION = "CORRECTION", "Correction"
        OTHER = "OTHER", "Other"

    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.CASCADE, related_name="salary_revisions"
    )
    previous_structure = models.ForeignKey(
        SalaryStructure, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    new_structure = models.ForeignKey(
        SalaryStructure, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    effective_date = models.DateField()
    reason = models.CharField(max_length=20, choices=Reason.choices, default=Reason.ANNUAL_REVIEW)
    previous_gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    new_gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, default="")
    approved_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date"]

    def __str__(self) -> str:
        return f"{self.employee} {self.previous_gross} → {self.new_gross}"

    @property
    def change_pct(self) -> Decimal:
        if self.previous_gross == 0:
            return ZERO
        return ((self.new_gross - self.previous_gross) * 100 / self.previous_gross).quantize(
            Decimal("0.01")
        )


# ---------------------------------------------------------------------------
# Leave: types, balances, accrual
# ---------------------------------------------------------------------------


class LeaveType(models.Model):
    """A configurable leave category — days, accrual, carry-over and whether it
    is paid (unpaid leave reduces the payroll gross)."""

    class Accrual(models.TextChoices):
        MONTHLY = "MONTHLY", "Accrues monthly"
        ANNUAL = "ANNUAL", "Granted annually up front"
        NONE = "NONE", "No accrual (per-event entitlement)"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="leave_types"
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    days_per_year = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    accrual = models.CharField(max_length=10, choices=Accrual.choices, default=Accrual.MONTHLY)
    is_paid = models.BooleanField(default=True)
    carry_over_max_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    carry_over_expires_months = models.PositiveIntegerField(default=0)
    requires_document = models.BooleanField(
        default=False, help_text="e.g. a medical certificate for sick leave over 3 days."
    )
    max_consecutive_days = models.PositiveIntegerField(default=0, help_text="0 = no cap.")
    min_notice_days = models.PositiveIntegerField(default=0)
    is_encashable = models.BooleanField(
        default=True, help_text="Unused balance is paid out on final settlement."
    )
    gender_restriction = models.CharField(
        max_length=10, blank=True, default="", help_text="Blank, M or F (maternity/paternity)."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization", "name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uniq_leave_type_code")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.days_per_year}d)"


class LeaveBalance(models.Model):
    """An employee's running entitlement for one leave type in one leave year."""

    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.CASCADE, related_name="leave_balances"
    )
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name="balances")
    year = models.PositiveIntegerField()
    opening_balance = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    accrued = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    carried_over = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    taken = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    pending = models.DecimalField(
        max_digits=6, decimal_places=2, default=0, help_text="Requested but not yet approved."
    )
    encashed = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    adjustment = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "leave_type__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "leave_type", "year"], name="uniq_leave_balance"
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee} {self.leave_type.code} {self.year}: {self.available}"

    @property
    def entitled(self) -> Decimal:
        return self.opening_balance + self.accrued + self.carried_over + self.adjustment

    @property
    def available(self) -> Decimal:
        """What can still be booked — pending requests are held, not free."""
        return self.entitled - self.taken - self.pending - self.encashed


class LeaveAccrual(models.Model):
    """One posting into a balance — the audit trail behind ``LeaveBalance``."""

    class Kind(models.TextChoices):
        ACCRUAL = "ACCRUAL", "Periodic accrual"
        CARRY_OVER = "CARRY_OVER", "Carried over from last year"
        GRANT = "GRANT", "Manual grant"
        TAKEN = "TAKEN", "Leave taken"
        ENCASHMENT = "ENCASHMENT", "Encashed"
        FORFEIT = "FORFEIT", "Forfeited (carry-over expiry)"
        ADJUSTMENT = "ADJUSTMENT", "Correction"

    balance = models.ForeignKey(LeaveBalance, on_delete=models.CASCADE, related_name="movements")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.ACCRUAL)
    days = models.DecimalField(max_digits=6, decimal_places=2, help_text="Signed.")
    occurred_on = models.DateField(default=date.today)
    leave_request = models.ForeignKey(
        "hr.LeaveRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movements",
    )
    note = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_on", "-id"]

    def __str__(self) -> str:
        return f"{self.kind} {self.days:+} on {self.occurred_on}"


# ---------------------------------------------------------------------------
# Timesheets
# ---------------------------------------------------------------------------


class Timesheet(models.Model):
    """The approved, calculated view of a period's attendance.

    Payroll reads *this*, never raw punches — and a run cannot be approved while
    a timesheet for the period is still pending (ROADMAP cross-system invariant).
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        LOCKED = "LOCKED", "Locked (payroll run)"

    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="timesheets")
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    days_worked = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    days_absent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    days_on_leave = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    unpaid_leave_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hours_worked = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    hours_rostered = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    night_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    holiday_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    late_count = models.PositiveIntegerField(default=0)
    early_leave_count = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=300, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start", "employee"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "period_start", "period_end"], name="uniq_timesheet_period"
            )
        ]
        indexes = [models.Index(fields=["status", "period_end"])]

    def __str__(self) -> str:
        return f"{self.employee} {self.period_start}–{self.period_end} ({self.status})"

    @property
    def is_editable(self) -> bool:
        return self.status in {self.Status.DRAFT, self.Status.REJECTED}


# ---------------------------------------------------------------------------
# Loans & advances
# ---------------------------------------------------------------------------


class LoanAdvance(models.Model):
    """Money advanced to an employee, repaid by payroll deduction."""

    class Kind(models.TextChoices):
        SALARY_ADVANCE = "SALARY_ADVANCE", "Salary advance"
        EMERGENCY = "EMERGENCY", "Emergency loan"
        EDUCATION = "EDUCATION", "Education loan"
        HOUSING = "HOUSING", "Housing loan"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        ACTIVE = "ACTIVE", "Active (repaying)"
        SETTLED = "SETTLED", "Fully repaid"
        WRITTEN_OFF = "WRITTEN_OFF", "Written off"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    reference = models.CharField(max_length=40, blank=True, default="")
    employee = models.ForeignKey("hr.Employee", on_delete=models.PROTECT, related_name="loans")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SALARY_ADVANCE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    principal = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monthly_installment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    installments_count = models.PositiveIntegerField(default=1)
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=300, blank=True, default="")
    guarantor = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="guaranteed_loans",
    )
    disbursed_on = models.DateField(null=True, blank=True)
    disbursement_method = models.CharField(max_length=20, blank=True, default="")
    disbursement_reference = models.CharField(max_length=100, blank=True, default="")
    approved_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["employee", "status"])]

    def __str__(self) -> str:
        return f"{self.reference or f'LOAN#{self.pk}'} · {self.employee} · {self.balance}"

    @property
    def total_repayable(self) -> Decimal:
        return self.principal + (self.principal * self.interest_rate_pct / Decimal("100"))

    @property
    def repaid(self) -> Decimal:
        return self.total_repayable - self.balance

    @property
    def progress_pct(self) -> Decimal:
        total = self.total_repayable
        if total == 0:
            return ZERO
        return (self.repaid * 100 / total).quantize(Decimal("0.01"))


class LoanInstallment(models.Model):
    """One scheduled repayment. Payroll settles the next due one per run."""

    loan = models.ForeignKey(LoanAdvance, on_delete=models.CASCADE, related_name="installments")
    sequence = models.PositiveIntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    payroll_run = models.ForeignKey(
        "hr.PayrollRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loan_installments",
    )
    skipped_reason = models.CharField(
        max_length=200, blank=True, default="", help_text="e.g. unpaid leave that month."
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["loan", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["loan", "sequence"], name="uniq_loan_installment_seq")
        ]

    def __str__(self) -> str:
        return f"{self.loan} #{self.sequence} due {self.due_date}"

    @property
    def is_overdue(self) -> bool:
        return not self.is_paid and self.due_date < date.today()


class PayrollAdjustment(models.Model):
    """Arrears, back-pay or a correction applied to a *future* run.

    An approved run is immutable, so this is the only way money moves after the
    fact — which is exactly what keeps the payroll register auditable.
    """

    class Kind(models.TextChoices):
        ARREARS = "ARREARS", "Arrears / back-pay"
        BONUS = "BONUS", "Bonus"
        COMMISSION = "COMMISSION", "Commission"
        THIRTEENTH = "THIRTEENTH", "13th cheque"
        DEDUCTION = "DEDUCTION", "Deduction"
        CORRECTION = "CORRECTION", "Correction of a previous run"
        REIMBURSEMENT = "REIMBURSEMENT", "Expense reimbursement"

    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.CASCADE, related_name="payroll_adjustments"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.ARREARS)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Signed: negative for a deduction."
    )
    is_taxable = models.BooleanField(default=True)
    in_pension_base = models.BooleanField(default=False)
    reason = models.CharField(max_length=300, blank=True, default="")
    relates_to_run = models.ForeignKey(
        "hr.PayrollRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="corrections",
    )
    applied_run = models.ForeignKey(
        "hr.PayrollRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="adjustments",
    )
    apply_from = models.DateField(
        default=date.today, help_text="The first run on or after this date picks it up."
    )
    approved_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-apply_from", "-id"]
        indexes = [models.Index(fields=["employee", "applied_run"])]

    def __str__(self) -> str:
        return f"{self.employee} {self.kind} {self.amount:+}"


# ---------------------------------------------------------------------------
# Statutory filings
# ---------------------------------------------------------------------------


class StatutoryFiling(models.Model):
    """A PAYE / RSSB / CBHI / VAT / PIT return for one period.

    Invariant (ROADMAP §9.2): it may not be marked ``FILED_PAID`` unless the
    amount ties to the matching GL sub-ledger balance.
    """

    class Kind(models.TextChoices):
        PAYE_MONTHLY = "PAYE_MONTHLY", "PAYE — monthly (RRA)"
        RSSB_MONTHLY = "RSSB_MONTHLY", "RSSB unified — monthly"
        CBHI_MONTHLY = "CBHI_MONTHLY", "CBHI — monthly"
        VAT_MONTHLY = "VAT_MONTHLY", "VAT — monthly (RRA)"
        WHT_MONTHLY = "WHT_MONTHLY", "Withholding tax — monthly"
        PIT_ANNUAL = "PIT_ANNUAL", "PIT — annual summary"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        GENERATED = "GENERATED", "Generated"
        FILED = "FILED", "Filed"
        FILED_PAID = "FILED_PAID", "Filed & paid"
        REJECTED = "REJECTED", "Rejected by authority"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="statutory_filings"
    )
    reference = models.CharField(max_length=40, blank=True, default="")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    period_start = models.DateField()
    period_end = models.DateField()
    due_date = models.DateField(help_text="PAYE/RSSB: the 15th of the following month.")
    employee_count = models.PositiveIntegerField(default=0)
    gross_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employee_contribution = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employer_contribution = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gl_balance_at_generation = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Sub-ledger balance when generated — must equal amount_due to file.",
    )
    payload = models.JSONField(default=dict, blank=True)
    return_file = models.CharField(max_length=255, blank=True, default="")
    authority_reference = models.CharField(
        max_length=100, blank=True, default="", help_text="RRA/RSSB acknowledgement number."
    )
    filed_on = models.DateField(null=True, blank=True)
    filed_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    tax_payment = models.ForeignKey(
        "finance.TaxPayment", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    rejection_reason = models.CharField(max_length=300, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end", "kind"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "kind", "period_start", "period_end"],
                name="uniq_statutory_filing_period",
            )
        ]
        indexes = [models.Index(fields=["organization", "status", "due_date"])]

    def __str__(self) -> str:
        return f"{self.kind} {self.period_start}–{self.period_end} ({self.status})"

    @property
    def is_overdue(self) -> bool:
        return self.status not in {self.Status.FILED, self.Status.FILED_PAID} and (
            self.due_date < date.today()
        )

    @property
    def ties_to_ledger(self) -> bool:
        return self.amount_due == self.gl_balance_at_generation


# ---------------------------------------------------------------------------
# Recruitment → onboarding
# ---------------------------------------------------------------------------


class JobRequisition(models.Model):
    """A request to fill a role — the start of the hiring funnel."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        OPEN = "OPEN", "Open"
        ON_HOLD = "ON_HOLD", "On hold"
        FILLED = "FILLED", "Filled"
        CANCELLED = "CANCELLED", "Cancelled"

    reference = models.CharField(max_length=40, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="job_requisitions"
    )
    department = models.ForeignKey(
        "iam.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    job_title = models.CharField(max_length=150)
    headcount = models.PositiveIntegerField(default=1)
    headcount_filled = models.PositiveIntegerField(default=0)
    employment_type = models.CharField(max_length=20, default="FULL_TIME")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_replacement = models.BooleanField(default=False)
    replaces = models.ForeignKey(
        "hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    hiring_manager = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requisitions",
    )
    budget_min = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_max = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    requires_licence = models.BooleanField(
        default=False, help_text="Pharmacist/technician roles need a valid NPC licence."
    )
    job_description = models.TextField(blank=True, default="")
    requirements = models.TextField(blank=True, default="")
    opened_at = models.DateField(null=True, blank=True)
    closes_at = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"{self.reference or f'REQ#{self.pk}'} · {self.job_title}"

    @property
    def vacancies_left(self) -> int:
        return max(0, self.headcount - self.headcount_filled)


class Applicant(models.Model):
    """Someone in the funnel for a requisition."""

    class Stage(models.TextChoices):
        APPLIED = "APPLIED", "Applied"
        SCREENED = "SCREENED", "Screened"
        SHORTLISTED = "SHORTLISTED", "Shortlisted"
        INTERVIEWED = "INTERVIEWED", "Interviewed"
        OFFERED = "OFFERED", "Offered"
        HIRED = "HIRED", "Hired"
        REJECTED = "REJECTED", "Rejected"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    requisition = models.ForeignKey(
        JobRequisition, on_delete=models.CASCADE, related_name="applicants"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    national_id = models.CharField(max_length=30, blank=True, default="")
    gender = models.CharField(max_length=10, blank=True, default="")
    stage = models.CharField(max_length=15, choices=Stage.choices, default=Stage.APPLIED)
    source = models.CharField(
        max_length=50, blank=True, default="", help_text="Referral, job board, walk-in…"
    )
    years_experience = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    highest_qualification = models.CharField(max_length=150, blank=True, default="")
    licence_number = models.CharField(max_length=100, blank=True, default="")
    cv_url = models.CharField(max_length=255, blank=True, default="")
    cover_letter_url = models.CharField(max_length=255, blank=True, default="")
    expected_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    offered_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    offer_sent_on = models.DateField(null=True, blank=True)
    offer_accepted_on = models.DateField(null=True, blank=True)
    proposed_start_date = models.DateField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=300, blank=True, default="")
    hired_employee = models.ForeignKey(
        "hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["requisition", "-created_at"]
        indexes = [models.Index(fields=["requisition", "stage"])]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.stage})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class InterviewSlot(models.Model):
    """A scheduled interview and its outcome."""

    class Decision(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ADVANCE = "ADVANCE", "Advance"
        HOLD = "HOLD", "Hold"
        REJECT = "REJECT", "Reject"

    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="interviews")
    round_number = models.PositiveIntegerField(default=1)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=45)
    mode = models.CharField(max_length=20, blank=True, default="IN_PERSON")
    location = models.CharField(max_length=200, blank=True, default="")
    panel = models.ManyToManyField("hr.Employee", blank=True, related_name="interview_panels")
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    decision = models.CharField(max_length=10, choices=Decision.choices, default=Decision.PENDING)
    feedback = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["applicant", "round_number"]

    def __str__(self) -> str:
        return f"{self.applicant} round {self.round_number}"


class OnboardingChecklist(models.Model):
    """The induction a new hire must complete before they are fully live."""

    employee = models.OneToOneField(
        "hr.Employee", on_delete=models.CASCADE, related_name="onboarding"
    )
    template = models.CharField(max_length=100, blank=True, default="")
    started_on = models.DateField(default=date.today)
    target_completion = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    owner = models.ForeignKey(
        "hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_on"]

    def __str__(self) -> str:
        return f"Onboarding · {self.employee}"

    @property
    def progress_pct(self) -> Decimal:
        items = list(self.items.all())
        if not items:
            return ZERO
        done = sum(1 for i in items if i.is_done)
        return (Decimal(done) * 100 / Decimal(len(items))).quantize(Decimal("0.01"))


class ChecklistItem(models.Model):
    """One task on an onboarding or clearance checklist."""

    class Phase(models.TextChoices):
        ONBOARDING = "ONBOARDING", "Onboarding"
        CLEARANCE = "CLEARANCE", "Offboarding clearance"

    class Category(models.TextChoices):
        DOCUMENT = "DOCUMENT", "Document"
        ASSET = "ASSET", "Asset / equipment"
        ACCESS = "ACCESS", "System access"
        TRAINING = "TRAINING", "Training / SOP"
        COMPLIANCE = "COMPLIANCE", "Licence / compliance"
        FINANCE = "FINANCE", "Finance"
        OTHER = "OTHER", "Other"

    onboarding = models.ForeignKey(
        OnboardingChecklist, null=True, blank=True, on_delete=models.CASCADE, related_name="items"
    )
    termination = models.ForeignKey(
        "hr.Termination", null=True, blank=True, on_delete=models.CASCADE, related_name="items"
    )
    phase = models.CharField(max_length=12, choices=Phase.choices, default=Phase.ONBOARDING)
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.DOCUMENT)
    label = models.CharField(max_length=200)
    is_mandatory = models.BooleanField(default=True)
    is_done = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    evidence_url = models.CharField(max_length=255, blank=True, default="")
    note = models.CharField(max_length=255, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.label} ({'done' if self.is_done else 'open'})"


# ---------------------------------------------------------------------------
# Offboarding
# ---------------------------------------------------------------------------


class Termination(models.Model):
    """The end of employment, its clearance, and the money owed.

    Invariant: an employee cannot be terminated while an open payroll run still
    references them.
    """

    class Reason(models.TextChoices):
        RESIGNATION = "RESIGNATION", "Resignation"
        CONTRACT_END = "CONTRACT_END", "End of fixed-term contract"
        DISMISSAL = "DISMISSAL", "Dismissal (misconduct)"
        REDUNDANCY = "REDUNDANCY", "Redundancy"
        RETIREMENT = "RETIREMENT", "Retirement"
        MUTUAL = "MUTUAL", "Mutual agreement"
        DEATH = "DEATH", "Death in service"
        PROBATION_FAIL = "PROBATION_FAIL", "Failed probation"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        CLEARED = "CLEARED", "Cleared"
        SETTLED = "SETTLED", "Settled & closed"
        CANCELLED = "CANCELLED", "Cancelled"

    employee = models.OneToOneField(
        "hr.Employee", on_delete=models.CASCADE, related_name="termination"
    )
    reason = models.CharField(max_length=20, choices=Reason.choices, default=Reason.RESIGNATION)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notice_given_on = models.DateField(null=True, blank=True)
    last_working_day = models.DateField()
    notice_period_served = models.BooleanField(default=True)
    notice_pay_in_lieu = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_eligible_for_rehire = models.BooleanField(default=True)
    exit_interview_done = models.BooleanField(default=False)
    exit_interview_notes = models.TextField(blank=True, default="")
    handover_to = models.ForeignKey(
        "hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    certificate_of_service_url = models.CharField(max_length=255, blank=True, default="")
    detail = models.TextField(blank=True, default="")
    initiated_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_working_day"]

    def __str__(self) -> str:
        return f"{self.employee} · {self.reason} on {self.last_working_day}"

    @property
    def clearance_pct(self) -> Decimal:
        items = list(self.items.all())
        if not items:
            return ZERO
        done = sum(1 for i in items if i.is_done)
        return (Decimal(done) * 100 / Decimal(len(items))).quantize(Decimal("0.01"))


class FinalSettlement(models.Model):
    """What is owed on exit — leave encashment, pro-rata pay, dues, less loans."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved"
        PAID = "PAID", "Paid"

    termination = models.OneToOneField(
        Termination, on_delete=models.CASCADE, related_name="settlement"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    computed_on = models.DateField(default=date.today)
    pro_rata_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    leave_days_encashed = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    leave_encashment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notice_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    severance_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_dues = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paye = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_on = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, blank=True, default="")
    payment_reference = models.CharField(max_length=100, blank=True, default="")
    approved_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-computed_on"]

    def __str__(self) -> str:
        return f"Final settlement · {self.termination.employee} · {self.net_payable}"

    @property
    def gross_dues(self) -> Decimal:
        return (
            self.pro_rata_salary
            + self.leave_encashment
            + self.notice_pay
            + self.severance_pay
            + self.other_dues
        )

    @property
    def total_deductions(self) -> Decimal:
        return self.loan_recovery + self.advance_recovery + self.paye + self.other_deductions


# ---------------------------------------------------------------------------
# Training, CPD, competency, discipline, performance
# ---------------------------------------------------------------------------


class TrainingRecord(models.Model):
    """A course or SOP an employee has completed."""

    class Kind(models.TextChoices):
        SOP = "SOP", "SOP acknowledgement"
        INDUCTION = "INDUCTION", "Induction"
        TECHNICAL = "TECHNICAL", "Technical / clinical"
        COMPLIANCE = "COMPLIANCE", "Compliance (GDP, data protection)"
        SAFETY = "SAFETY", "Health & safety"
        SOFT_SKILLS = "SOFT_SKILLS", "Soft skills"
        EXTERNAL = "EXTERNAL", "External course"

    class Status(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        EXPIRED = "EXPIRED", "Expired — needs refresh"
        FAILED = "FAILED", "Failed"

    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.CASCADE, related_name="training_records"
    )
    course_name = models.CharField(max_length=200)
    kind = models.CharField(max_length=15, choices=Kind.choices, default=Kind.TECHNICAL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ASSIGNED)
    provider = models.CharField(max_length=150, blank=True, default="")
    is_mandatory = models.BooleanField(default=False)
    assigned_on = models.DateField(default=date.today)
    due_on = models.DateField(null=True, blank=True)
    completed_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(
        null=True, blank=True, help_text="Refresher due date for recurring training."
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    certificate_number = models.CharField(max_length=100, blank=True, default="")
    certificate_url = models.CharField(max_length=255, blank=True, default="")
    acknowledged_at = models.DateTimeField(
        null=True, blank=True, help_text="For SOP assign-and-acknowledge."
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_on"]
        indexes = [models.Index(fields=["employee", "status"])]

    def __str__(self) -> str:
        return f"{self.employee} · {self.course_name}"

    @property
    def is_overdue(self) -> bool:
        return (
            self.status in {self.Status.ASSIGNED, self.Status.IN_PROGRESS}
            and self.due_on is not None
            and self.due_on < date.today()
        )


class CPDRecord(models.Model):
    """Continuing professional development hours — required to renew an NPC licence."""

    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.CASCADE, related_name="cpd_records"
    )
    activity = models.CharField(max_length=200)
    activity_date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    provider = models.CharField(max_length=150, blank=True, default="")
    cpd_year = models.PositiveIntegerField(default=date.today().year)
    is_accredited = models.BooleanField(default=True)
    accreditation_body = models.CharField(max_length=150, blank=True, default="")
    evidence_url = models.CharField(max_length=255, blank=True, default="")
    verified_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-activity_date"]
        indexes = [models.Index(fields=["employee", "cpd_year"])]

    def __str__(self) -> str:
        return f"{self.employee} · {self.activity} ({self.hours}h)"


class CompetencyAssessment(models.Model):
    """A periodic check that someone is still competent to do a regulated task.

    ``CONTROLLED_DRUG_HANDLING`` is the one that bites: it gates the
    dispense-controlled permission, and it expires.
    """

    class Competency(models.TextChoices):
        DISPENSING = "DISPENSING", "Dispensing"
        CONTROLLED_DRUG_HANDLING = "CONTROLLED_DRUG_HANDLING", "Controlled-drug handling"
        COLD_CHAIN = "COLD_CHAIN", "Cold-chain handling"
        COUNSELLING = "COUNSELLING", "Patient counselling"
        CASH_HANDLING = "CASH_HANDLING", "Cash handling"
        RECEIVING = "RECEIVING", "Goods receiving & QC"
        VACCINATION = "VACCINATION", "Vaccination / injection"

    class Result(models.TextChoices):
        COMPETENT = "COMPETENT", "Competent"
        NEEDS_SUPERVISION = "NEEDS_SUPERVISION", "Competent under supervision"
        NOT_COMPETENT = "NOT_COMPETENT", "Not yet competent"

    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.CASCADE, related_name="competencies"
    )
    competency = models.CharField(max_length=30, choices=Competency.choices)
    result = models.CharField(max_length=20, choices=Result.choices, default=Result.COMPETENT)
    assessed_on = models.DateField(default=date.today)
    valid_until = models.DateField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    assessor = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assessments_given",
    )
    evidence_url = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assessed_on"]
        indexes = [models.Index(fields=["employee", "competency"])]

    def __str__(self) -> str:
        return f"{self.employee} · {self.competency} ({self.result})"

    @property
    def is_valid(self) -> bool:
        if self.result == self.Result.NOT_COMPETENT:
            return False
        return self.valid_until is None or self.valid_until >= date.today()


class DisciplinaryAction(models.Model):
    """A formal disciplinary step, with the right of reply the Labour Code requires."""

    class Kind(models.TextChoices):
        VERBAL = "VERBAL", "Verbal warning"
        WRITTEN = "WRITTEN", "Written warning"
        FINAL = "FINAL", "Final written warning"
        SUSPENSION = "SUSPENSION", "Suspension"
        DEMOTION = "DEMOTION", "Demotion"
        DISMISSAL = "DISMISSAL", "Dismissal"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ISSUED = "ISSUED", "Issued"
        APPEALED = "APPEALED", "Under appeal"
        UPHELD = "UPHELD", "Upheld"
        OVERTURNED = "OVERTURNED", "Overturned"
        EXPIRED = "EXPIRED", "Expired from record"

    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.CASCADE, related_name="disciplinary_actions"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.VERBAL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    incident_date = models.DateField()
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(
        null=True, blank=True, help_text="When the warning drops off the record."
    )
    reason = models.TextField()
    employee_response = models.TextField(blank=True, default="")
    responded_at = models.DateTimeField(null=True, blank=True)
    suspension_start = models.DateField(null=True, blank=True)
    suspension_end = models.DateField(null=True, blank=True)
    is_suspension_paid = models.BooleanField(default=True)
    document_url = models.CharField(max_length=255, blank=True, default="")
    issued_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-incident_date"]
        indexes = [models.Index(fields=["employee", "status"])]

    def __str__(self) -> str:
        return f"{self.employee} · {self.kind} ({self.incident_date})"

    @property
    def is_live(self) -> bool:
        return self.status in {self.Status.ISSUED, self.Status.UPHELD} and (
            self.expires_on is None or self.expires_on >= date.today()
        )


class PerformanceReview(models.Model):
    """A review cycle: goals, rating, and the employee's acknowledgement."""

    class Kind(models.TextChoices):
        PROBATION = "PROBATION", "Probation review"
        QUARTERLY = "QUARTERLY", "Quarterly"
        MID_YEAR = "MID_YEAR", "Mid-year"
        ANNUAL = "ANNUAL", "Annual"
        PIP = "PIP", "Performance improvement plan"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SELF_ASSESSMENT = "SELF_ASSESSMENT", "Awaiting self-assessment"
        MANAGER_REVIEW = "MANAGER_REVIEW", "Awaiting manager review"
        AWAITING_ACK = "AWAITING_ACK", "Awaiting acknowledgement"
        COMPLETED = "COMPLETED", "Completed"

    class Rating(models.TextChoices):
        OUTSTANDING = "OUTSTANDING", "Outstanding"
        EXCEEDS = "EXCEEDS", "Exceeds expectations"
        MEETS = "MEETS", "Meets expectations"
        PARTIAL = "PARTIAL", "Partially meets"
        BELOW = "BELOW", "Below expectations"

    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.CASCADE, related_name="performance_reviews"
    )
    reviewer = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviews_given",
    )
    kind = models.CharField(max_length=15, choices=Kind.choices, default=Kind.ANNUAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    period_start = models.DateField()
    period_end = models.DateField()
    rating = models.CharField(max_length=15, choices=Rating.choices, blank=True, default="")
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    goals = models.JSONField(
        default=list, blank=True, help_text="[{goal, weight, target, achieved, score}]"
    )
    strengths = models.TextField(blank=True, default="")
    development_areas = models.TextField(blank=True, default="")
    self_assessment = models.TextField(blank=True, default="")
    manager_comments = models.TextField(blank=True, default="")
    employee_comments = models.TextField(blank=True, default="")
    training_recommended = models.TextField(blank=True, default="")
    salary_action_recommended = models.CharField(max_length=100, blank=True, default="")
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "kind", "period_start", "period_end"],
                name="uniq_performance_review_period",
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee} · {self.kind} {self.period_start}–{self.period_end}"
