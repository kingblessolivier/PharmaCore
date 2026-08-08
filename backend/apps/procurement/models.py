"""Procurement & imports — the buy side of the depot.

ROADMAP.md "4. Procurement & imports". The chain this app models, end to end:

    Requisition (branch)  →  consolidated at HQ  →  RFQ  →  supplier quotes
        →  Purchase order (raise → approve → send)
        →  Import consignment (proforma / BoL / customs / duties / freight
           / insurance  →  **landed cost** allocated into unit cost)
        →  Goods receipt against the PO (batch + expiry capture, over/under
           delivery, QC hand-off to quarantine)
        →  Supplier invoice (**3-way match** PO ↔ GRN ↔ invoice)
           + debit/credit notes  →  posts to the Finance AP ledger.

Everything is org-scoped (``organization`` = the *buying* branch/depot) and every
sensitive step (requisition approval, PO approval, invoice approval / variance
override) routes through the shared approvals engine — claim-to-lock, no
self-approval, SLA timers (see ``apps/approvals`` and services.py here).

Money: ``unit_price``/amounts are in the document's own ``currency``;
``exchange_rate`` converts to the base currency (RWF). Costs that land in
inventory are always base-currency, landed (i.e. including duty/freight/
insurance) — that is the whole point of the imports slice.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

BASE_CURRENCY = "RWF"
ZERO = Decimal("0.00")


def _q(value: Decimal) -> Decimal:
    """Round to money precision (2 dp), half-up like the rest of the ledger."""
    return value.quantize(Decimal("0.01"))


class Incoterm(models.TextChoices):
    """Delivery terms — who pays freight/insurance and where risk passes."""

    EXW = "EXW", "EXW — Ex works"
    FCA = "FCA", "FCA — Free carrier"
    FAS = "FAS", "FAS — Free alongside ship"
    FOB = "FOB", "FOB — Free on board"
    CFR = "CFR", "CFR — Cost & freight"
    CIF = "CIF", "CIF — Cost, insurance & freight"
    CPT = "CPT", "CPT — Carriage paid to"
    CIP = "CIP", "CIP — Carriage & insurance paid to"
    DAP = "DAP", "DAP — Delivered at place"
    DPU = "DPU", "DPU — Delivered at place unloaded"
    DDP = "DDP", "DDP — Delivered duty paid"


class NumberSequence(models.Model):
    """Gapless per-organization, per-domain, per-document-kind, per-year numbering.

    ROADMAP §E ("Numbers, periods & opening balances"): allocated transactionally
    under ``SELECT … FOR UPDATE`` so two clerks can never take the same number.

    ADR-014: a single, first-class numbering primitive. The ``Domain`` field
    namespaces the ``Kind`` value so finance journals, HR payslips, retail
    receipts, etc. all live in the same table and the same :func:`next_number`
    helper serves them all.
    """

    class Domain(models.TextChoices):
        PROCUREMENT = "PROC", "Procurement"
        FINANCE = "FIN", "Finance"
        HR = "HR", "HR"
        INVENTORY = "INV", "Inventory"
        DISTRIBUTION = "DIST", "Distribution"
        RETAIL = "RTL", "Retail"
        DOCUMENTS = "DOC", "Documents (vault)"

    class Kind(models.TextChoices):
        # --- Procurement (pre-existing) ---
        REQUISITION = "PR", "Purchase requisition"
        RFQ = "RFQ", "Request for quotation"
        PURCHASE_ORDER = "PO", "Purchase order"
        GOODS_RECEIPT = "GRN", "Goods receipt"
        IMPORT = "IMP", "Import consignment"
        SUPPLIER_INVOICE = "SINV", "Supplier invoice"
        DEBIT_NOTE = "DBN", "Debit note"
        CREDIT_NOTE = "CRN", "Credit note"
        # --- Finance (ADR-014) ---
        CUSTOMER_INVOICE = "CINV", "Customer invoice (AR)"
        CUSTOMER_RECEIPT = "RCT", "Customer receipt"
        JOURNAL_ENTRY = "JE", "Journal entry"
        PAYMENT_RUN = "PRUN", "Payment run (AP disbursement)"
        STATUTORY_FILING = "FIL", "Statutory filing (PAYE/RSSB/CBHI/VAT)"
        # --- HR (ADR-014) ---
        PAYSLIP = "PSL", "Payslip"
        EMPLOYEE = "EMP", "Employee number"
        LOAN = "LOAN", "Loan / advance"
        # --- Documents ---
        DOCUMENT = "DOC", "Document vault reference"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="procurement_sequences"
    )
    domain = models.CharField(max_length=4, choices=Domain.choices, default=Domain.PROCUREMENT)
    kind = models.CharField(max_length=6, choices=Kind.choices)
    year = models.IntegerField()
    next_number = models.BigIntegerField(default=1)

    class Meta:
        constraints = [
            # ADR-014: unique (org, domain, kind, year). The previous unique
            # constraint was (org, kind, year); adding domain is additive —
            # existing procurement rows are unaffected (their domain is the
            # default PROCUREMENT).
            models.UniqueConstraint(
                fields=["organization", "domain", "kind", "year"],
                name="uniq_procurement_sequence",
            )
        ]

    def __str__(self) -> str:
        return f"{self.domain}/{self.kind} {self.year}: next {self.next_number}"


# ---------------------------------------------------------------------------
# Supplier master (the procurement view of a catalog.Supplier)
# ---------------------------------------------------------------------------


class SupplierProfile(models.Model):
    """Commercial & compliance master data for a supplier.

    ``catalog.Supplier`` is the shared identity (name/TIN/contact/lead time); this
    carries what *procurement* needs — standing (preferred → blacklisted), trade
    terms, banking, and the rolling performance scores. One profile per supplier.
    """

    class Standing(models.TextChoices):
        PREFERRED = "PREFERRED", "Preferred"
        APPROVED = "APPROVED", "Approved"
        PROBATION = "PROBATION", "On probation"
        SUSPENDED = "SUSPENDED", "Suspended"
        BLACKLISTED = "BLACKLISTED", "Blacklisted"

    class Kind(models.TextChoices):
        MANUFACTURER = "MANUFACTURER", "Manufacturer"
        IMPORTER = "IMPORTER", "Importer"
        DISTRIBUTOR = "DISTRIBUTOR", "Distributor / wholesaler"
        LOCAL_AGENT = "LOCAL_AGENT", "Local agent"
        SERVICE = "SERVICE", "Service provider (freight, clearing…)"

    supplier = models.OneToOneField(
        "catalog.Supplier", on_delete=models.CASCADE, related_name="procurement_profile"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.DISTRIBUTOR)
    standing = models.CharField(max_length=15, choices=Standing.choices, default=Standing.APPROVED)
    standing_reason = models.CharField(max_length=300, blank=True, default="")
    standing_changed_at = models.DateTimeField(null=True, blank=True)
    standing_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    # Identity & contact
    trading_name = models.CharField(max_length=255, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    website = models.URLField(blank=True, default="")
    contact_person = models.CharField(max_length=150, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=30, blank=True, default="")

    # Trade terms
    is_import_source = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, default=BASE_CURRENCY)
    incoterm = models.CharField(max_length=3, choices=Incoterm.choices, blank=True, default="")
    payment_terms_days = models.PositiveIntegerField(default=30)
    early_payment_discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    early_payment_days = models.PositiveIntegerField(default=0)
    minimum_order_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    lead_time_variance_days = models.PositiveIntegerField(default=0)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Settlement
    bank_name = models.CharField(max_length=150, blank=True, default="")
    bank_account_number = models.CharField(max_length=50, blank=True, default="")
    bank_swift = models.CharField(max_length=20, blank=True, default="")
    mobile_money_number = models.CharField(max_length=30, blank=True, default="")

    # Rolling performance (0–100), refreshed by services.refresh_supplier_scores()
    delivery_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    price_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    compliance_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    scores_updated_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["supplier__name"]

    def __str__(self) -> str:
        return f"{self.supplier.name} ({self.standing})"

    @property
    def overall_score(self) -> Decimal:
        """Equally-weighted scorecard — the number the buyer compares suppliers on."""
        parts = [self.delivery_score, self.quality_score, self.price_score, self.compliance_score]
        return _q(sum(parts, ZERO) / Decimal("4"))

    @property
    def can_order(self) -> bool:
        """A blacklisted or suspended supplier may not receive new purchase orders."""
        return self.standing not in {self.Standing.BLACKLISTED, self.Standing.SUSPENDED}


class SupplierLicence(models.Model):
    """A supplier's regulatory/quality credential with its expiry.

    GDP requires trading-partner qualification: you may not buy medicines from an
    unlicensed source. An expired *required* licence blocks approving a PO.
    """

    class Kind(models.TextChoices):
        FDA_IMPORT = "FDA_IMPORT", "Rwanda FDA import licence"
        FDA_WHOLESALE = "FDA_WHOLESALE", "Rwanda FDA wholesale licence"
        FDA_MANUFACTURE = "FDA_MANUFACTURE", "Rwanda FDA manufacturing licence"
        GMP = "GMP", "GMP certificate"
        GDP = "GDP", "GDP certificate"
        WHO_PREQUAL = "WHO_PREQUAL", "WHO prequalification"
        ISO = "ISO", "ISO certification"
        BUSINESS_REG = "BUSINESS_REG", "Business registration (RDB)"
        TAX_CLEARANCE = "TAX_CLEARANCE", "Tax clearance (RRA)"
        FREE_SALE = "FREE_SALE", "Certificate of free sale"
        OTHER = "OTHER", "Other"

    supplier = models.ForeignKey(
        "catalog.Supplier", on_delete=models.CASCADE, related_name="procurement_licences"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.FDA_WHOLESALE)
    licence_number = models.CharField(max_length=100)
    issuing_authority = models.CharField(max_length=150, blank=True, default="")
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    # A licence marked required must be present, verified and unexpired before a
    # purchase order to this supplier can be approved.
    is_required = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    document_url = models.CharField(max_length=255, blank=True, default="")
    notes = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["supplier__name", "kind"]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "kind", "licence_number"], name="uniq_supplier_licence"
            )
        ]

    def __str__(self) -> str:
        return f"{self.supplier.name} · {self.kind} {self.licence_number}"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_on and self.expires_on < timezone.localdate())

    @property
    def days_to_expiry(self) -> int | None:
        return (self.expires_on - timezone.localdate()).days if self.expires_on else None


class SupplierPriceAgreement(models.Model):
    """A negotiated (contract) price for a product from a supplier.

    Effective-dated with a volume break (``min_quantity``) so tiered/framework
    contracts are first-class. Purchase-order lines pull their price from here.
    """

    supplier = models.ForeignKey(
        "catalog.Supplier", on_delete=models.CASCADE, related_name="price_agreements"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="supplier_price_agreements"
    )
    organization = models.ForeignKey(
        "iam.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="supplier_price_agreements",
        help_text="Leave blank for a group-wide agreement; set it for one branch.",
    )
    contract_reference = models.CharField(max_length=100, blank=True, default="")
    currency = models.CharField(max_length=3, default=BASE_CURRENCY)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    min_quantity = models.PositiveIntegerField(default=1)
    lead_time_days = models.PositiveIntegerField(default=0)
    moq = models.PositiveIntegerField(default=0, help_text="Minimum order quantity.")
    pack_multiple = models.PositiveIntegerField(default=1, help_text="Order in multiples of.")
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["supplier__name", "product__generic_name", "min_quantity"]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "product", "min_quantity", "valid_from"],
                name="uniq_supplier_price_tier",
            )
        ]
        indexes = [models.Index(fields=["supplier", "product", "valid_from"])]

    def __str__(self) -> str:
        return (
            f"{self.supplier.name} · {self.product} @ {self.unit_price} "
            f"(min {self.min_quantity})"
        )

    def covers(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)


class SupplierEvaluation(models.Model):
    """A periodic supplier scorecard — the audit trail behind the rolling scores."""

    supplier = models.ForeignKey(
        "catalog.Supplier", on_delete=models.CASCADE, related_name="evaluations"
    )
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="supplier_evaluations"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    orders_count = models.PositiveIntegerField(default=0)
    on_time_delivery_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quality_acceptance_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    price_competitiveness = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    responsiveness = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    documentation_compliance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_auto_generated = models.BooleanField(default=False)
    comments = models.TextField(blank=True, default="")
    rated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_end", "supplier__name"]

    def __str__(self) -> str:
        return f"{self.supplier.name} {self.period_start}–{self.period_end}: {self.overall_score}"


# ---------------------------------------------------------------------------
# Requisitions (branch demand → consolidated purchasing at HQ)
# ---------------------------------------------------------------------------


class PurchaseRequisition(models.Model):
    """A branch's request to buy. Approved requisitions are consolidated at HQ into
    supplier purchase orders (many requisitions → one PO per supplier)."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted for approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CONVERTED = "CONVERTED", "Converted to PO"
        CANCELLED = "CANCELLED", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent (stock-out)"

    requisition_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="purchase_requisitions"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    needed_by = models.DateField(null=True, blank=True)
    justification = models.TextField(blank=True, default="")
    preferred_supplier = models.ForeignKey(
        "catalog.Supplier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requisitions",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return self.requisition_number or f"PR#{self.pk}"

    @property
    def estimated_total(self) -> Decimal:
        return _q(sum((ln.estimated_total for ln in self.lines.all()), ZERO))

    @property
    def is_editable(self) -> bool:
        return self.status == self.Status.DRAFT


class RequisitionLine(models.Model):
    requisition = models.ForeignKey(
        PurchaseRequisition, on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField()
    quantity_approved = models.PositiveIntegerField(default=0)
    quantity_ordered = models.PositiveIntegerField(default=0)
    estimated_unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} ×{self.quantity}"

    @property
    def estimated_total(self) -> Decimal:
        return _q(self.estimated_unit_cost * self.quantity)

    @property
    def quantity_outstanding(self) -> int:
        return max(0, (self.quantity_approved or self.quantity) - self.quantity_ordered)


# ---------------------------------------------------------------------------
# RFQ & quote comparison
# ---------------------------------------------------------------------------


class RequestForQuotation(models.Model):
    """An enquiry sent to several suppliers so their quotes can be compared."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SENT = "SENT", "Sent to suppliers"
        CLOSED = "CLOSED", "Closed for responses"
        AWARDED = "AWARDED", "Awarded"
        CANCELLED = "CANCELLED", "Cancelled"

    rfq_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="rfqs"
    )
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    requisition = models.ForeignKey(
        PurchaseRequisition, null=True, blank=True, on_delete=models.SET_NULL, related_name="rfqs"
    )
    issued_on = models.DateField(null=True, blank=True)
    response_due = models.DateField(null=True, blank=True)
    delivery_required_by = models.DateField(null=True, blank=True)
    terms = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return self.rfq_number or f"RFQ#{self.pk}"


class RFQLine(models.Model):
    rfq = models.ForeignKey(RequestForQuotation, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField()
    specification = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} ×{self.quantity}"


class SupplierQuote(models.Model):
    """One supplier's response to an RFQ — the thing the buyer compares."""

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        SHORTLISTED = "SHORTLISTED", "Shortlisted"
        AWARDED = "AWARDED", "Awarded"
        DECLINED = "DECLINED", "Not selected"

    rfq = models.ForeignKey(RequestForQuotation, on_delete=models.CASCADE, related_name="quotes")
    supplier = models.ForeignKey(
        "catalog.Supplier", on_delete=models.PROTECT, related_name="quotes"
    )
    quote_reference = models.CharField(max_length=100, blank=True, default="")
    quote_date = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RECEIVED)
    currency = models.CharField(max_length=3, default=BASE_CURRENCY)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal("1"))
    incoterm = models.CharField(max_length=3, choices=Incoterm.choices, blank=True, default="")
    lead_time_days = models.PositiveIntegerField(default=0)
    payment_terms_days = models.PositiveIntegerField(default=30)
    freight_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    warranty_terms = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["rfq", "supplier"], name="uniq_quote_per_rfq_supplier")
        ]

    def __str__(self) -> str:
        return f"{self.supplier.name} → {self.rfq}"

    @property
    def goods_total(self) -> Decimal:
        return _q(sum((ln.line_total for ln in self.lines.all()), ZERO))

    @property
    def total_amount(self) -> Decimal:
        return _q(
            self.goods_total + self.freight_amount + self.other_charges - self.discount_amount
        )

    @property
    def total_amount_base(self) -> Decimal:
        """Quote total in RWF — the only fair basis for comparing two currencies."""
        return _q(self.total_amount * self.exchange_rate)


