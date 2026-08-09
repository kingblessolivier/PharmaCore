"""Distribution models: B2B purchase orders (retail → depot) and their line items.

The order lifecycle (see docs/06-workflows-state-machines.md):
DRAFT → PENDING → APPROVED → PICKING → IN_TRANSIT → DELIVERED / PARTIALLY_RECEIVED.
Cancellable pre-dispatch. Later slices add allocation, shipment, and GRN.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import models


class StockOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        PICKING = "PICKING", "Picking"
        IN_TRANSIT = "IN_TRANSIT", "In transit"
        DELIVERED = "DELIVERED", "Delivered"
        PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partially received"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PARTIAL = "PARTIAL", "Partially paid"
        PAID = "PAID", "Paid"

    order_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    depot = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="incoming_orders"
    )
    retail = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="outgoing_orders"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    ordered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    expected_delivery = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    # Settlement: whether the buying pharmacy has paid the wholesaler for this order.
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["depot", "status"]),
            models.Index(fields=["retail", "status"]),
        ]

    def __str__(self) -> str:
        return self.order_number or f"PO#{self.pk}"

    @property
    def total_amount(self) -> float:
        return float(sum(i.line_total for i in self.items.all()))

    @property
    def amount_due(self) -> float:
        return max(0.0, self.total_amount - float(self.amount_paid))


class OrderItem(models.Model):
    order = models.ForeignKey(StockOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    quantity_ordered = models.PositiveIntegerField()
    quantity_approved = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    quantity_shipped = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    quantity_received = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    price_per_unit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    #: What the buyer counted in. A wholesale line saying "10" is meaningless
    #: on its own — ten cartons and ten tablets differ by a factor of 2,400,
    #: and the depot picking the order has only the number to go on. Purchase
    #: orders learned this in #121; B2B orders were still dimensionless.
    #:
    #: Null means the line was placed in base units, which is what every line
    #: written before this field existed meant.
    unit = models.ForeignKey(
        "catalog.ProductUnit",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    #: The same quantity in base units — what stock, availability and every
    #: downstream movement are actually counted in. Stored rather than derived
    #: so that re-pricing a pack size later cannot retroactively change what an
    #: order asked for.
    quantity_base = models.DecimalField(max_digits=16, decimal_places=3, default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        unit = self.unit
        suffix = f" {unit.code}" if unit else ""
        return f"{self.product} ×{self.quantity_ordered}{suffix}"

    @property
    def unit_label(self) -> str:
        """How to say this line's unit to a person."""
        unit = self.unit
        if unit is None:
            return ""
        return unit.name or unit.get_code_display()

    @property
    def price_per_ordered_unit(self) -> Decimal:
        """The price of one of whatever the buyer counted in.

        ``price_per_unit`` is the depot's published price for a *base* unit and
        stays that way — it is the authoritative figure and rescaling it on
        write would make the stored price depend on how somebody happened to
        type the order. This is the display figure: a carton costs the base
        price times what the carton holds.
        """
        unit = self.unit
        factor = Decimal(unit.factor_to_base) if unit else Decimal(1)
        return (Decimal(self.price_per_unit) * factor).quantize(Decimal("0.01"))

    @property
    def line_total(self) -> float:
        """What this line costs.

        Computed on the base quantity, not the ordered one. The published price
        is per base unit, so multiplying it by a pack count would price two
        cartons as though they were two tablets — an error of whatever the
        carton holds, silently, in the depot's favour or the buyer's depending
        on which way round it is read.
        """
        return float(self.price_per_unit) * float(self.quantity_base or self.quantity_ordered)


class Shipment(models.Model):
    """A dispatch of an order's goods from the depot (single-drop for now)."""

    order = models.ForeignKey(StockOrder, on_delete=models.CASCADE, related_name="shipments")
    driver_name = models.CharField(max_length=150, blank=True, default="")
    vehicle_registration = models.CharField(max_length=50, blank=True, default="")
    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    dispatched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-dispatched_at"]

    def __str__(self) -> str:
        return f"Shipment for {self.order}"


class ShipmentItem(models.Model):
    """One batch line on a shipment's packing manifest (what physically went out)."""

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="items")
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.PROTECT, related_name="shipment_items"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    quantity = models.DecimalField(max_digits=16, decimal_places=3)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} · {self.batch_number} ×{self.quantity}"


