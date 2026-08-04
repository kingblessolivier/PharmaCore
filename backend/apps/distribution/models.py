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
