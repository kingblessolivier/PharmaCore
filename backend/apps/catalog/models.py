"""Catalog models: the medicine master (global, shared across organizations).

The product master is not org-scoped (see docs/02-data-model.md) — inventory
batches that reference products are org-scoped, but the catalog itself is shared.
"""

from __future__ import annotations

from django.db import models


class Manufacturer(models.Model):
    name = models.CharField(max_length=255, unique=True)
    country = models.CharField(max_length=100, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Supplier(models.Model):
    """A supplier the depot buys from (importer/manufacturer/distributor)."""

    name = models.CharField(max_length=255, unique=True)
    tin = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    lead_time_days = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ActiveIngredient(models.Model):
    """An active pharmaceutical substance (for interaction/duplication checks)."""

    name = models.CharField(max_length=255, unique=True)
    atc_code = models.CharField(max_length=10, blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    """A medicine in the master catalog."""

    class TaxClass(models.TextChoices):
        A = "A", "A — Exempt (0%)"
        B = "B", "B — Standard (18% VAT)"
        C = "C", "C — Zero-rated"
        D = "D", "D — Special"

    class DosageForm(models.TextChoices):
        TABLET = "TABLET", "Tablet"
        CAPSULE = "CAPSULE", "Capsule"
        SYRUP = "SYRUP", "Syrup"
        INJECTION = "INJECTION", "Injection"
        OINTMENT = "OINTMENT", "Ointment"
        DROPS = "DROPS", "Drops"
        INHALER = "INHALER", "Inhaler"
        OTHER = "OTHER", "Other"

    class Storage(models.TextChoices):
        AMBIENT = "AMBIENT", "Ambient"
        COLD_CHAIN = "COLD_CHAIN", "Cold chain"
        FROZEN = "FROZEN", "Frozen"

    generic_name = models.CharField(max_length=255)
    brand_name = models.CharField(max_length=255, blank=True, default="")
    manufacturer = models.ForeignKey(
        Manufacturer, null=True, blank=True, on_delete=models.SET_NULL, related_name="products"
    )
    dosage_form = models.CharField(
        max_length=30, choices=DosageForm.choices, default=DosageForm.TABLET
    )
    strength = models.CharField(max_length=50, blank=True, default="")
    pack_size = models.CharField(max_length=50, blank=True, default="")
    unit_of_measure = models.CharField(max_length=20, blank=True, default="")
    atc_code = models.CharField(max_length=10, blank=True, default="")
    gtin = models.CharField(max_length=14, blank=True, default="")
    tax_class = models.CharField(max_length=1, choices=TaxClass.choices, default=TaxClass.B)
    requires_prescription = models.BooleanField(default=False)
    is_controlled_substance = models.BooleanField(default=False)
    storage_condition = models.CharField(
        max_length=20, choices=Storage.choices, default=Storage.AMBIENT
    )
    reorder_level = models.PositiveIntegerField(default=0)
    rra_item_code = models.CharField(max_length=50, blank=True, default="")  # RRA EBM item code
    image_url = models.URLField(blank=True, default="")
    leaflet_url = models.URLField(blank=True, default="")  # patient information leaflet
    # Cold-chain range (used when storage_condition is COLD_CHAIN / FROZEN)
    min_temp_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    max_temp_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["generic_name", "brand_name"]
        indexes = [models.Index(fields=["generic_name"]), models.Index(fields=["gtin"])]

    def __str__(self) -> str:
        return f"{self.generic_name} {self.strength}".strip()


class ProductIngredient(models.Model):
    """An active ingredient in a product, with its amount."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="ingredients")
    ingredient = models.ForeignKey(
        ActiveIngredient, on_delete=models.PROTECT, related_name="in_products"
    )
    amount = models.CharField(max_length=50, blank=True, default="")  # e.g. "500mg"

    class Meta:
        ordering = ["ingredient__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "ingredient"], name="uniq_product_ingredient"
            )
        ]

    def __str__(self) -> str:
        return f"{self.product} · {self.ingredient}"


class ProductBarcode(models.Model):
    """A scan code for a product at a packaging level."""

    class Level(models.TextChoices):
        EACH = "EACH", "Each"
        BOX = "BOX", "Box"
        CASE = "CASE", "Case"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="barcodes")
    barcode = models.CharField(max_length=64)
    packaging_level = models.CharField(max_length=20, choices=Level.choices, default=Level.EACH)
    units_per_level = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["packaging_level"]
        constraints = [
            models.UniqueConstraint(fields=["product", "barcode"], name="uniq_product_barcode")
        ]

    def __str__(self) -> str:
        return f"{self.barcode} ({self.packaging_level})"