class SupplierQuoteLine(models.Model):
    quote = models.ForeignKey(SupplierQuote, on_delete=models.CASCADE, related_name="lines")
    rfq_line = models.ForeignKey(
        RFQLine, null=True, blank=True, on_delete=models.SET_NULL, related_name="quote_lines"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    quantity_offered = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    lead_time_days = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} @ {self.unit_price}"

    @property
    def line_total(self) -> Decimal:
        return _q(self.unit_price * self.quantity_offered)


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------


class PurchaseOrder(models.Model):
    """A supplier purchase order: raise → approve → send → receive → close.

    Distinct from ``distribution.StockOrder`` (retail buying *from our depot*) —
    this is us buying from an **external supplier**, in the supplier's currency,
    with import terms and landed cost.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        SENT = "SENT", "Sent to supplier"
        PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partially received"
        RECEIVED = "RECEIVED", "Fully received"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    #: Statuses in which goods may still be booked in against the order.
    RECEIVABLE = {Status.APPROVED, Status.SENT, Status.PARTIALLY_RECEIVED}
    #: Statuses in which lines may still be edited.
    EDITABLE = {Status.DRAFT}

    po_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="purchase_orders"
    )
    supplier = models.ForeignKey(
        "catalog.Supplier", on_delete=models.PROTECT, related_name="purchase_orders"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    order_date = models.DateField(default=date.today)
    expected_delivery = models.DateField(null=True, blank=True)

    # Commercial terms
    currency = models.CharField(max_length=3, default=BASE_CURRENCY)
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal("1"),
        help_text="Units of RWF per 1 unit of the order currency.",
    )
    incoterm = models.CharField(max_length=3, choices=Incoterm.choices, blank=True, default="")
    payment_terms_days = models.PositiveIntegerField(default=30)
    payment_terms_note = models.CharField(max_length=255, blank=True, default="")
    freight_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Imports & delivery routing
    is_import = models.BooleanField(default=False)
    consignment = models.ForeignKey(
        "procurement.ImportConsignment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    # Drop-ship: goods go straight to a branch instead of the ordering depot.
    is_dropship = models.BooleanField(default=False)
    deliver_to = models.ForeignKey(
        "iam.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inbound_purchase_orders",
        help_text="Where the goods physically land. Defaults to the ordering org.",
    )
    delivery_address = models.CharField(max_length=255, blank=True, default="")

    # Provenance
    requisition = models.ForeignKey(
        PurchaseRequisition,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
    )
    quote = models.ForeignKey(
        SupplierQuote,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
    )
    supplier_reference = models.CharField(max_length=100, blank=True, default="")
    terms = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")

    # Lifecycle audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_method = models.CharField(max_length=30, blank=True, default="")
    closed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["supplier", "status"]),
        ]

    def __str__(self) -> str:
        return self.po_number or f"PO#{self.pk}"

    # --- money -------------------------------------------------------------
    @property
    def subtotal(self) -> Decimal:
        return _q(sum((ln.line_subtotal for ln in self.lines.all()), ZERO))

    @property
    def tax_total(self) -> Decimal:
        return _q(sum((ln.line_tax for ln in self.lines.all()), ZERO))

    @property
    def total_amount(self) -> Decimal:
        return _q(
            self.subtotal
            + self.tax_total
            + self.freight_amount
            + self.other_charges
            - self.discount_amount
        )

    @property
    def total_amount_base(self) -> Decimal:
        return _q(self.total_amount * self.exchange_rate)

    # --- progress ----------------------------------------------------------
    @property
    def quantity_ordered(self) -> int:
        return sum(ln.quantity_ordered for ln in self.lines.all())

    @property
    def quantity_received(self) -> int:
        return sum(ln.quantity_received for ln in self.lines.all())

    @property
    def received_pct(self) -> Decimal:
        ordered = self.quantity_ordered
        if ordered == 0:
            return ZERO
        return _q(Decimal(self.quantity_received) * 100 / Decimal(ordered))

    @property
    def is_fully_received(self) -> bool:
        lines = list(self.lines.all())
        return bool(lines) and all(ln.quantity_received >= ln.quantity_ordered for ln in lines)

    @property
    def destination(self) -> object:
        return self.deliver_to or self.organization

    @property
    def is_editable(self) -> bool:
        return self.status in self.EDITABLE

    @property
    def can_receive(self) -> bool:
        return self.status in self.RECEIVABLE


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=255, blank=True, default="")
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    quantity_rejected = models.PositiveIntegerField(default=0)
    quantity_invoiced = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    expected_delivery = models.DateField(null=True, blank=True)
    requisition_line = models.ForeignKey(
        RequisitionLine,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_lines",
    )
    # Landed cost: filled by services.allocate_landed_costs() — the share of
    # duty/freight/insurance/clearing this line carries, and the resulting
    # per-unit cost in base currency that goes into the inventory batch.
    landed_cost_allocated = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    landed_unit_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} ×{self.quantity_ordered}"

    @property
    def net_unit_price(self) -> Decimal:
        return _q(self.unit_price * (Decimal("100") - self.discount_pct) / Decimal("100"))

    @property
    def line_subtotal(self) -> Decimal:
        return _q(self.net_unit_price * self.quantity_ordered)

    @property
    def line_tax(self) -> Decimal:
        return _q(self.line_subtotal * self.tax_rate_pct / Decimal("100"))

    @property
    def line_total(self) -> Decimal:
        return _q(self.line_subtotal + self.line_tax)

    @property
    def quantity_outstanding(self) -> int:
        return max(0, self.quantity_ordered - self.quantity_received)

    @property
    def base_unit_cost(self) -> Decimal:
        """Goods-only unit cost in RWF, before landed costs are added."""
        return _q(self.net_unit_price * self.order.exchange_rate)

    @property
    def effective_unit_cost(self) -> Decimal:
        """What one unit costs us on the shelf — landed if allocated, else goods-only."""
        return self.landed_unit_cost if self.landed_unit_cost is not None else self.base_unit_cost


# ---------------------------------------------------------------------------
# Imports: consignment + landed cost
# ---------------------------------------------------------------------------


class ImportConsignment(models.Model):
    """An import shipment: proforma → bill of lading → customs → cleared → landed.

    Carries the documents an importer must hold and the cost components
    (freight, insurance, duty, clearing…) that are allocated into unit cost.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PROFORMA = "PROFORMA", "Proforma received"
        SHIPPED = "SHIPPED", "Shipped / in transit"
        ARRIVED = "ARRIVED", "Arrived at port"
        AT_CUSTOMS = "AT_CUSTOMS", "At customs / clearing"
        CLEARED = "CLEARED", "Customs cleared"
        LANDED = "LANDED", "Landed & costed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Mode(models.TextChoices):
        SEA = "SEA", "Sea freight"
        AIR = "AIR", "Air freight"
        ROAD = "ROAD", "Road freight"
        RAIL = "RAIL", "Rail"
        COURIER = "COURIER", "Courier"

    reference = models.CharField(max_length=30, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="import_consignments"
    )
    supplier = models.ForeignKey(
        "catalog.Supplier", on_delete=models.PROTECT, related_name="consignments"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.SEA)
    incoterm = models.CharField(max_length=3, choices=Incoterm.choices, blank=True, default="")
    currency = models.CharField(max_length=3, default="USD")
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal("1"))

    # Proforma invoice (the supplier's pre-shipment quote/commitment)
    proforma_number = models.CharField(max_length=100, blank=True, default="")
    proforma_date = models.DateField(null=True, blank=True)
    proforma_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    proforma_document_url = models.CharField(max_length=255, blank=True, default="")

    # Transport documents
    bill_of_lading_number = models.CharField(max_length=100, blank=True, default="")
    bill_of_lading_date = models.DateField(null=True, blank=True)
    airway_bill_number = models.CharField(max_length=100, blank=True, default="")
    vessel_or_flight = models.CharField(max_length=100, blank=True, default="")
    container_numbers = models.CharField(max_length=255, blank=True, default="")
    carrier = models.CharField(max_length=150, blank=True, default="")
    port_of_loading = models.CharField(max_length=100, blank=True, default="")
    port_of_discharge = models.CharField(max_length=100, blank=True, default="")
    country_of_origin = models.CharField(max_length=100, blank=True, default="")
    gross_weight_kg = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    packages_count = models.PositiveIntegerField(default=0)
    etd = models.DateField(null=True, blank=True, verbose_name="Estimated departure")
    eta = models.DateField(null=True, blank=True, verbose_name="Estimated arrival")
    arrived_on = models.DateField(null=True, blank=True)

    # Customs & clearing
    customs_declaration_number = models.CharField(max_length=100, blank=True, default="")
    customs_office = models.CharField(max_length=150, blank=True, default="")
    customs_cleared_on = models.DateField(null=True, blank=True)
    clearing_agent = models.CharField(max_length=150, blank=True, default="")
    clearing_agent_contact = models.CharField(max_length=100, blank=True, default="")
    hs_code_summary = models.CharField(max_length=255, blank=True, default="")

    # Insurance
    insurance_policy_number = models.CharField(max_length=100, blank=True, default="")
    insurer_name = models.CharField(max_length=150, blank=True, default="")
    insured_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Cost allocation
    allocation_basis = models.CharField(
        max_length=10,
        choices=[("VALUE", "By line value"), ("QUANTITY", "By quantity")],
        default="VALUE",
    )
    costs_allocated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return self.reference or f"IMP#{self.pk}"

    @property
    def goods_value_base(self) -> Decimal:
        """Value of the goods on the attached POs, in RWF."""
        return _q(sum((po.total_amount_base for po in self.orders.all()), ZERO))

    @property
    def landed_cost_total(self) -> Decimal:
        """Non-recoverable landed cost in RWF (what capitalises into stock)."""
        return _q(
            sum(
                (c.amount_base for c in self.costs.all() if not c.is_recoverable_tax),
                ZERO,
            )
        )

    @property
    def recoverable_tax_total(self) -> Decimal:
        """Import VAT etc. — reclaimed from RRA, never added to unit cost."""
        return _q(sum((c.amount_base for c in self.costs.all() if c.is_recoverable_tax), ZERO))

    @property
    def total_landed_value(self) -> Decimal:
        return _q(self.goods_value_base + self.landed_cost_total)

    @property
    def uplift_pct(self) -> Decimal:
        """How much % landing the goods added to their invoice cost."""
        goods = self.goods_value_base
        if goods == 0:
            return ZERO
        return _q(self.landed_cost_total * 100 / goods)


