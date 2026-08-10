"""Identity & Access models: User, Role, and the append-only AuditLog.

Phase 0 foundation. Organization/department scoping and licenses arrive in Phase 1
(see docs/02-data-model.md); the FKs are intentionally deferred to keep this slice
focused on auth + base RBAC + audit.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Permission(models.Model):
    """A single grantable capability = ``resource`` × ``action`` (e.g. ``sale.void``).

    Roles are bundles of permissions; access checks are per-permission (not per-role
    name), so a pharmacy can re-shape what a role may do without touching code.
    """

    resource = models.CharField(max_length=40)  # e.g. "sale", "order", "user"
    action = models.CharField(max_length=40)  # e.g. "create", "approve", "manage"
    code = models.CharField(max_length=80, unique=True)  # "<resource>.<action>"
    description = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["resource", "action"]
        constraints = [
            models.UniqueConstraint(fields=["resource", "action"], name="uniq_resource_action")
        ]

    def __str__(self) -> str:
        return self.code


class Role(models.Model):
    """A named role users can hold. A role is a **bundle of permissions**."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)
    # Authority limit (apps/iam/authority.py R2) — how much money someone holding
    # this role may approve. Competence and limit are deliberately separate: a
    # branch manager and a group accountant may both hold ``finance.manage`` and
    # only one of them can sign off forty million francs. Null means no ceiling.
    approval_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Default approval ceiling in RWF for this role. "
            "Empty means unlimited — reserve that for SYS_ADMIN."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class Company(models.Model):
    """The legal business entity that owns one or more `Organization`s (branches /
    premises). A solo pharmacy is a Company with a single Organization; a chain is a
    Company with an HQ + several branch Organizations. Optional — an Organization may
    stand alone with no Company (the pre-existing single-tenant shape)."""

    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True, default="")
    tin = models.CharField(max_length=20, blank=True, default="")  # RRA taxpayer id
    registration_number = models.CharField(max_length=100, blank=True, default="")  # RDB
    contact_person = models.CharField(max_length=150, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    logo_url = models.CharField(max_length=500, blank=True, default="")
    currency = models.CharField(max_length=3, default="RWF")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return self.name


class Organization(models.Model):
    """A depot, retail pharmacy, or HQ — the multi-tenant root everything scopes by."""

    class OrgType(models.TextChoices):
        DEPOT = "DEPOT", "Depot"
        RETAIL = "RETAIL", "Retail"
        HQ = "HQ", "HQ"

    company = models.ForeignKey(
        Company, null=True, blank=True, on_delete=models.PROTECT, related_name="branches"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=OrgType.choices)
    tin = models.CharField(max_length=20, blank=True, default="")  # RRA taxpayer id
    registration_number = models.CharField(
        max_length=100, blank=True, default=""
    )  # RDB company reg
    rwanda_fda_license_no = models.CharField(max_length=100, blank=True, default="")
    license_expiry_date = models.DateField(null=True, blank=True)
    contact_person = models.CharField(max_length=150, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    logo_url = models.CharField(max_length=500, blank=True, default="")
    currency = models.CharField(max_length=3, default="RWF")
    # Rwanda administrative hierarchy: Province › District › Sector › Cell › Village.
    province = models.CharField(max_length=100, blank=True, default="")
    district = models.CharField(max_length=100, blank=True, default="")
    sector = models.CharField(max_length=100, blank=True, default="")
    cell = models.CharField(max_length=100, blank=True, default="")
    village = models.CharField(max_length=100, blank=True, default="")
    address_line = models.TextField(blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Onboarding lifecycle: a new pharmacy is DRAFT while its licences/documents are
    # captured, PENDING_REVIEW once submitted, ACTIVE once verified (the activation
    # gate), or SUSPENDED. Existing orgs default to ACTIVE.
    class OnboardingStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_REVIEW = "PENDING_REVIEW", "Pending review"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"

    onboarding_status = models.CharField(
        max_length=20, choices=OnboardingStatus.choices, default=OnboardingStatus.ACTIVE
    )

    # --- Per-tenant settings, plan & branding ---
    class Plan(models.TextChoices):
        BASIC = "BASIC", "Basic"
        STANDARD = "STANDARD", "Standard"
        PREMIUM = "PREMIUM", "Premium"
        ENTERPRISE = "ENTERPRISE", "Enterprise"

    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.STANDARD)

    class Size(models.TextChoices):
        """How the place is actually staffed — which is not the same as how big it is.

        Most Rwandan community pharmacies are not departmental. One person, or
        two, does the selling, the ordering, the receiving, the cash and the
        books. A system that offers them a Procurement Department and a Finance
        Department is not merely over-featured — it is describing an
        organisation that does not exist, and every screen then asks them to
        pretend.

        This is deliberately about *responsibilities*, not headcount alone or
        revenue. The database, the workflow engine and the permission model are
        the same at every size; this decides how much of them a person is shown
        and how many people a control can reasonably demand.
        """

        MICRO = "MICRO", "One or two people, doing everything"
        SMALL = "SMALL", "A handful of people, roles overlap"
        MEDIUM = "MEDIUM", "Distinct roles, one site"
        ENTERPRISE = "ENTERPRISE", "Departments across sites"

    size = models.CharField(
        max_length=12,
        choices=Size.choices,
        default=Size.MICRO,
        help_text=(
            "How this pharmacy is staffed. Drives navigation, the home screen, and "
            "how many people an approval can require — never what the system can do."
        ),
    )

    #: Whether this pharmacy is registered for VAT with the RRA.
    #:
    #: Registration is compulsory above RWF 20,000,000 of turnover in twelve
    #: months, or RWF 5,000,000 in the preceding quarter. Below that a pharmacy
    #: is **not** VAT-registered and must not charge VAT — the 18% belongs to
    #: nobody, and adding it to a paracetamol both overcharges the customer and
    #: creates a liability the pharmacy never owed.
    #:
    #: Every sale line took its rate from the product's tax class alone, so
    #: every pharmacy in the system charged VAT whether or not it was registered
    #: to. Most Rwandan community pharmacies are under the threshold, so for
    #: most of them the till was wrong on every line.
    #:
    #: Defaults to False, which is the true state of a pharmacy that has not
    #: said otherwise. Registering is a thing somebody does deliberately, with a
    #: certificate; assuming it silently is how the wrong default gets applied
    #: to the many in order to suit the few.
    is_vat_registered = models.BooleanField(
        default=False,
        help_text=(
            "Registered for VAT with the RRA. Compulsory above RWF 20M turnover in "
            "12 months, or RWF 5M in the preceding quarter. When off, no VAT is "
            "charged at the till and no VAT appears on an invoice."
        ),
    )
    vat_registration_no = models.CharField(max_length=30, blank=True, default="")

    @property
    def is_single_handed(self) -> bool:
        """One person carries every responsibility here.

        The consequence that matters: a control which requires a *second person*
        cannot be satisfied, so demanding one does not make the pharmacy safer,
        it makes the pharmacy unable to trade. What remains meaningful at this
        size is the record — see `apps.approvals.services.decide`.
        """
        return self.size == Organization.Size.MICRO

    # Primary brand colour (hex, e.g. "#0D9488") — logo_url above is the brand mark.
    brand_color = models.CharField(max_length=9, blank=True, default="")
    # Per-tenant feature toggles, e.g. {"online_store": true, "insurance": false}.
    feature_flags = models.JSONField(default=dict, blank=True)

    #: Whether quarantine release *refuses* without a verified Certificate of
    #: Analysis, or releases and records the gap.
    #:
    #: Refusing is the stricter reading of GDP and the right end state. It is
    #: not the right default: switching it on before a pharmacy has loaded any
    #: CoAs would stop it releasing stock at all, on the day it starts using
    #: the system. So the gap is recorded from the outset — visible and
    #: auditable — and the pharmacy turns enforcement on when its paperwork has
    #: caught up. Which is a decision for whoever runs it, not for us.
    require_coa_before_release = models.BooleanField(
        default=False,
        help_text=(
            "Refuse to release a lot from quarantine unless its Certificate of "
            "Analysis is on file and verified."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class OrganizationDocument(models.Model):
    """A registration / compliance document for an organization (the paperwork that
    must be on file before it can trade): RDB certificate, RRA/VAT, Rwanda FDA
    premises licence, NPC, tax clearance, etc. Captured and verified during onboarding.
    """

    class DocType(models.TextChoices):
        RWANDA_FDA_LICENCE = "RWANDA_FDA_LICENCE", "Rwanda FDA premises licence"
        NPC_LICENCE = "NPC_LICENCE", "NPC pharmacist licence"
        RDB_CERTIFICATE = "RDB_CERTIFICATE", "RDB registration certificate"
        RRA_VAT = "RRA_VAT", "RRA / VAT certificate"
        TAX_CLEARANCE = "TAX_CLEARANCE", "Tax clearance"
        OTHER = "OTHER", "Other"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="onboarding_documents"
    )
    doc_type = models.CharField(max_length=30, choices=DocType.choices)
    document_number = models.CharField(max_length=100, blank=True, default="")
    document_url = models.URLField(blank=True, default="")
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    notes = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "doc_type"])]

    def __str__(self) -> str:
        return f"{self.doc_type} · {self.organization_id}"


