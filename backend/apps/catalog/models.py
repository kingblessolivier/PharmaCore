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

    class Route(models.TextChoices):
        ORAL = "ORAL", "Oral"
        IV = "IV", "Intravenous (IV)"
        IM = "IM", "Intramuscular (IM)"
        SUBCUTANEOUS = "SUBCUTANEOUS", "Subcutaneous"
        TOPICAL = "TOPICAL", "Topical"
        INHALATION = "INHALATION", "Inhalation"
        OPHTHALMIC = "OPHTHALMIC", "Ophthalmic (eye)"
        NASAL = "NASAL", "Nasal"
        RECTAL = "RECTAL", "Rectal"
        OTHER = "OTHER", "Other"

    class LifecycleStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DISCONTINUED = "DISCONTINUED", "Discontinued"
        OBSOLETE = "OBSOLETE", "Obsolete"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Approval"

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
    units_per_pack = models.PositiveIntegerField(default=1)  # e.g. 10×10 blister = 100
    route_of_administration = models.CharField(
        max_length=20, choices=Route.choices, blank=True, default=""
    )
    atc_code = models.CharField(max_length=10, blank=True, default="")
    gtin = models.CharField(max_length=14, blank=True, default="")
    fda_registration_number = models.CharField(  # Rwanda FDA product registration
        max_length=100, blank=True, default=""
    )
    tax_class = models.CharField(max_length=1, choices=TaxClass.choices, default=TaxClass.B)
    requires_prescription = models.BooleanField(default=False)
    is_controlled_substance = models.BooleanField(default=False)
    controlled_schedule = models.CharField(  # e.g. "Schedule 2" (when controlled)
        max_length=50, blank=True, default=""
    )
    storage_condition = models.CharField(
        max_length=20, choices=Storage.choices, default=Storage.AMBIENT
    )
    reorder_level = models.PositiveIntegerField(default=0)
    reorder_quantity = models.PositiveIntegerField(default=0)  # how much to reorder
    rra_item_code = models.CharField(max_length=50, blank=True, default="")  # RRA EBM item code
    image_url = models.URLField(blank=True, default="")
    leaflet_url = models.URLField(blank=True, default="")  # patient information leaflet
    # Cold-chain range (used when storage_condition is COLD_CHAIN / FROZEN)
    min_temp_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    max_temp_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    # WHO International Clinical Standards & Lifecycle
    ddd = models.CharField(max_length=50, blank=True, default="")  # Defined Daily Dose (e.g. "500mg/day")
    is_essential = models.BooleanField(default=False)  # Essential Medicines List (WHO / EML)
    rxnorm_id = models.CharField(max_length=50, blank=True, default="")  # RxNorm identifier
    lifecycle_status = models.CharField(
        max_length=30, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE
    )

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


class ProductInteraction(models.Model):
    """Drug-drug interaction between active ingredients (DrugBank severity scale)."""

    class Severity(models.TextChoices):
        MINOR = "MINOR", "Minor"
        MODERATE = "MODERATE", "Moderate"
        MAJOR = "MAJOR", "Major"

    ingredient_a = models.ForeignKey(
        ActiveIngredient, on_delete=models.CASCADE, related_name="interactions_as_a"
    )
    ingredient_b = models.ForeignKey(
        ActiveIngredient, on_delete=models.CASCADE, related_name="interactions_as_b"
    )
    severity = models.CharField(
        max_length=20, choices=Severity.choices, default=Severity.MODERATE
    )
    effect = models.TextField(blank=True, default="")
    management = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["ingredient_a__name", "ingredient_b__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["ingredient_a", "ingredient_b"], name="uniq_ingredient_interaction"
            )
        ]

    def __str__(self) -> str:
        return f"{self.ingredient_a} ↔ {self.ingredient_b} ({self.severity})"


class ProductContraindication(models.Model):
    """Condition or disease contraindication for a product."""

    class Severity(models.TextChoices):
        PRECAUTION = "PRECAUTION", "Precaution"
        WARNING = "WARNING", "Warning"
        CONTRAINDICATED = "CONTRAINDICATED", "Contraindicated"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="contraindications")
    condition = models.CharField(max_length=255)
    icd10_code = models.CharField(max_length=20, blank=True, default="")
    snomed_code = models.CharField(max_length=30, blank=True, default="")
    severity = models.CharField(
        max_length=20, choices=Severity.choices, default=Severity.WARNING
    )
    message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["condition"]

    def __str__(self) -> str:
        return f"{self.product} · {self.condition} ({self.severity})"


class PriceList(models.Model):
    """A named price list (Wholesale, Retail, Promotional, Contract)."""

    class ListType(models.TextChoices):
        WHOLESALE = "WHOLESALE", "Wholesale"
        RETAIL = "RETAIL", "Retail"
        PROMOTIONAL = "PROMOTIONAL", "Promotional"
        CONTRACT = "CONTRACT", "Contract"

    name = models.CharField(max_length=255)
    list_type = models.CharField(
        max_length=20, choices=ListType.choices, default=ListType.RETAIL
    )
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.list_type})"


class ProductPrice(models.Model):
    """Specific price for a product in a price list, with optional volume tiering."""

    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name="prices")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="prices")
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    min_quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["product__generic_name", "min_quantity"]
        constraints = [
            models.UniqueConstraint(
                fields=["price_list", "product", "min_quantity"],
                name="uniq_price_list_product_tier",
            )
        ]

    def __str__(self) -> str:
        return f"{self.price_list.name} · {self.product} · {self.unit_price} (min {self.min_quantity})"


class FormularyItem(models.Model):
    """Insurer coverage definition for a product (RSSB, CBHI, MMI, etc.)."""

    scheme_name = models.CharField(max_length=100)  # e.g. "RSSB / RAMA", "CBHI / Mutuelle"
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="formulary_items"
    )
    is_covered = models.BooleanField(default=True)
    max_reimbursable_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    copay_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    requires_prior_auth = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["scheme_name", "product__generic_name"]

    def __str__(self) -> str:
        return f"{self.scheme_name} · {self.product} (Covered: {self.is_covered})"


class ProductUomConversion(models.Model):
    """Packaging/Dispensing Unit of Measure conversion (e.g. Pack ↔ Strip ↔ Tablet)."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="uom_conversions"
    )
    unit_name = models.CharField(max_length=50)  # e.g. "Strip", "Tablet"
    conversion_factor = models.PositiveIntegerField(default=1)  # e.g. 10 units
    price_per_unit = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    is_default_dispensing = models.BooleanField(default=False)

    class Meta:
        ordering = ["product__generic_name", "unit_name"]

    def __str__(self) -> str:
        return f"{self.product} · {self.unit_name} ({self.conversion_factor}x)"


class ProductSubstitute(models.Model):
    """Generic or therapeutic alternative for a product."""

    class SubstituteType(models.TextChoices):
        GENERIC_EQUIVALENT = "GENERIC_EQUIVALENT", "Generic equivalent"
        THERAPEUTIC_ALTERNATIVE = "THERAPEUTIC_ALTERNATIVE", "Therapeutic alternative"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="substitutes")
    substitute_product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="substitute_for"
    )
    substitute_type = models.CharField(
        max_length=30, choices=SubstituteType.choices, default=SubstituteType.GENERIC_EQUIVALENT
    )
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "substitute_product"], name="uniq_product_substitute"
            )
        ]

    def __str__(self) -> str:
        return f"{self.product} ➔ {self.substitute_product} ({self.substitute_type})"