class LandedCostComponent(models.Model):
    """One cost incurred bringing a consignment in — freight, duty, insurance…

    ``is_recoverable_tax`` marks input VAT: it is reclaimed from RRA, so it must
    **not** inflate unit cost. Everything else is allocated across the goods.
    """

    class Kind(models.TextChoices):
        FREIGHT = "FREIGHT", "Freight"
        INSURANCE = "INSURANCE", "Marine / transit insurance"
        CUSTOMS_DUTY = "CUSTOMS_DUTY", "Customs duty"
        EXCISE = "EXCISE", "Excise duty"
        IMPORT_VAT = "IMPORT_VAT", "Import VAT (recoverable)"
        WITHHOLDING = "WITHHOLDING", "Withholding tax"
        CLEARING_FEE = "CLEARING_FEE", "Clearing agent fee"
        PORT_HANDLING = "PORT_HANDLING", "Port / terminal handling"
        INLAND_TRANSPORT = "INLAND_TRANSPORT", "Inland transport"
        STORAGE_DEMURRAGE = "STORAGE_DEMURRAGE", "Storage / demurrage"
        INSPECTION = "INSPECTION", "Inspection & testing"
        BANK_CHARGES = "BANK_CHARGES", "Bank / LC charges"
        OTHER = "OTHER", "Other"

    consignment = models.ForeignKey(
        ImportConsignment, on_delete=models.CASCADE, related_name="costs"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.FREIGHT)
    description = models.CharField(max_length=255, blank=True, default="")
    vendor_name = models.CharField(max_length=150, blank=True, default="")
    invoice_reference = models.CharField(max_length=100, blank=True, default="")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default=BASE_CURRENCY)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal("1"))
    is_recoverable_tax = models.BooleanField(default=False)
    incurred_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.kind} {self.amount} {self.currency}"

    @property
    def amount_base(self) -> Decimal:
        return _q(self.amount * self.exchange_rate)


