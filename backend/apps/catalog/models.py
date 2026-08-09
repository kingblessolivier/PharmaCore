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

    created_at = models.DateTimeField(auto_now_add=True, null=True)

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
    ddd = models.CharField(
        max_length=50, blank=True, default=""
    )  # Defined Daily Dose (e.g. "500mg/day")
    is_essential = models.BooleanField(default=False)  # Essential Medicines List (WHO / EML)
    rxnorm_id = models.CharField(max_length=50, blank=True, default="")  # RxNorm identifier
    lifecycle_status = models.CharField(
        max_length=30, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE
    )

    #: How finely one base unit may legitimately be divided when dispensing.
    #:
    #: 1 means whole units only, 2 means halves, 4 means quarters. It defaults to
    #: 1 and is opt-in per product, because divisibility is a property of the
    #: physical tablet — only a *scored*, immediate-release tablet may be split.
    #: Halving an enteric-coated or modified-release tablet converts a 24-hour
    #: dose into an immediate one, which is a clinical harm rather than an
    #: inventory rounding, so the safe default is to refuse.
    divisibility = models.PositiveSmallIntegerField(default=1)
    #: Shown when a split is refused, so the refusal explains itself rather than
    #: looking like a bug at the counter.
    split_note = models.CharField(max_length=255, blank=True, default="")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["generic_name", "brand_name"]
        indexes = [models.Index(fields=["generic_name"]), models.Index(fields=["gtin"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(divisibility__in=(1, 2, 3, 4)),
                name="product_divisibility_is_a_real_split",
            )
        ]

    def __str__(self) -> str:
        return f"{self.generic_name} {self.strength}".strip()

    @property
    def base_unit(self) -> ProductUnit | None:
        """The smallest unit this product is counted in. Stock is always in these."""
        return next((u for u in self.units.all() if u.is_base), None)


class ProductUnit(models.Model):
    """One level of a product's packaging chain.

    A medicine is not counted in one unit; it is counted in a chain of them, and
    each party in the trade transacts at a different link. An importer buys a
    carton, a depot picks a case, a pharmacy shelves a pack, a counter sells a
    strip, and a patient swallows a tablet. Those are the same goods measured
    five ways, and a system that stores a bare number has thrown away which one
    was meant — so a depot shipping "10" and a pharmacy receiving "10" can agree
    on the number and disagree by a factor of a hundred.

    Every level states its size in **base units**, never in the level above, so a
    conversion is one multiplication and cannot compound rounding through the
    chain.
    """

    class Code(models.TextChoices):
        # Discrete forms
        TABLET = "TABLET", "Tablet"
        CAPSULE = "CAPSULE", "Capsule"
        SACHET = "SACHET", "Sachet"
        SUPPOSITORY = "SUPPOSITORY", "Suppository"
        # Containers that are themselves the sellable thing
        BOTTLE = "BOTTLE", "Bottle"
        TUBE = "TUBE", "Tube"
        VIAL = "VIAL", "Vial"
        AMPOULE = "AMPOULE", "Ampoule"
        DEVICE = "DEVICE", "Device"
        BAG = "BAG", "Bag"
        # Packaging levels
        STRIP = "STRIP", "Strip"
        PACK = "PACK", "Pack"
        CASE = "CASE", "Case"
        CARTON = "CARTON", "Carton"
        # Measured, not counted
        ML = "ML", "Millilitre"
        G = "G", "Gram"
        UNIT = "UNIT", "Unit"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="units")
    code = models.CharField(max_length=20, choices=Code.choices)
    #: What a human calls it — "Box of 100", "Strip of 10".
    name = models.CharField(max_length=100, blank=True, default="")
    #: How many base units this level contains. Decimal so a dose unit (5 mL of a
    #: 100 mL bottle) can be expressed as well as a packaging one.
    factor_to_base = models.DecimalField(max_digits=14, decimal_places=3, default=1)
    #: 0 is the base; larger is further out. Used only for ordering a menu.
    level = models.PositiveSmallIntegerField(default=0)
    is_base = models.BooleanField(default=False)
    #: What procurement orders in, and what the counter sells in by default.
    is_purchase_default = models.BooleanField(default=False)
    is_sale_default = models.BooleanField(default=False)
    #: Under GS1 each packaging level carries its own GTIN, so a scanner can tell
    #: a case from the pack inside it.
    barcode = models.CharField(max_length=64, blank=True, default="")
    #: Price for one of *this* unit. Null falls back to the resolved base price
    #: times the factor, which is what a pharmacy that does not price packs
    #: separately actually wants.
    price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["product__generic_name", "level"]
        constraints = [
            models.UniqueConstraint(fields=["product", "code"], name="uniq_product_unit_code"),
            # One base, one purchase default, one sale default — per product.
            # Without these the conversion has no defined starting point and
            # "which unit did they mean" comes back as a different answer each
            # time depending on row order.
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(is_base=True),
                name="uniq_product_base_unit",
            ),
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(is_purchase_default=True),
                name="uniq_product_purchase_unit",
            ),
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(is_sale_default=True),
                name="uniq_product_sale_unit",
            ),
            models.CheckConstraint(
                condition=models.Q(factor_to_base__gt=0),
                name="product_unit_factor_is_positive",
            ),
            # The base unit is the one everything else is measured against, so
            # its own factor can only be 1.
            models.CheckConstraint(
                condition=~models.Q(is_base=True) | models.Q(factor_to_base=1),
                name="product_base_unit_factor_is_one",
            ),
        ]

    def __str__(self) -> str:
        label = self.name or self.get_code_display()
        return f"{self.product} · {label} ({self.factor_to_base}×)"


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
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MODERATE)
    effect = models.TextField(blank=True, default="")
    management = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, null=True)

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
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WARNING)
    message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["condition"]

    def __str__(self) -> str:
        return f"{self.product} · {self.condition} ({self.severity})"


