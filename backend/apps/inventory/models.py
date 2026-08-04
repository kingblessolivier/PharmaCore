"""Inventory models: per-pharmacy product listing, batch stock, and the immutable
stock-movement ledger (FEFO by expiry). See docs/02-data-model.md & 06-workflows."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models


class PharmacyProduct(models.Model):
    """A product a specific organization (pharmacy/depot) carries, with its price."""

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="pharmacy_products"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="pharmacy_listings"
    )
    retail_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    # For a depot: the price it charges retailers (pulled into their purchase orders).
    wholesale_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    min_stock_level = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product__generic_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "product"], name="uniq_pharmacy_product"
            )
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} · {self.product}"


class InventoryBatch(models.Model):
    """A lot of a product held by an organization, tracked by batch + expiry (FEFO)."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        QUARANTINE = "QUARANTINE", "Quarantine"
        EXPIRED = "EXPIRED", "Expired"
        RECALLED = "RECALLED", "Recalled"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="inventory_batches"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="batches")
    batch_number = models.CharField(max_length=100)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    # Unsigned at the DB level → can never go negative.
    quantity_available = models.PositiveIntegerField(default=0)
    # Held for approved orders (not yet dispatched). Free-to-allocate = available - reserved.
    quantity_reserved = models.PositiveIntegerField(default=0)
    wholesale_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    storage_location = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # FEFO: soonest-expiring first.
        ordering = ["expiry_date", "batch_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "product", "batch_number"], name="uniq_org_product_batch"
            )
        ]
        indexes = [
            models.Index(fields=["organization", "product", "expiry_date"]),
            models.Index(fields=["batch_number"]),
        ]

    def __str__(self) -> str:
        return f"{self.product} · {self.batch_number} (exp {self.expiry_date})"


class StockMovement(models.Model):
    """Append-only ledger — every quantity change is one immutable signed row."""

    class Type(models.TextChoices):
        INTAKE = "INTAKE", "Supplier intake"
        TRANSFER_IN = "TRANSFER_IN", "Transfer in"
        TRANSFER_OUT = "TRANSFER_OUT", "Transfer out"
        SALE = "SALE", "Sale"
        RETURN = "RETURN", "Customer return / sale void"
        WASTAGE = "WASTAGE", "Wastage"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        RECALL = "RECALL", "Recall"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="stock_movements"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    batch = models.ForeignKey(
        InventoryBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="movements"
    )
    batch_number = models.CharField(max_length=100, blank=True, default="")
    movement_type = models.CharField(max_length=30, choices=Type.choices)
    quantity_delta = models.IntegerField()  # signed: +intake, -sale/wastage
    reference_type = models.CharField(max_length=50, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="")
    reason = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["organization", "product", "occurred_at"])]

    def __str__(self) -> str:
        return f"{self.movement_type} {self.quantity_delta:+d} · {self.product}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValueError("StockMovement is append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("StockMovement is append-only and cannot be deleted.")