# ---------------------------------------------------------------------------
# Goods receipt against a purchase order
# ---------------------------------------------------------------------------


class GoodsReceipt(models.Model):
    """Reception of supplier goods against a PO — the stock write-event.

    Posting a receipt creates/tops up inventory batches at **landed** unit cost,
    appends the immutable stock movements, and (when ``requires_qc``) lands the
    batches in QUARANTINE with a pending ``inventory.QualityCheck`` so nothing
    unverified reaches saleable stock.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        POSTED = "POSTED", "Posted to stock"
        CANCELLED = "CANCELLED", "Cancelled"

    grn_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    organization = models.ForeignKey(
        "iam.Organization",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
        help_text="Where the stock lands (the PO's deliver-to for a drop-ship).",
    )
    consignment = models.ForeignKey(
        ImportConsignment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="receipts",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    received_on = models.DateField(default=date.today)

    # Delivery paperwork
    supplier_delivery_note = models.CharField(max_length=100, blank=True, default="")
    waybill_number = models.CharField(max_length=100, blank=True, default="")
    vehicle_plate = models.CharField(max_length=50, blank=True, default="")
    driver_name = models.CharField(max_length=150, blank=True, default="")

    # Inbound checks (GDP)
    requires_qc = models.BooleanField(
        default=True,
        help_text="Land the goods in quarantine pending QC release (GDP default).",
    )
    cold_chain_intact = models.BooleanField(default=True)
    packaging_intact = models.BooleanField(default=True)
    temperature_on_arrival_c = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    has_discrepancy = models.BooleanField(default=False)
    discrepancy_note = models.CharField(max_length=300, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return self.grn_number or f"GRN#{self.pk}"

    @property
    def total_received(self) -> int:
        return sum(ln.quantity_received for ln in self.lines.all())

    @property
    def total_rejected(self) -> int:
        return sum(ln.quantity_rejected for ln in self.lines.all())

    @property
    def goods_value_base(self) -> Decimal:
        return _q(sum((ln.line_value for ln in self.lines.all()), ZERO))

    @property
    def is_editable(self) -> bool:
        return self.status == self.Status.DRAFT


class GoodsReceiptLine(models.Model):
    """One batch of one product received — batch/expiry capture is mandatory."""

    class Condition(models.TextChoices):
        GOOD = "GOOD", "Good"
        DAMAGED = "DAMAGED", "Damaged"
        SHORT_DATED = "SHORT_DATED", "Short-dated"
        WRONG_ITEM = "WRONG_ITEM", "Wrong item"
        TEMPERATURE_ABUSED = "TEMPERATURE_ABUSED", "Temperature abused"

    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    order_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.PROTECT, related_name="receipt_lines"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    batch_number = models.CharField(max_length=100)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    quantity_expected = models.PositiveIntegerField(default=0)
    quantity_received = models.PositiveIntegerField(default=0)
    quantity_rejected = models.PositiveIntegerField(default=0)
    rejection_reason = models.CharField(
        max_length=25, choices=Condition.choices, blank=True, default=""
    )
    rejection_note = models.CharField(max_length=255, blank=True, default="")
    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Landed unit cost in RWF, snapshotted when the receipt is posted.",
    )
    storage_location = models.CharField(max_length=100, blank=True, default="")
    bin_location = models.ForeignKey(
        "inventory.BinLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    batch = models.ForeignKey(
        "inventory.InventoryBatch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The stock batch this line created/topped up when posted.",
    )

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} · {self.batch_number} ×{self.quantity_received}"

    @property
    def variance(self) -> int:
        """Signed over/under delivery against what the PO line expected."""
        return self.quantity_received - self.quantity_expected

    @property
    def is_over_delivery(self) -> bool:
        return self.variance > 0

    @property
    def is_under_delivery(self) -> bool:
        return self.variance < 0

    @property
    def line_value(self) -> Decimal:
        return _q(self.unit_cost * self.quantity_received)


# ---------------------------------------------------------------------------
# Supplier invoices (AP) — 3-way match, notes, statements
# ---------------------------------------------------------------------------


class SupplierInvoice(models.Model):
    """A supplier's invoice, matched PO ↔ GRN ↔ invoice before it may be approved.

    Approval creates the payable in the Finance ledger (``finance.SupplierBill``)
    and posts the journal, so payments, aging and DPO keep one source of truth.
    A variance can only be approved with an explicit, audited override reason —
    routed through the approvals engine.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        MATCHED = "MATCHED", "Matched — ready to approve"
        VARIANCE = "VARIANCE", "Variance — needs review"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        APPROVED = "APPROVED", "Approved & posted"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    class MatchResult(models.TextChoices):
        NOT_RUN = "NOT_RUN", "Not matched yet"
        MATCHED = "MATCHED", "Matched within tolerance"
        QTY_VARIANCE = "QTY_VARIANCE", "Quantity variance"
        PRICE_VARIANCE = "PRICE_VARIANCE", "Price variance"
        QTY_AND_PRICE = "QTY_AND_PRICE", "Quantity & price variance"
        NO_RECEIPT = "NO_RECEIPT", "No goods receipt to match"

    invoice_number = models.CharField(max_length=100, help_text="The supplier's own number.")
    internal_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="supplier_invoices"
    )
    supplier = models.ForeignKey(
        "catalog.Supplier", on_delete=models.PROTECT, related_name="procurement_invoices"
    )
    order = models.ForeignKey(
        PurchaseOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices"
    )
    receipt = models.ForeignKey(
        GoodsReceipt, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    invoice_date = models.DateField(default=date.today)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default=BASE_CURRENCY)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal("1"))
    freight_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_class = models.CharField(max_length=4, blank=True, default="")

    # 3-way match
    match_result = models.CharField(
        max_length=15, choices=MatchResult.choices, default=MatchResult.NOT_RUN
    )
    match_detail = models.JSONField(default=list, blank=True)
    qty_tolerance_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    price_tolerance_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1"))
    matched_at = models.DateTimeField(null=True, blank=True)
    matched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    override_reason = models.CharField(max_length=300, blank=True, default="")

    # Posting to the finance ledger
    finance_bill = models.ForeignKey(
        "finance.SupplierBill",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="procurement_invoices",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.CharField(max_length=300, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "supplier", "invoice_number"],
                name="uniq_supplier_invoice_number",
            )
        ]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"{self.invoice_number} · {self.supplier.name}"

    @property
    def goods_subtotal(self) -> Decimal:
        return _q(sum((ln.line_subtotal for ln in self.lines.all()), ZERO))

    @property
    def tax_total(self) -> Decimal:
        return _q(sum((ln.line_tax for ln in self.lines.all()), ZERO))

    @property
    def net_amount(self) -> Decimal:
        """Ex-tax amount payable, after charges and discount."""
        return _q(
            self.goods_subtotal + self.freight_amount + self.other_charges - self.discount_amount
        )

    @property
    def total_amount(self) -> Decimal:
        return _q(self.net_amount + self.tax_total)

    @property
    def total_amount_base(self) -> Decimal:
        return _q(self.total_amount * self.exchange_rate)

    @property
    def notes_total(self) -> Decimal:
        """Debit notes increase what we owe; credit notes reduce it."""
        total = ZERO
        for note in self.notes_issued.all():
            if note.status == SupplierNote.Status.CANCELLED:
                continue
            signed = (
                note.total_amount if note.kind == SupplierNote.Kind.DEBIT else -note.total_amount
            )
            total += signed
        return _q(total)

    @property
    def payable_amount(self) -> Decimal:
        return _q(self.total_amount + self.notes_total)

    @property
    def is_editable(self) -> bool:
        return self.status in {self.Status.DRAFT, self.Status.MATCHED, self.Status.VARIANCE}

    @property
    def has_variance(self) -> bool:
        return self.match_result in {
            self.MatchResult.QTY_VARIANCE,
            self.MatchResult.PRICE_VARIANCE,
            self.MatchResult.QTY_AND_PRICE,
            self.MatchResult.NO_RECEIPT,
        }