class Department(models.Model):
    """An operational department within an organization (dispensing, cashier, …)."""

    class DeptCode(models.TextChoices):
        WAREHOUSE = "WAREHOUSE", "Warehouse"
        DISPATCH = "DISPATCH", "Dispatch"
        PURCHASING = "PURCHASING", "Purchasing"
        DISPENSING = "DISPENSING", "Dispensing"
        CASHIER = "CASHIER", "Cashier"
        INSURANCE = "INSURANCE", "Insurance"
        FINANCE = "FINANCE", "Finance"
        HR = "HR", "Human Resources"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="departments"
    )
    code = models.CharField(max_length=30, choices=DeptCode.choices)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization", "code"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uniq_department_per_org")
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} · {self.code}"


class User(AbstractUser):
    """Custom user model (set as AUTH_USER_MODEL before the first migration).

    Extends Django's AbstractUser (username/email/password/flags) and adds a phone,
    org/department scoping, and role membership. Passwords are hashed with argon2.
    """

    phone = models.CharField(max_length=20, blank=True, default="")
    # Payroll-file / staff number — an alternate login identifier for staff who
    # have no email. Unique when set; the person's key across HR/attendance/audit.
    pf_number = models.CharField(
        max_length=30,
        blank=True,
        default="",
        db_index=True,
        help_text="Payroll-file / staff number; usable to sign in.",
    )
    organization = models.ForeignKey(
        Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    roles = models.ManyToManyField(Role, related_name="users", blank=True)
    # Set True when an admin resets the password; the user must set a new one.
    must_change_password = models.BooleanField(default=False)
    # Bumped to invalidate all outstanding tokens (force-logout / session revocation).
    token_version = models.PositiveIntegerField(default=0)
    # RRA TIN — Rwanda tax-identification, used on PAYE withholding certificates.
    tin = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text=(
            "Rwanda Revenue Authority Tax Identification Number — "
            "printed on annual PIT summaries."
        ),
    )
    # A secondary mailbox for payslip/PDF delivery (separate from login email).
    payroll_email = models.EmailField(
        blank=True,
        default="",
        help_text=(
            "Optional secondary email where payslips/PDFs are delivered, "
            "in addition to the login email."
        ),
    )
    # Senior oversight — used by the approvals engine to escalate long-tail queues.
    reports_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="direct_reports",
        help_text="The user's supervisor — used for senior oversight and approval escalation.",
    )
    # Authority limit (apps/iam/authority.py R2). Overrides whatever the user's
    # roles allow — which is how a deputy is covered for a fortnight without being
    # handed a role. Null means "use the roles"; see authority.approval_limit().
    approval_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Personal approval ceiling in RWF, overriding this user's roles. "
            "Leave empty to use the highest limit among their roles."
        ),
    )

    class Meta(AbstractUser.Meta):  # type: ignore[name-defined]
        constraints = [
            models.UniqueConstraint(
                fields=["pf_number"],
                condition=models.Q(pf_number__gt=""),
                name="uniq_pf_number_when_set",
            )
        ]

    def has_role(self, code: str) -> bool:
        return self.roles.filter(code=code).exists()

    def has_permission(self, code: str) -> bool:
        """True if any of the user's roles grants ``code``. Superusers and SYS_ADMIN
        implicitly hold every permission."""
        if self.is_superuser or self.has_role("SYS_ADMIN"):
            return True
        return self.roles.filter(permissions__code=code).exists()

    def permission_codes(self) -> set[str]:
        """All permission codes this user holds (via their roles)."""
        from apps.iam.models import Permission

        if self.is_superuser or self.has_role("SYS_ADMIN"):
            return set(Permission.objects.values_list("code", flat=True))
        return set(
            self.roles.filter(permissions__isnull=False).values_list("permissions__code", flat=True)
        )


