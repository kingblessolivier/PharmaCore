"""HR foundation: the Employee master everything else (attendance, leave, payroll,
licences) hangs off. See ROADMAP.md "10. People (HR & payroll)" (Phase 9) and
docs/02-data-model.md §9 / docs/12-requirements-fields-documents-approvals.md §3.
"""

from __future__ import annotations

from django.db import models


class Employee(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full time"
        PART_TIME = "PART_TIME", "Part time"
        CONTRACT = "CONTRACT", "Contract"

    class Status(models.TextChoices):
        PROBATION = "PROBATION", "Probation"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        TERMINATED = "TERMINATED", "Terminated"

    # The staff login (PF/staff number lives on User) — optional, since an
    # employee record may be opened before an account is provisioned.
    user = models.OneToOneField(
        "iam.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee_profile",
    )
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="employees"
    )
    department = models.ForeignKey(
        "iam.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="employees"
    )
    employee_number = models.CharField(max_length=30, blank=True, default="", db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    national_id = models.CharField(max_length=30, blank=True, default="")
    job_title = models.CharField(max_length=100, blank=True, default="")
    employment_type = models.CharField(
        max_length=20, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME
    )
    employment_status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROBATION
    )
    hire_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bank_account = models.CharField(max_length=50, blank=True, default="")
    momo_number = models.CharField(max_length=20, blank=True, default="")
    rssb_number = models.CharField(max_length=30, blank=True, default="")
    # ---- Finacle-grade R/O/C fields for the People module ----
    # Personal / identity
    gender = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="M / F / Other — used for headcount reporting and pension scheme flags.",
    )
    dob = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Date of birth — drives annual-leave entitlement " "(Law 66/2018 §55: 25 days if ≥55y)."
        ),
    )
    photo = models.URLField(
        blank=True,
        default="",
        help_text="URL of the employee's profile photo (badge).",
    )
    # Contract lifecycle
    probation_end = models.DateField(
        null=True,
        blank=True,
        help_text="Last day of the probation period (auto-confirmation trigger).",
    )
    contract_end = models.DateField(
        null=True,
        blank=True,
        help_text="End date of a fixed-term contract (CDD); blank for permanent (CDI).",
    )
    # Payroll classification
    pay_group = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text=(
            "Salary band — pharmacist, technician, cashier, driver, manager. "
            "Drives default salary structure."
        ),
    )
    pay_frequency = models.CharField(
        max_length=10,
        blank=True,
        default="MONTHLY",
        help_text="Pay period — MONTHLY (Law 66/2018 default) or FORTNIGHTLY.",
    )
    tin = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="RRA TIN — Rwanda tax-identification number; printed on annual PIT summaries.",
    )
    supervisor = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reports",
        help_text="Direct manager — used by the approvals engine for leave / loan routing.",
    )
    # Professional licence driving dispensing rights (pharmacist/technician).
    license = models.ForeignKey(
        "iam.License", null=True, blank=True, on_delete=models.SET_NULL, related_name="employees"
    )
    next_of_kin_name = models.CharField(max_length=150, blank=True, default="")
    next_of_kin_relation = models.CharField(max_length=50, blank=True, default="")
    next_of_kin_phone = models.CharField(max_length=20, blank=True, default="")
    emergency_contact_phone = models.CharField(max_length=20, blank=True, default="")
    address = models.TextField(blank=True, default="")

    # ---- Personal (completes the statutory + payroll field set) ----
    middle_name = models.CharField(max_length=100, blank=True, default="")
    marital_status = models.CharField(
        max_length=12,
        blank=True,
        default="",
        help_text="SINGLE / MARRIED / DIVORCED / WIDOWED — reported on RSSB declarations.",
    )
    dependants_count = models.PositiveIntegerField(
        default=0, help_text="Declared dependants — drives CBHI household cover."
    )
    nationality = models.CharField(max_length=60, blank=True, default="Rwandan")
    personal_email = models.EmailField(
        blank=True, default="", help_text="Where the payslip goes after offboarding."
    )
    personal_phone = models.CharField(max_length=20, blank=True, default="")
    district = models.CharField(max_length=100, blank=True, default="")
    sector = models.CharField(max_length=100, blank=True, default="")
    cell = models.CharField(max_length=100, blank=True, default="")
    village = models.CharField(max_length=100, blank=True, default="")
    has_disability = models.BooleanField(default=False)
    disability_note = models.CharField(max_length=200, blank=True, default="")

    # ---- Right to work (non-Rwandan staff) ----
    work_permit_number = models.CharField(max_length=60, blank=True, default="")
    work_permit_expiry = models.DateField(
        null=True, blank=True, help_text="Blocks roster assignment once past."
    )
    passport_number = models.CharField(max_length=40, blank=True, default="")

    # ---- Statutory & settlement ----
    rama_number = models.CharField(
        max_length=30, blank=True, default="", help_text="RAMA medical scheme member number."
    )
    cbhi_number = models.CharField(max_length=30, blank=True, default="")
    is_rama_member = models.BooleanField(
        default=False, help_text="Opts the employee into the 7.5%+7.5% RAMA deduction on basic."
    )
    bank_name = models.CharField(max_length=150, blank=True, default="")
    bank_branch = models.CharField(max_length=150, blank=True, default="")
    bank_account_name = models.CharField(max_length=150, blank=True, default="")
    payment_method = models.CharField(
        max_length=15, blank=True, default="BANK", help_text="BANK / MOMO / CASH."
    )

    # ---- Exit (mirrors the Termination record for quick reads) ----
    termination_reason = models.CharField(max_length=30, blank=True, default="")
    is_eligible_for_rehire = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["national_id"],
                condition=models.Q(national_id__gt=""),
                name="uniq_employee_national_id_when_set",
            ),
            models.UniqueConstraint(
                fields=["employee_number"],
                condition=models.Q(employee_number__gt=""),
                name="uniq_employee_number_when_set",
            ),
        ]
        indexes = [models.Index(fields=["organization", "employment_status"])]

    def __str__(self) -> str:
        return f"{self.employee_number} · {self.first_name} {self.last_name}"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class EmployeeDocument(models.Model):
    class DocType(models.TextChoices):
        NATIONAL_ID = "NATIONAL_ID", "National ID / passport"
        PROFESSIONAL_LICENSE = "PROFESSIONAL_LICENSE", "Professional licence"
        ACADEMIC_CERTIFICATE = "ACADEMIC_CERTIFICATE", "Academic certificate"
        EMPLOYMENT_CONTRACT = "EMPLOYMENT_CONTRACT", "Signed employment contract"
        POLICE_CLEARANCE = "POLICE_CLEARANCE", "Police clearance"
        MEDICAL_FITNESS = "MEDICAL_FITNESS", "Medical fitness certificate"
        BANK_PROOF = "BANK_PROOF", "Bank / MoMo proof"
        OTHER = "OTHER", "Other"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=30, choices=DocType.choices)
    document_url = models.URLField(blank=True, default="")
    uploaded_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.employee} · {self.doc_type}"