class SupplierInvoiceLine(models.Model):
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name="lines")
    order_line = models.ForeignKey(
        PurchaseOrderLine,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoice_lines",
    )
    product = models.ForeignKey(
        "catalog.Product", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    description = models.CharField(max_length=255, blank=True, default="")
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product or self.description} ×{self.quantity}"

    @property
    def net_unit_price(self) -> Decimal:
        return _q(self.unit_price * (Decimal("100") - self.discount_pct) / Decimal("100"))

    @property
    def line_subtotal(self) -> Decimal:
        return _q(self.net_unit_price * self.quantity)

    @property
    def line_tax(self) -> Decimal:
        return _q(self.line_subtotal * self.tax_rate_pct / Decimal("100"))

    @property
    def line_total(self) -> Decimal:
        return _q(self.line_subtotal + self.line_tax)


class SupplierNote(models.Model):
    """A debit or credit note against a supplier.

    **Debit note** — we charge the supplier (short-ship, damage, price over-charge):
    it *reduces* what we owe. **Credit note** — the supplier credits us (return,
    rebate, agreed allowance). Both feed the statement and the payable.
    """

    class Kind(models.TextChoices):
        DEBIT = "DEBIT", "Debit note (we charge the supplier)"
        CREDIT = "CREDIT", "Credit note (supplier credits us)"

    class Reason(models.TextChoices):
        SHORT_SHIPMENT = "SHORT_SHIPMENT", "Short shipment"
        DAMAGE = "DAMAGE", "Damaged goods"
        WRONG_ITEM = "WRONG_ITEM", "Wrong item supplied"
        SHORT_DATED = "SHORT_DATED", "Short-dated stock"
        PRICE_VARIANCE = "PRICE_VARIANCE", "Price variance"
        QUALITY_DEFECT = "QUALITY_DEFECT", "Quality defect"
        RETURN = "RETURN", "Return to supplier"
        REBATE = "REBATE", "Rebate / allowance"
        FREIGHT = "FREIGHT", "Freight adjustment"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ISSUED = "ISSUED", "Issued"
        SETTLED = "SETTLED", "Settled"
        CANCELLED = "CANCELLED", "Cancelled"

    note_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="supplier_notes"
    )
    supplier = models.ForeignKey(
        "catalog.Supplier", on_delete=models.PROTECT, related_name="notes_raised"
    )
    invoice = models.ForeignKey(
        SupplierInvoice,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notes_issued",
    )
    receipt = models.ForeignKey(
        GoodsReceipt, null=True, blank=True, on_delete=models.SET_NULL, related_name="notes_issued"
    )
    kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.DEBIT)
    reason = models.CharField(max_length=20, choices=Reason.choices, default=Reason.SHORT_SHIPMENT)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    note_date = models.DateField(default=date.today)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default=BASE_CURRENCY)
    description = models.TextField(blank=True, default="")
    settled_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-note_date", "-id"]
        indexes = [models.Index(fields=["organization", "supplier", "status"])]

    def __str__(self) -> str:
        return f"{self.note_number or f'NOTE#{self.pk}'} ({self.kind})"

    @property
    def total_amount(self) -> Decimal:
        return _q(self.amount + self.tax_amount)
