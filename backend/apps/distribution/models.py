"""Distribution models: B2B purchase orders (retail → depot) and their line items.

The order lifecycle (see docs/06-workflows-state-machines.md):
DRAFT → PENDING → APPROVED → PICKING → IN_TRANSIT → DELIVERED / PARTIALLY_RECEIVED.
Cancellable pre-dispatch. Later slices add allocation, shipment, and GRN.
"""

from __future__ import annotations

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
    quantity_approved = models.PositiveIntegerField(default=0)
    quantity_shipped = models.PositiveIntegerField(default=0)
    quantity_received = models.PositiveIntegerField(default=0)
    price_per_unit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} ×{self.quantity_ordered}"

    @property
    def line_total(self) -> float:
        return float(self.price_per_unit) * self.quantity_ordered


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
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} · {self.batch_number} ×{self.quantity}"


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
    quantity_expected = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    quantity_damaged = models.PositiveIntegerField(default=0)

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
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity} of {self.batch} for {self.order}"