class InTransitStock(models.Model):
    """Stock that has left the source but not yet been received at the destination.

    Held here so every unit is counted *somewhere* at all times: dispatch moves it
    from the depot's on-hand into this ledger; receiving clears it and adds it to the
    retail on-hand. No 'ghost stock' visible at two places, none vanished in between.
    """

    order = models.ForeignKey(StockOrder, on_delete=models.CASCADE, related_name="in_transit")
    source_org = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="outbound_in_transit"
    )
    destination_org = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="inbound_in_transit"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    quantity = models.DecimalField(max_digits=16, decimal_places=3)
    driver_name = models.CharField(max_length=150, blank=True, default="")
    vehicle_plate = models.CharField(max_length=50, blank=True, default="")
    dispatched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["destination_org"]),
            models.Index(fields=["source_org"]),
        ]

    def __str__(self) -> str:
        return f"{self.quantity}× {self.product} in transit → {self.destination_org}"


class GoodsReceivedNote(models.Model):
    """Reception record at the retail pharmacy — the stock write-event."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        FINALIZED = "FINALIZED", "Finalized"

    grn_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    order = models.ForeignKey(StockOrder, on_delete=models.CASCADE, related_name="grns")
    shipment = models.ForeignKey(
        Shipment, null=True, blank=True, on_delete=models.SET_NULL, related_name="grns"
    )
    retail = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="received_notes"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    has_discrepancy = models.BooleanField(default=False)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self) -> str:
        return self.grn_number or f"GRN#{self.pk}"


class GRNLine(models.Model):
    grn = models.ForeignKey(GoodsReceivedNote, on_delete=models.CASCADE, related_name="lines")
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name="grn_lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    quantity_expected = models.DecimalField(max_digits=16, decimal_places=3)
    quantity_received = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    quantity_damaged = models.DecimalField(max_digits=16, decimal_places=3, default=0)

    class Meta:
        ordering = ["id"]

    @property
    def has_discrepancy(self) -> bool:
        return self.quantity_received != self.quantity_expected or self.quantity_damaged > 0


class OrderPayment(models.Model):
    """A payment the buying pharmacy made to the wholesaler against an order."""

    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
        CHEQUE = "CHEQUE", "Cheque"
        CREDIT = "CREDIT", "On credit"

    order = models.ForeignKey(StockOrder, on_delete=models.CASCADE, related_name="order_payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.BANK_TRANSFER)
    reference = models.CharField(max_length=100, blank=True, default="")  # txn / cheque no.
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    paid_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.amount} for {self.order}"


class Reservation(models.Model):
    """A hold placed on a specific depot batch for an approved order line (FEFO).

    Sum of a batch's reservations equals its ``quantity_reserved``. Released when the
    order is cancelled; consumed when the shipment is dispatched (later slice).
    """

    order = models.ForeignKey(StockOrder, on_delete=models.CASCADE, related_name="reservations")
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="reservations")
    batch = models.ForeignKey(
        "inventory.InventoryBatch", on_delete=models.PROTECT, related_name="reservations"
    )
    quantity = models.DecimalField(max_digits=16, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity} of {self.batch} for {self.order}"


class DepotProductListing(models.Model):
    """Depot offered stock listing, decoupled from physical warehouse on-hand.

    ROADMAP '5. Distribution'.
    """

    depot = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="depot_listings"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="depot_listings"
    )
    offered_qty = models.PositiveIntegerField(default=0)
    buffer_qty = models.PositiveIntegerField(default=0)
    price_per_unit = models.DecimalField(max_digits=14, decimal_places=2)
    is_published = models.BooleanField(default=True)
    customer_segment = models.CharField(max_length=50, blank=True, default="ALL")
    min_order_qty = models.PositiveIntegerField(default=1)
    #: Orders must be a whole multiple of this. A case is not opened to fill an
    #: order, so a depot that ships by the case sells 5 or 10, never 7 — and a
    #: pharmacy that can place an unfillable quantity only finds out on delivery.
    order_multiple = models.PositiveIntegerField(default=1)
    #: A depot's own photograph of the stock it is offering. Falls back to the
    #: catalogue picture; a buyer browsing a storefront of text alone has no way
    #: to tell one white box from another.
    image_url = models.CharField(max_length=500, blank=True, default="")
    #: Who confirmed this photo is of this medicine, and when.
    #:
    #: An unverified picture is worse than none: a buyer trusts it, and a wrong
    #: photo on a listing sells the wrong medicine. Upload and verification are
    #: deliberately separate acts, as they are for batch paperwork — attaching a
    #: file is not the same as somebody checking it is the right file.
    image_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    image_verified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["depot", "product"], name="uniq_depot_product_listing")
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Changing the photo clears its verification.

        Otherwise the check is a one-off: verify a correct picture once, swap it
        for anything later, and the tick stays. The verification has to belong to
        the image it was given, not to the row.
        """
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values_list("image_url", flat=True)
            was = next(iter(previous), None)
            if was is not None and was != self.image_url:
                self.image_verified_by = None
                self.image_verified_at = None
        super().save(*args, **kwargs)

    @property
    def image_is_trusted(self) -> bool:
        """Whether this photo may be shown to a buyer as this medicine."""
        return bool(self.image_url) and self.image_verified_at is not None

    def __str__(self) -> str:
        return f"{self.depot.name} · {self.product} (Offered: {self.offered_qty})"

    @property
    def available_for_order(self) -> int:
        return max(0, self.offered_qty - self.buffer_qty)