class StatutoryRate(models.Model):
    """Versioned, effective-dated statutory rate config the payroll engine reads
    from — never hardcoded — so rates match the books when law changes. See
    docs/18-rwanda-integrations-and-statutory.md §3 (PAYE/RSSB/CBHI)."""

    class RateType(models.TextChoices):
        PAYE_BRACKET = "PAYE_BRACKET", "PAYE bracket"
        PENSION_EMPLOYEE = "PENSION_EMPLOYEE", "RSSB pension (employee)"
        PENSION_EMPLOYER = "PENSION_EMPLOYER", "RSSB pension (employer)"
        MATERNITY_EMPLOYEE = "MATERNITY_EMPLOYEE", "Maternity leave (employee)"
        MATERNITY_EMPLOYER = "MATERNITY_EMPLOYER", "Maternity leave (employer)"
        CBHI = "CBHI", "Community-based health insurance"
        OCCUPATIONAL_HAZARD = "OCCUPATIONAL_HAZARD", "Occupational hazard (employer)"

    country = models.CharField(max_length=2, default="RW")
    rate_type = models.CharField(max_length=30, choices=RateType.choices)
    # For PAYE_BRACKET: the progressive band this row covers (band_max null = open-ended top band).
    band_min = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    band_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    rate_pct = models.DecimalField(max_digits=5, decimal_places=3)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["rate_type", "band_min"]
        indexes = [models.Index(fields=["rate_type", "effective_from"])]

    def __str__(self) -> str:
        return f"{self.rate_type} {self.rate_pct}% from {self.effective_from}"