class PriceList(models.Model):
    """A named price list (Wholesale, Retail, Promotional, Contract).

    ``organization`` is what makes the list *someone's*. Without it every active
    list applied to every pharmacy in the system, so one shop running a weekend
    promotion silently repriced its competitors and the depot. Null means a
    group-wide list set by HQ, which is a real and useful case — a chain running
    one price across its branches — so the field is nullable rather than required.
    """

    class ListType(models.TextChoices):
        WHOLESALE = "WHOLESALE", "Wholesale"
        RETAIL = "RETAIL", "Retail"
        PROMOTIONAL = "PROMOTIONAL", "Promotional"
        CONTRACT = "CONTRACT", "Contract"

    organization = models.ForeignKey(
        "iam.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="price_lists",
        help_text="Whose list this is. Empty means group-wide (set by HQ).",
    )
    name = models.CharField(max_length=255)
    list_type = models.CharField(max_length=20, choices=ListType.choices, default=ListType.RETAIL)
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
        return (
            f"{self.price_list.name} · {self.product} · {self.unit_price} (min {self.min_quantity})"
        )


class FormularyItem(models.Model):
    """Insurer coverage definition for a product (RSSB, CBHI, MMI, etc.)."""

    scheme_name = models.CharField(max_length=100)  # e.g. "RSSB / RAMA", "CBHI / Mutuelle"
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="formulary_items")
    is_covered = models.BooleanField(default=True)
    max_reimbursable_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    copay_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    requires_prior_auth = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["scheme_name", "product__generic_name"]

    def __str__(self) -> str:
        return f"{self.scheme_name} · {self.product} (Covered: {self.is_covered})"


class ProductUomConversion(models.Model):
    """Packaging/Dispensing Unit of Measure conversion (e.g. Pack ↔ Strip ↔ Tablet)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="uom_conversions")
    unit_name = models.CharField(max_length=50)  # e.g. "Strip", "Tablet"
    conversion_factor = models.PositiveIntegerField(default=1)  # e.g. 10 units
    price_per_unit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
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