class SalesRepresentative(models.Model):
    """Field sales rep / medical rep master. ROADMAP '5. Distribution'."""

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="sales_reps"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sales_rep_profile"
    )
    employee = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_reps",
    )
    territory_code = models.CharField(max_length=50, default="KIGALI-CENTRAL")
    monthly_sales_target = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    commission_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=2.50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return f"Rep {self.user.username} ({self.territory_code})"


class JourneyPlan(models.Model):
    """Rep scheduled customer beat/visit plan. ROADMAP '5. Distribution'."""

    rep = models.ForeignKey(
        SalesRepresentative, on_delete=models.CASCADE, related_name="journey_plans"
    )
    customer_org = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="rep_visits"
    )
    planned_date = models.DateField()
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["planned_date"]

    def __str__(self) -> str:
        return f"{self.planned_date} · {self.rep} ➔ {self.customer_org.name}"


class SalesVisitLog(models.Model):
    """Field sales rep call report & pre-sale/van-sale log. ROADMAP '5. Distribution'."""

    class VisitType(models.TextChoices):
        PRE_SALE = "PRE_SALE", "Pre-sale order visit"
        VAN_SALE = "VAN_SALE", "Van sale (sell-from-stock)"
        CALL_ONLY = "CALL_ONLY", "Detailing / Call only"

    journey_plan = models.ForeignKey(
        JourneyPlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="visit_logs",
    )
    rep = models.ForeignKey(
        SalesRepresentative, on_delete=models.CASCADE, related_name="visit_logs"
    )
    customer_org = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="completed_visits"
    )
    visit_type = models.CharField(
        max_length=20, choices=VisitType.choices, default=VisitType.PRE_SALE
    )
    visited_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="")
    order = models.ForeignKey(
        StockOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="visit_origin",
    )
    sales_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["-visited_at"]

    def __str__(self) -> str:
        return f"{self.rep} visit to {self.customer_org.name} ({self.visit_type})"


class VanStock(models.Model):
    """Inventory assigned to a van for sell-from-stock sales. ROADMAP '5. Distribution'."""

    rep = models.ForeignKey(
        SalesRepresentative, on_delete=models.CASCADE, related_name="van_stocks"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE)
    batch_number = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["rep", "product"]
        constraints = [
            models.UniqueConstraint(
                fields=["rep", "product", "batch_number"], name="uniq_van_stock_item"
            )
        ]

    def __str__(self) -> str:
        return f"Van {self.rep} · {self.product} ({self.quantity} units)"


class TenderContract(models.Model):
    """Institutional / B2G Tender Contract & Locked Price Agreement. ROADMAP '5. Distribution'."""

    tender_number = models.CharField(max_length=50, unique=True)
    depot = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="tender_contracts"
    )
    client_org = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="awarded_tenders"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE)
    contract_price = models.DecimalField(max_digits=14, decimal_places=2)
    total_committed_qty = models.DecimalField(max_digits=16, decimal_places=3)
    drawn_qty = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    valid_until = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-valid_until"]

    def __str__(self) -> str:
        return f"Tender {self.tender_number} · {self.client_org.name}"

    @property
    def remaining_qty(self) -> Decimal:
        return max(Decimal(0), self.total_committed_qty - self.drawn_qty)


