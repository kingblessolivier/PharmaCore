"""Insurance: who pays for a medicine when the patient does not pay all of it.

Rwanda's payer landscape is unusual and the model has to hold it honestly:

* **CBHI / Mutuelle de Santé**, run by RSSB, covers most of the population at a
  **10% co-payment** — except Ubudehe category 1 members, who are **fully
  subsidised at 0%**. A co-pay that lives only on the scheme cannot express that,
  so the rate resolves member-first, then formulary, then scheme.
* **A February 2026 Prime Minister's order** moved CBHI from reimbursing
  facilities after the fact to **funding them upfront by capitation**, piloted in
  January 2026 and rolling out nationally. Private pharmacies still bill per
  script. Both settlement models are therefore first-class here — assuming either
  one alone dates the build immediately.

The other thing the design refuses to do is treat silence as coverage. A product
absent from a scheme's formulary is the patient's to pay in full; it is never
quietly billed to an insurer that never agreed to it.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

ZERO = Decimal("0.00")


class InsuranceScheme(models.Model):
    """A payer: CBHI, RSSB medical (RAMA), MMI, or a private insurer."""

    class Kind(models.TextChoices):
        CBHI = "CBHI", "CBHI / Mutuelle de Santé"
        RSSB_MEDICAL = "RSSB_MEDICAL", "RSSB medical (RAMA)"
        MILITARY = "MILITARY", "Military medical insurance (MMI)"
        PRIVATE = "PRIVATE", "Private insurer"
        EMPLOYER = "EMPLOYER", "Employer scheme"

    class Settlement(models.TextChoices):
        #: The pharmacy dispenses, claims, and is reimbursed per script.
        FEE_FOR_SERVICE = "FEE_FOR_SERVICE", "Fee for service (claim per dispense)"
        #: The payer funds a period upfront; dispensing draws against that budget.
        CAPITATION = "CAPITATION", "Capitation (funded upfront)"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="insurance_schemes"
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PRIVATE)
    settlement = models.CharField(
        max_length=20, choices=Settlement.choices, default=Settlement.FEE_FOR_SERVICE
    )
    #: Fallback share the patient pays, when neither the member nor the formulary
    #: says otherwise. 10.00 = 10%.
    default_copay_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("10.00")
    )
    #: Flat amount the patient pays per visit regardless of basket (RWF 200 at
    #: health-centre level under CBHI). Charged once per sale, not per line.
    consultation_fee = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    #: Days after dispensing within which a claim must be submitted. Past it the
    #: money is generally unrecoverable, so the queue has to surface the deadline.
    claim_window_days = models.PositiveIntegerField(default=30)
    contact_person = models.CharField(max_length=150, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=30, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="uniq_scheme_code_per_org"
            )
        ]
        indexes = [models.Index(fields=["organization", "is_active"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    @property
    def is_capitated(self) -> bool:
        return self.settlement == self.Settlement.CAPITATION


class MemberPolicy(models.Model):
    """The card presented at the counter.

    ``copay_pct_override`` exists because Rwanda's co-payment is a property of the
    *member*, not only the scheme: an Ubudehe category 1 member on CBHI pays
    nothing while a category 3 member on the same scheme pays 10%. A scheme-level
    rate alone would overcharge the poorest patients.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        EXPIRED = "EXPIRED", "Expired"

    class Relationship(models.TextChoices):
        PRINCIPAL = "PRINCIPAL", "Principal member"
        SPOUSE = "SPOUSE", "Spouse"
        CHILD = "CHILD", "Child"
        DEPENDANT = "DEPENDANT", "Other dependant"

    scheme = models.ForeignKey(InsuranceScheme, on_delete=models.PROTECT, related_name="policies")
    member_number = models.CharField(max_length=60)
    #: Household/group the member belongs to — CBHI membership is by household.
    group_number = models.CharField(max_length=60, blank=True, default="")
    full_name = models.CharField(max_length=150)
    national_id = models.CharField(max_length=30, blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    relationship = models.CharField(
        max_length=15, choices=Relationship.choices, default=Relationship.PRINCIPAL
    )
    #: Ubudehe category drives the subsidy under CBHI; 1 is fully subsidised.
    ubudehe_category = models.PositiveSmallIntegerField(null=True, blank=True)
    copay_pct_override = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Member's own co-payment share. Overrides the scheme rate; " "0 means fully covered."
        ),
    )
    valid_from = models.DateField()
    valid_to = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    #: Where a member holds two policies, the lower number pays first. This is
    #: what makes coordination of benefits resolvable rather than guesswork.
    priority = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "member_number"], name="uniq_member_per_scheme"
            )
        ]
        indexes = [
            models.Index(fields=["member_number"]),
            models.Index(fields=["national_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} · {self.member_number}"


class SchemeFormulary(models.Model):
    """What a scheme covers, and on what terms.

    A product with no row here is **not covered**. That is deliberate: treating
    absence as coverage bills insurers for medicines they never agreed to, and the
    rejection arrives weeks later once the stock has gone.
    """

    scheme = models.ForeignKey(InsuranceScheme, on_delete=models.CASCADE, related_name="formulary")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="insurance_coverage"
    )
    is_covered = models.BooleanField(default=True)
    copay_pct_override = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    #: Ceiling the scheme will pay per unit. Anything above it falls to the patient.
    max_price_per_unit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    max_quantity_per_claim = models.PositiveIntegerField(null=True, blank=True)
    requires_prior_auth = models.BooleanField(default=False)
    note = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product__generic_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "product"], name="uniq_formulary_scheme_product"
            )
        ]
        verbose_name_plural = "scheme formulary"

    def __str__(self) -> str:
        return f"{self.scheme.code} · {self.product}"