class PayrollRun(models.Model):
    """One payroll period for one organization. Journeys DRAFT → PENDING_APPROVAL
    (routed through the approvals engine, no self-approval) → APPROVED → PAID."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        PAID = "PAID", "Paid"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="payroll_runs"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-period_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "period_start", "period_end"],
                name="uniq_payroll_period_per_org",
            )
        ]

    def __str__(self) -> str:
        return f"Payroll {self.organization} {self.period_start}–{self.period_end}"


class PayrollRecord(models.Model):
    """One employee's computed payslip line within a PayrollRun. Immutable once the
    run is approved — a correction reprocesses via a new run, never an edit."""

    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="records")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payroll_records")
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shift_premium = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paye = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pension_employee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pension_employer = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maternity_employee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maternity_employer = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cbhi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loans_advances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payslip_document_id = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["employee"]
        constraints = [
            models.UniqueConstraint(fields=["run", "employee"], name="uniq_payroll_record_per_run")
        ]

    def __str__(self) -> str:
        return f"{self.employee} · {self.run}"


class AttendanceLog(models.Model):
    """Employee Clock-In / Clock-Out & Overtime tracking. ROADMAP '10. People'."""

    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        LATE = "LATE", "Late arrival"
        ABSENT = "ABSENT", "Absent"
        ON_LEAVE = "ON_LEAVE", "On approved leave"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_logs")
    date = models.DateField()
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"], name="uniq_attendance_per_employee_day"
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee} · {self.date} ({self.status})"


class ShiftRoster(models.Model):
    """Credential-based shift scheduling with a mandatory pharmacist coverage guard.

    ROADMAP '10. People'.
    """

    class ShiftType(models.TextChoices):
        MORNING = "MORNING", "Morning shift (07:00 – 15:00)"
        EVENING = "EVENING", "Evening shift (15:00 – 23:00)"
        NIGHT = "NIGHT", "Night shift (23:00 – 07:00)"
        FULL_DAY = "FULL_DAY", "Full day (08:00 – 17:00)"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="shift_rosters"
    )
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="shift_rosters")
    date = models.DateField()
    shift_type = models.CharField(
        max_length=20, choices=ShiftType.choices, default=ShiftType.FULL_DAY
    )
    requires_pharmacist_license = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "shift_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "employee", "date"], name="uniq_shift_roster"
            )
        ]

    def __str__(self) -> str:
        return f"{self.date} · {self.shift_type} · {self.employee}"


class LeaveRequest(models.Model):
    """Employee Leave Request & Accrual Engine. ROADMAP '10. People'."""

    class LeaveType(models.TextChoices):
        ANNUAL = "ANNUAL", "Annual leave"
        SICK = "SICK", "Sick leave"
        MATERNITY = "MATERNITY", "Maternity leave"
        PATERNITY = "PATERNITY", "Paternity leave"
        CASUAL = "CASUAL", "Casual leave"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(
        max_length=20, choices=LeaveType.choices, default=LeaveType.ANNUAL
    )
    start_date = models.DateField()
    end_date = models.DateField()
    days_count = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reason = models.TextField(blank=True, default="")
    approved_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.employee} · {self.leave_type} ({self.days_count} days)"


# ---------------------------------------------------------------------------
# The rest of the People model lives in models_people.py so this module stays
# readable. They are ordinary `hr` models — Django resolves the app label from
# the package path — and are re-exported here so `from apps.hr.models import X`
# keeps working everywhere.
# ---------------------------------------------------------------------------

from apps.hr.models_people import (  # noqa: E402,F401
    Applicant,
    ChecklistItem,
    CompetencyAssessment,
    CPDRecord,
    DisciplinaryAction,
    EmploymentContract,
    FinalSettlement,
    InterviewSlot,
    JobRequisition,
    LeaveAccrual,
    LeaveBalance,
    LeaveType,
    LoanAdvance,
    LoanInstallment,
    OnboardingChecklist,
    PayrollAdjustment,
    PerformanceReview,
    SalaryComponent,
    SalaryRevision,
    SalaryStructure,
    StatutoryFiling,
    Termination,
    Timesheet,
    TrainingRecord,
)
