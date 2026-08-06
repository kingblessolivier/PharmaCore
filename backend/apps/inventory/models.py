"""Inventory models: per-pharmacy product listing, batch stock, storage zones/bins,
temperature logging, QA/quarantine, batch recalls, physical stock counts, and witness disposal.
See docs/02-data-model.md & 06-workflows."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models


class StorageZone(models.Model):
    """Warehouse / Pharmacy storage zone with climate controls."""

    class ZoneType(models.TextChoices):
        AMBIENT = "AMBIENT", "Ambient (15–25 °C)"
        COLD_CHAIN = "COLD_CHAIN", "Cold Chain (2–8 °C)"
        FREEZER = "FREEZER", "Freezer (-20 °C)"
        CONTROLLED_SAFE = "CONTROLLED_SAFE", "Controlled Substance Safe"
        HAZARDOUS = "HAZARDOUS", "Hazardous / Cytotoxic"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="storage_zones"
    )
    name = models.CharField(max_length=100)
    zone_type = models.CharField(
        max_length=30, choices=ZoneType.choices, default=ZoneType.AMBIENT
    )
    temp_min_celsius = models.DecimalField(
        max_digits=5, decimal_places=2, default=15.00
    )
    temp_max_celsius = models.DecimalField(
        max_digits=5, decimal_places=2, default=25.00
    )
    humidity_max_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=65.00
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="uniq_org_storage_zone"
            )
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} · {self.name} ({self.zone_type})"


class BinLocation(models.Model):
    """Specific aisle/shelf/bin location within a storage zone."""

    zone = models.ForeignKey(
        StorageZone, on_delete=models.CASCADE, related_name="bins"
    )
    aisle = models.CharField(max_length=20, blank=True, default="")
    shelf = models.CharField(max_length=20, blank=True, default="")
    bin_code = models.CharField(max_length=50)  # e.g., Z1-A02-S03-B04
    is_occupied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["zone", "bin_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["zone", "bin_code"], name="uniq_zone_bin_code"
            )
        ]

    def __str__(self) -> str:
        return f"{self.zone.name} · {self.bin_code}"


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
    bin_location = models.ForeignKey(
        BinLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="batches"
    )
    is_consignment = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    # Where this lot came from — for recall traceability. A supplier (depot intake)
    # or another organization (a depot it was transferred from).
    source_supplier = models.ForeignKey(
        "catalog.Supplier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supplied_batches",
    )
    source_org = models.ForeignKey(
        "iam.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
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


class TemperatureSensor(models.Model):
    """Calibrated sensor monitoring climate in a storage zone."""

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="temp_sensors"
    )
    zone = models.ForeignKey(
        StorageZone, on_delete=models.CASCADE, related_name="sensors"
    )
    device_id = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    calibration_due_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["zone", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.device_id})"


class TemperatureLog(models.Model):
    """Environmental reading logged by a sensor."""

    class ExcursionStatus(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        WARNING = "WARNING", "Warning"
        CRITICAL_BREACH = "CRITICAL_BREACH", "Critical Excursion Breach"

    sensor = models.ForeignKey(
        TemperatureSensor, on_delete=models.CASCADE, related_name="logs"
    )
    temperature_celsius = models.DecimalField(max_digits=5, decimal_places=2)
    humidity_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    excursion_status = models.CharField(
        max_length=25, choices=ExcursionStatus.choices, default=ExcursionStatus.NORMAL
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self) -> str:
        return f"{self.sensor.name} · {self.temperature_celsius}°C ({self.excursion_status})"


class QualityCheck(models.Model):
    """Inbound Quality Assurance & Quarantine Inspection record."""

    class Status(models.TextChoices):
        PASSED = "PASSED", "Passed QC & Released"
        FAILED = "FAILED", "Failed QC & Rejected"
        PENDING_REVIEW = "PENDING_REVIEW", "Pending Review"

    batch = models.ForeignKey(
        InventoryBatch, on_delete=models.CASCADE, related_name="quality_checks"
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    inspection_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING_REVIEW
    )
    visual_integrity_ok = models.BooleanField(default=True)
    temp_indicator_ok = models.BooleanField(default=True)
    coa_document_url = models.CharField(max_length=255, blank=True, default="")
    inspection_notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-inspection_date"]

    def __str__(self) -> str:
        return f"QC {self.status} · {self.batch}"


class BatchRecall(models.Model):
    """Company-wide emergency batch recall & freeze order."""

    class Status(models.TextChoices):
        INITIATED = "INITIATED", "Initiated / Frozen"
        IN_PROGRESS = "IN_PROGRESS", "Quarantine in Progress"
        COMPLETED = "COMPLETED", "Completed & Disposed"

    company = models.ForeignKey(
        "iam.Company", null=True, blank=True, on_delete=models.CASCADE, related_name="recalls"
    )
    recall_reference = models.CharField(max_length=100, unique=True)
    manufacturer_name = models.CharField(max_length=100, blank=True, default="")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    batch_number = models.CharField(max_length=100)
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.INITIATED
    )
    recalled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recalled_at"]

    def __str__(self) -> str:
        return f"Recall {self.recall_reference} · Batch {self.batch_number}"


class StockCount(models.Model):
    """Physical inventory audit session."""

    class CountType(models.TextChoices):
        CYCLE_COUNT = "CYCLE_COUNT", "Cycle Count (ABC)"
        FULL_PHYSICAL = "FULL_PHYSICAL", "Full Physical Count"
        SPOT_CHECK = "SPOT_CHECK", "Spot Check"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        SUBMITTED = "SUBMITTED", "Submitted for Approval"
        APPROVED = "APPROVED", "Approved & Reconciled"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="stock_counts"
    )
    reference_no = models.CharField(max_length=100, unique=True)
    count_type = models.CharField(
        max_length=20, choices=CountType.choices, default=CountType.CYCLE_COUNT
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    counter_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="counted_audits"
    )
    approver_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_audits"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"StockCount {self.reference_no} ({self.status})"


class StockCountItem(models.Model):
    """Individual line item variance in a stock count."""

    stock_count = models.ForeignKey(
        StockCount, on_delete=models.CASCADE, related_name="items"
    )
    batch = models.ForeignKey(InventoryBatch, on_delete=models.CASCADE)
    system_qty = models.IntegerField()
    counted_qty = models.IntegerField()
    variance_qty = models.IntegerField()  # counted - system
    variance_reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["batch__product__generic_name"]

    def __str__(self) -> str:
        return f"{self.batch} · Var {self.variance_qty:+d}"


class StockDisposal(models.Model):
    """Expired or damaged stock disposal & witnessed destruction record."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved for Destruction"
        DESTROYED = "DESTROYED", "Destroyed & Certified"

    class Reason(models.TextChoices):
        EXPIRED = "EXPIRED", "Expired Stock"
        DAMAGED = "DAMAGED", "Damaged / Compromised Stock"
        RECALLED = "RECALLED", "Recalled Stock"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="disposals"
    )
    disposal_no = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    reason = models.CharField(
        max_length=20, choices=Reason.choices, default=Reason.EXPIRED
    )
    primary_witness = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="witnessed_disposals_primary"
    )
    secondary_witness_name = models.CharField(max_length=100, blank=True, default="")
    destruction_method = models.CharField(max_length=100, blank=True, default="INCINERATION")
    certificate_no = models.CharField(max_length=100, blank=True, default="")
    destroyed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Disposal {self.disposal_no} ({self.status})"


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