class Claim(models.Model):
    """What the pharmacy is owed by a payer for one insured sale."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        ACCEPTED = "ACCEPTED", "Accepted"
        PART_PAID = "PART_PAID", "Partially paid"
        PAID = "PAID", "Paid"
        REJECTED = "REJECTED", "Rejected"
        REVERSED = "REVERSED", "Reversed"

    class RejectionReason(models.TextChoices):
        NOT_ELIGIBLE = "NOT_ELIGIBLE", "Member not eligible on the date of service"
        NOT_COVERED = "NOT_COVERED", "Product not on the scheme formulary"
        NO_PRIOR_AUTH = "NO_PRIOR_AUTH", "Prior authorisation missing"
        LATE_SUBMISSION = "LATE_SUBMISSION", "Submitted outside the claim window"
        DUPLICATE = "DUPLICATE", "Duplicate of a claim already submitted"
        PRICE_EXCEEDED = "PRICE_EXCEEDED", "Above the scheme's price ceiling"
        QUANTITY_EXCEEDED = "QUANTITY_EXCEEDED", "Above the scheme's quantity limit"
        OTHER = "OTHER", "Other (see notes)"

    claim_number = models.CharField(max_length=40, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="insurance_claims"
    )
    scheme = models.ForeignKey(InsuranceScheme, on_delete=models.PROTECT, related_name="claims")
    policy = models.ForeignKey(MemberPolicy, on_delete=models.PROTECT, related_name="claims")
    sale = models.ForeignKey(
        "retail.Sale", on_delete=models.PROTECT, related_name="insurance_claims"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    service_date = models.DateField()
    #: What the patient paid at the counter, and what is being claimed. They sum
    #: to the sale total — the split is not allowed to lose or invent money.
    patient_paid = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    claimed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    #: What the insurer actually settled. Short-pays are the difference.
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    rejection_reason = models.CharField(
        max_length=20, choices=RejectionReason.choices, blank=True, default=""
    )
    notes = models.TextField(blank=True, default="")
    prior_auth_reference = models.CharField(max_length=60, blank=True, default="")
    submitted_at = models.DateTimeField(null=True, blank=True)
    adjudicated_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["scheme", "status"]),
            models.Index(fields=["service_date"]),
        ]

    def __str__(self) -> str:
        return self.claim_number or f"CLAIM#{self.pk}"

    @property
    def outstanding(self) -> Decimal:
        """Claimed but not yet settled — the pharmacy's exposure to this payer."""
        if self.status in (self.Status.REJECTED, self.Status.REVERSED):
            return ZERO
        return max(ZERO, self.claimed_amount - self.paid_amount)

    @property
    def shortfall(self) -> Decimal:
        """Accepted but under-paid. A short-pay that nobody chases is a write-off."""
        if self.status != self.Status.PAID:
            return ZERO
        return max(ZERO, self.claimed_amount - self.paid_amount)


class ClaimLine(models.Model):
    """One dispensed product on a claim, with its split."""

    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    sale_item = models.ForeignKey(
        "retail.SaleItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2)
    patient_amount = models.DecimalField(max_digits=14, decimal_places=2)
    insurer_amount = models.DecimalField(max_digits=14, decimal_places=2)
    copay_pct_applied = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    #: Why this line was split the way it was — capped by a ceiling, uncovered,
    #: needing prior authorisation. Without it a patient charge looks arbitrary.
    note = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity}× {self.product}"


class RemittanceAdvice(models.Model):
    """What an insurer says it is paying, against what was claimed.

    Kept as its own document rather than folded into the claims, because the
    reconciliation question — *did they pay what they agreed to* — cannot be
    answered from claim rows that have already been overwritten.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        POSTED = "POSTED", "Posted"

    reference = models.CharField(max_length=60)
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="remittances"
    )
    scheme = models.ForeignKey(
        InsuranceScheme, on_delete=models.PROTECT, related_name="remittances"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    advice_date = models.DateField()
    #: What the insurer's own document says it paid, before we match it to claims.
    total_advised = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-advice_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "scheme", "reference"], name="uniq_remittance_ref"
            )
        ]

    def __str__(self) -> str:
        return f"{self.scheme.code} · {self.reference}"

    @property
    def total_matched(self) -> Decimal:
        return sum((ln.amount_paid for ln in self.lines.all()), ZERO)

    @property
    def unmatched(self) -> Decimal:
        """Advised but not tied to a claim — money arrived that nobody can explain."""
        return self.total_advised - self.total_matched


class RemittanceLine(models.Model):
    """One claim's settlement on an advice."""

    remittance = models.ForeignKey(RemittanceAdvice, on_delete=models.CASCADE, related_name="lines")
    claim = models.ForeignKey(Claim, on_delete=models.PROTECT, related_name="remittance_lines")
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2)
    #: Populated when the insurer paid less than was claimed.
    denial_reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["remittance", "claim"], name="uniq_remittance_claim")
        ]

    def __str__(self) -> str:
        return f"{self.claim} paid {self.amount_paid}"
