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
    # Professional licence driving dispensing rights (pharmacist/technician).
    license = models.ForeignKey(
        "iam.License", null=True, blank=True, on_delete=models.SET_NULL, related_name="employees"
    )
    next_of_kin_name = models.CharField(max_length=150, blank=True, default="")
    next_of_kin_relation = models.CharField(max_length=50, blank=True, default="")
    next_of_kin_phone = models.CharField(max_length=20, blank=True, default="")
    emergency_contact_phone = models.CharField(max_length=20, blank=True, default="")
    address = models.TextField(blank=True, default="")
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