class CustomerReturn(models.Model):
    """Retailer return-to-depot request with quality inspection. ROADMAP '5. Distribution'."""

    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested by retailer"
        INSPECTING = "INSPECTING", "Inspecting at depot"
        APPROVED = "APPROVED", "Approved & Restocked / Credited"
        REJECTED = "REJECTED", "Rejected (Damaged / Invalid)"

    return_number = models.CharField(max_length=40, unique=True)
    depot = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="incoming_returns"
    )
    retail = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="outgoing_returns"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    reason = models.TextField(blank=True, default="")
    credit_note_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Return {self.return_number} from {self.retail.name}"


class BackorderLine(models.Model):
    """Demand a depot could not meet — the signal it imports against.

    When a retailer asks for something the depot does not stock, has withdrawn, or
    holds too little of, refusing the line throws away the most valuable thing in a
    marketplace: a customer telling you what to buy. The unmet quantity is captured
    here instead, aggregated across every retailer, and converted into a purchase
    requisition that feeds the existing procurement and import flow.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open — awaiting sourcing"
        SOURCING = "SOURCING", "Being sourced"
        FULFILLED = "FULFILLED", "Fulfilled"
        CANCELLED = "CANCELLED", "Cancelled"

    class Origin(models.TextChoices):
        UNLISTED = "UNLISTED", "Not offered by the depot"
        WITHDRAWN = "WITHDRAWN", "Withdrawn from sale"
        SHORT = "SHORT", "Offered but insufficient stock"
        SEGMENT = "SEGMENT", "Outside the offer's segment"
        REQUEST = "REQUEST", "Direct buyer request"

    depot = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="incoming_demand"
    )
    retail = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="outgoing_demand"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    order = models.ForeignKey(
        StockOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backorders",
    )
    quantity = models.DecimalField(max_digits=16, decimal_places=3)
    quantity_fulfilled = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    origin = models.CharField(max_length=12, choices=Origin.choices, default=Origin.SHORT)
    note = models.CharField(max_length=255, blank=True, default="")
    # Set once the demand has been rolled into a procurement requisition, so the
    # same demand is never sourced twice.
    requisition = models.ForeignKey(
        "procurement.PurchaseRequisition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_backorders",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["depot", "status"]),
            models.Index(fields=["depot", "product", "status"]),
            models.Index(fields=["retail", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.quantity}× {self.product} wanted by {self.retail.name}"

    @property
    def quantity_outstanding(self) -> Decimal:
        return max(Decimal(0), self.quantity - self.quantity_fulfilled)

    @property
    def is_open(self) -> bool:
        return self.status in (self.Status.OPEN, self.Status.SOURCING)


class VanStockMovement(models.Model):
    """A load-out, sale or return against a rep's van.

    ``VanStock`` holds the running quantity; this is the audit trail that explains
    every change to it. Without it a van's stock is a number nobody can reconcile.
    """

    class Kind(models.TextChoices):
        LOAD = "LOAD", "Loaded from depot"
        SALE = "SALE", "Sold from van"
        RETURN = "RETURN", "Returned to depot"
        ADJUST = "ADJUST", "Adjustment"

    rep = models.ForeignKey(
        SalesRepresentative, on_delete=models.CASCADE, related_name="van_movements"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    batch_number = models.CharField(max_length=50)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    quantity = models.IntegerField(help_text="Signed: positive adds to the van, negative removes.")
    visit = models.ForeignKey(
        SalesVisitLog, null=True, blank=True, on_delete=models.SET_NULL, related_name="van_moves"
    )
    reference = models.CharField(max_length=100, blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["rep", "created_at"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.quantity}× {self.product}"


class CustomerReturnLine(models.Model):
    """What was physically sent back, and what the depot accepted.

    The header's ``credit_note_amount`` used to be a number typed by a human with
    nothing behind it. Credit is now the sum of these lines: accepted units at the
    price they were sold for. Rejected units are recorded but never credited and
    never restocked.
    """

    return_request = models.ForeignKey(
        CustomerReturn, on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    batch_number = models.CharField(max_length=100, blank=True, default="")
    expiry_date = models.DateField(null=True, blank=True)
    quantity_returned = models.PositiveIntegerField()
    quantity_accepted = models.PositiveIntegerField(default=0)
    quantity_rejected = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    inspection_note = models.CharField(max_length=255, blank=True, default="")
    # Set when the accepted units are written back into depot stock, so a second
    # approval can never restock the same goods twice.
    restocked_batch = models.ForeignKey(
        "inventory.InventoryBatch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity_returned}× {self.product} returned"

    @property
    def credit_amount(self) -> Decimal:
        return (Decimal(self.unit_price) * self.quantity_accepted).quantize(Decimal("0.01"))