class UserDocument(models.Model):
    """An identity document attached to a **user account** (who may sign in) — national
    ID, passport, professional licence, or contract. This is account-provisioning
    identity, distinct from HR employment/payroll documents. Admins capture and
    verify these when creating/managing a user.
    """

    class DocType(models.TextChoices):
        NATIONAL_ID = "NATIONAL_ID", "National ID"
        PASSPORT = "PASSPORT", "Passport"
        PROFESSIONAL_LICENCE = "PROFESSIONAL_LICENCE", "Professional licence"
        CONTRACT = "CONTRACT", "Employment contract"
        CERTIFICATE = "CERTIFICATE", "Certificate"
        OTHER = "OTHER", "Other"

    user = models.ForeignKey("iam.User", on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=30, choices=DocType.choices)
    document_number = models.CharField(max_length=100, blank=True, default="")
    document_url = models.URLField(blank=True, default="")
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    notes = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "doc_type"])]

    def __str__(self) -> str:
        return f"{self.doc_type} · {self.user_id}"


class ApiKey(models.Model):
    """A service-account API key. It authenticates requests **as a specific user**
    (reusing that user's roles & org scope), so machine integrations get exactly the
    access their service account is granted. Only the SHA-256 **hash** is stored; the
    raw key is shown once at creation and never again.
    """

    name = models.CharField(max_length=120)
    user = models.ForeignKey("iam.User", on_delete=models.CASCADE, related_name="api_keys")
    prefix = models.CharField(max_length=12, db_index=True)  # shown in the UI
    key_hash = models.CharField(max_length=64, unique=True)  # sha256 hex
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_active"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}…)"


