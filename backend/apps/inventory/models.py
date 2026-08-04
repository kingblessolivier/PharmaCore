"""Inventory models.

Phase 1: PharmacyProduct — the per-pharmacy product listing + retail price
(which products a pharmacy stocks and at what price). Batch-level stock and the
immutable movement ledger arrive in the next inventory slice.
"""

from __future__ import annotations

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