class ImpersonationSession(models.Model):
    """Records an admin 'view-as' session: who acted as whom, when, and until when.

    Super-admin power is never invisible — every impersonation is stamped here and
    in the audit log, and the UI shows a banner while it is active.
    """

    admin = models.ForeignKey(
        "iam.User", on_delete=models.CASCADE, related_name="impersonations_started"
    )
    target = models.ForeignKey("iam.User", on_delete=models.CASCADE, related_name="impersonated_as")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["admin", "-started_at"])]

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    def __str__(self) -> str:
        return f"{self.admin_id} as {self.target_id}"


class License(models.Model):
    """A regulatory licence held by an organization (premises) or a staff member
    (professional). Tracked with expiry for compliance alerts."""

    class Type(models.TextChoices):
        PREMISES = "PREMISES", "Premises"
        PHARMACIST = "PHARMACIST", "Pharmacist"
        WHOLESALE = "WHOLESALE", "Wholesale"
        RETAIL = "RETAIL", "Retail"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        SUSPENDED = "SUSPENDED", "Suspended"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="licenses"
    )
    # Set when the licence belongs to a staff member (professional licence).
    user = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="licenses"
    )
    license_type = models.CharField(max_length=20, choices=Type.choices)
    license_number = models.CharField(max_length=100)
    issuing_authority = models.CharField(max_length=150, blank=True, default="")
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    document_url = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["expiry_date"]
        indexes = [models.Index(fields=["organization", "expiry_date"])]

    def __str__(self) -> str:
        return f"{self.license_type} · {self.license_number}"


class AuditLog(models.Model):
    """Append-only record of every significant action (GDP requirement).

    Immutability is enforced here at the model level (no updates, no deletes); on
    PostgreSQL a migration additionally denies UPDATE/DELETE to the app role.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    organization = models.ForeignKey(
        "iam.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100, blank=True, default="")
    entity_id = models.CharField(max_length=64, blank=True, default="")
    changes = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} @ {self.created_at:%Y-%m-%d %H:%M:%S}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Append-only: allow the initial insert, forbid any update.
        if not self._state.adding:
            raise ValueError("AuditLog is append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("AuditLog is append-only and cannot be deleted.")
