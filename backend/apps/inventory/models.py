"""Inventory models: warehouses, per-pharmacy product listing, batch stock, storage
zones/bins, temperature logging & the calibrated-sensor register, QA/quarantine, batch
recalls, physical stock counts, witness disposal, reorder policy, GS1 serialisation &
EPCIS, consignment/VMI and wave picking. See docs/02-data-model.md & 06-workflows."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone


class Warehouse(models.Model):
    """A physical storage facility belonging to an organization.

    One org can run several (main distribution store, a satellite cross-dock, a
    bonded warehouse under customs control, the quarantine store). Storage zones —
    and through them bins and batches — hang off a warehouse, so stock is
    addressable down to facility → zone → bin.
    """

    class Type(models.TextChoices):
        MAIN = "MAIN", "Main distribution store"
        SATELLITE = "SATELLITE", "Satellite / cross-dock"
        COLD_STORE = "COLD_STORE", "Dedicated cold store"
        BONDED = "BONDED", "Bonded (customs-controlled)"
        QUARANTINE = "QUARANTINE", "Quarantine / hold store"
        DISPENSARY = "DISPENSARY", "Dispensary back-store"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="warehouses"
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    warehouse_type = models.CharField(max_length=20, choices=Type.choices, default=Type.MAIN)
    address_line = models.CharField(max_length=255, blank=True, default="")
    district = models.CharField(max_length=100, blank=True, default="")
    contact_person = models.CharField(max_length=150, blank=True, default="")
    contact_phone = models.CharField(max_length=30, blank=True, default="")
    # Where stock lands when a receipt does not name a warehouse.
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="uniq_org_warehouse_code"
            ),
            # At most one default per org — a receipt must never be ambiguous.
            models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(is_default=True),
                name="uniq_org_default_warehouse",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


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
    # Which facility this zone sits in. Nullable so single-site orgs (and every
    # zone created before multi-warehouse) keep working untouched.
    warehouse = models.ForeignKey(
        "Warehouse", null=True, blank=True, on_delete=models.SET_NULL, related_name="zones"
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
    warehouse = models.ForeignKey(
        "Warehouse", null=True, blank=True, on_delete=models.SET_NULL, related_name="batches"
    )
    bin_location = models.ForeignKey(
        BinLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="batches"
    )
    # Consignment: the stock sits here but title stays with the owner named on the
    # agreement until it is consumed. Never mix owned and consigned in one lot.
    is_consignment = models.BooleanField(default=False)
    consignment_agreement = models.ForeignKey(
        "ConsignmentAgreement",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="batches",
    )
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
    """A monitoring device on the calibrated-sensor register.

    GDP treats an uncalibrated reading as no reading at all, so the device carries
    its own identity (make/model/serial), its stated accuracy, and the date its
    calibration expires. ``calibration_state`` is what an inspector actually asks
    for — is this probe in date today?
    """

    class DeviceType(models.TextChoices):
        DATA_LOGGER = "DATA_LOGGER", "Data logger"
        WIRELESS_PROBE = "WIRELESS_PROBE", "Wireless probe"
        CHART_RECORDER = "CHART_RECORDER", "Chart recorder"
        MIN_MAX_THERMOMETER = "MIN_MAX_THERMOMETER", "Min/max thermometer"
        IOT_GATEWAY = "IOT_GATEWAY", "IoT gateway sensor"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="temp_sensors"
    )
    zone = models.ForeignKey(
        StorageZone, on_delete=models.CASCADE, related_name="sensors"
    )
    device_id = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    device_type = models.CharField(
        max_length=25, choices=DeviceType.choices, default=DeviceType.DATA_LOGGER
    )
    manufacturer = models.CharField(max_length=150, blank=True, default="")
    model_number = models.CharField(max_length=100, blank=True, default="")
    serial_number = models.CharField(max_length=100, blank=True, default="")
    # Stated measurement uncertainty, e.g. ±0.50 °C — feeds excursion judgement.
    accuracy_celsius = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    installed_on = models.DateField(null=True, blank=True)
    last_calibration_date = models.DateField(null=True, blank=True)
    calibration_due_date = models.DateField(null=True, blank=True)
    calibration_interval_months = models.PositiveIntegerField(default=12)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["zone", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.device_id})"

    @property
    def calibration_state(self) -> str:
        """``VALID`` / ``DUE_SOON`` (≤30 days) / ``OVERDUE`` / ``UNKNOWN``."""
        from datetime import date, timedelta

        if not self.calibration_due_date:
            return "UNKNOWN"
        today = date.today()
        if self.calibration_due_date < today:
            return "OVERDUE"
        if self.calibration_due_date <= today + timedelta(days=30):
            return "DUE_SOON"
        return "VALID"


class SensorCalibration(models.Model):
    """One calibration event on a sensor's register — the certificate trail.

    Recording a PASS/ADJUSTED calibration rolls the sensor's own
    ``last_calibration_date`` / ``calibration_due_date`` forward; a FAIL leaves the
    sensor overdue, which is the honest state until it is fixed or replaced.
    """

    class Result(models.TextChoices):
        PASS = "PASS", "Pass — within tolerance"
        ADJUSTED = "ADJUSTED", "Passed after adjustment"
        FAIL = "FAIL", "Fail — withdrawn from service"

    sensor = models.ForeignKey(
        TemperatureSensor, on_delete=models.CASCADE, related_name="calibrations"
    )
    certificate_no = models.CharField(max_length=100)
    calibrated_on = models.DateField()
    next_due_on = models.DateField()
    calibrated_by = models.CharField(max_length=150, blank=True, default="")
    # Deviation the lab measured against the reference standard.
    deviation_celsius = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True
    )
    accuracy_celsius = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    result = models.CharField(max_length=10, choices=Result.choices, default=Result.PASS)
    reference_standard = models.CharField(max_length=150, blank=True, default="")
    certificate_url = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-calibrated_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["sensor", "certificate_no"], name="uniq_sensor_calibration_cert"
            )
        ]

    def __str__(self) -> str:
        return f"{self.sensor.name} · {self.certificate_no} ({self.result})"


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
    # Settable (not auto_now_add): a data logger uploads a buffer of readings whose
    # real timestamps are in the past, and MKT over a window is only meaningful if
    # each reading keeps the moment it was actually taken.
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self) -> str:
        return f"{self.sensor.name} · {self.temperature_celsius}°C ({self.excursion_status})"


class ExcursionInvestigation(models.Model):
    """A temperature excursion worked through to a documented product decision.

    An alert is not enough: GDP wants the window bounded, the exposure quantified
    (min/max plus **mean kinetic temperature** over the window — a single figure
    that expresses the cumulative thermal stress), the affected lots named, a root
    cause, and a **disposition** signed by QA. Closing the investigation is what
    applies that disposition to the batches, so stock can never quietly resume
    selling after an excursion nobody signed off.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open — data gathering"
        UNDER_REVIEW = "UNDER_REVIEW", "Under QA review"
        CLOSED = "CLOSED", "Closed — disposition applied"

    class Disposition(models.TextChoices):
        PENDING = "PENDING", "Pending assessment"
        RELEASE = "RELEASE", "Release — product unaffected"
        QUARANTINE = "QUARANTINE", "Quarantine pending further data"
        DESTROY = "DESTROY", "Destroy — product compromised"
        RETURN_TO_SUPPLIER = "RETURN_TO_SUPPLIER", "Return to supplier"

    class Severity(models.TextChoices):
        MINOR = "MINOR", "Minor — brief, within stability data"
        MAJOR = "MAJOR", "Major — outside label storage"
        CRITICAL = "CRITICAL", "Critical — product safety at risk"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="excursion_investigations"
    )
    reference_no = models.CharField(max_length=100, unique=True)
    sensor = models.ForeignKey(
        TemperatureSensor, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="investigations",
    )
    zone = models.ForeignKey(
        StorageZone, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="investigations",
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    min_temp_celsius = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_temp_celsius = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # Mean kinetic temperature over the excursion window (Arrhenius-weighted).
    mkt_celsius = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    readings_count = models.PositiveIntegerField(default=0)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MINOR)
    affected_batches = models.ManyToManyField(
        InventoryBatch, blank=True, related_name="excursion_investigations"
    )
    root_cause = models.TextField(blank=True, default="")
    impact_assessment = models.TextField(blank=True, default="")
    corrective_action = models.TextField(blank=True, default="")
    disposition = models.CharField(
        max_length=20, choices=Disposition.choices, default=Disposition.PENDING
    )
    disposition_rationale = models.TextField(blank=True, default="")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="opened_excursions",
    )
    qa_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="approved_excursions",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"Excursion {self.reference_no} ({self.status}/{self.disposition})"


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


class ReorderRule(models.Model):
    """The replenishment policy for one product at one organization.

    Min/max, reorder point and par level are the levers a buyer actually turns;
    ``avg_daily_demand``/``demand_std_dev``/``abc_class``/``xyz_class`` are what the
    analytics engine writes back so the levers can be set from evidence rather than
    habit. A rule with ``is_auto_calculated`` lets the engine recompute the point
    each run; clear it to pin hand-set numbers the engine must not touch.
    """

    class ABC(models.TextChoices):
        A = "A", "A — top 80 % of consumption value"
        B = "B", "B — next 15 %"
        C = "C", "C — bottom 5 %"

    class XYZ(models.TextChoices):
        X = "X", "X — steady demand (CV < 0.5)"
        Y = "Y", "Y — variable demand (CV 0.5–1.0)"
        Z = "Z", "Z — erratic demand (CV > 1.0)"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="reorder_rules"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="reorder_rules"
    )
    warehouse = models.ForeignKey(
        Warehouse, null=True, blank=True, on_delete=models.SET_NULL, related_name="reorder_rules"
    )
    min_level = models.PositiveIntegerField(default=0)
    max_level = models.PositiveIntegerField(default=0)
    # Cross this and it is time to buy: lead-time demand + safety stock.
    reorder_point = models.PositiveIntegerField(default=0)
    reorder_quantity = models.PositiveIntegerField(default=0)
    # Top-up target for a periodic-review item (order up to par).
    par_level = models.PositiveIntegerField(default=0)
    safety_stock = models.PositiveIntegerField(default=0)
    lead_time_days = models.PositiveIntegerField(default=7)
    review_period_days = models.PositiveIntegerField(default=30)
    service_level_percent = models.DecimalField(max_digits=5, decimal_places=2, default=95)
    avg_daily_demand = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    demand_std_dev = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    annual_consumption_value = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    abc_class = models.CharField(max_length=1, choices=ABC.choices, blank=True, default="")
    xyz_class = models.CharField(max_length=1, choices=XYZ.choices, blank=True, default="")
    preferred_supplier = models.ForeignKey(
        "catalog.Supplier", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reorder_rules",
    )
    is_auto_calculated = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    last_computed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization", "product__generic_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "product"], name="uniq_org_product_reorder_rule"
            )
        ]
        indexes = [models.Index(fields=["organization", "abc_class"])]

    def __str__(self) -> str:
        return f"{self.product} · ROP {self.reorder_point} / max {self.max_level}"


class SerialUnit(models.Model):
    """One serialised physical thing — a saleable pack, a case, or a pallet.

    A pack carries an **SGTIN** (GTIN + serial, from AIs 01 + 21 of the DataMatrix);
    a case or pallet carries an **SSCC** (AI 00). ``parent`` is the aggregation link
    (each → case → pallet), so scanning a pallet resolves every pack on it and a
    recall can name exactly which units shipped where.
    """

    class Level(models.TextChoices):
        EACH = "EACH", "Each / saleable pack"
        CASE = "CASE", "Case / shipper"
        PALLET = "PALLET", "Pallet / logistic unit"

    class Status(models.TextChoices):
        COMMISSIONED = "COMMISSIONED", "Commissioned"
        IN_STOCK = "IN_STOCK", "In stock"
        IN_TRANSIT = "IN_TRANSIT", "In transit"
        DISPENSED = "DISPENSED", "Dispensed / sold"
        RETURNED = "RETURNED", "Returned"
        RECALLED = "RECALLED", "Recalled"
        DESTROYED = "DESTROYED", "Destroyed"
        DECOMMISSIONED = "DECOMMISSIONED", "Decommissioned"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="serial_units"
    )
    product = models.ForeignKey(
        "catalog.Product", null=True, blank=True, on_delete=models.PROTECT,
        related_name="serial_units",
    )
    batch = models.ForeignKey(
        InventoryBatch, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="serial_units",
    )
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.EACH)
    gtin = models.CharField(max_length=14, blank=True, default="")
    serial = models.CharField(max_length=64, blank=True, default="")
    sscc = models.CharField(max_length=18, blank=True, default="")
    # Canonical EPC URI (urn:epc:id:sgtin:… / urn:epc:id:sscc:…) used in EPCIS.
    epc = models.CharField(max_length=150, blank=True, default="")
    batch_number = models.CharField(max_length=100, blank=True, default="")
    expiry_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)  # eaches contained
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMMISSIONED)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    current_bin = models.ForeignKey(
        BinLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="serial_units"
    )
    last_scanned_at = models.DateTimeField(null=True, blank=True)
    commissioned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-commissioned_at"]
        constraints = [
            # SGTIN uniqueness: a GTIN+serial pair identifies exactly one pack.
            models.UniqueConstraint(
                fields=["organization", "gtin", "serial"],
                condition=~models.Q(serial=""),
                name="uniq_org_sgtin",
            ),
            # SSCC uniqueness for logistic units.
            models.UniqueConstraint(
                fields=["organization", "sscc"],
                condition=~models.Q(sscc=""),
                name="uniq_org_sscc",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["gtin", "serial"]),
            models.Index(fields=["batch_number"]),
        ]

    def __str__(self) -> str:
        return self.epc or self.sscc or f"{self.gtin}/{self.serial}"


class EpcisEvent(models.Model):
    """An EPCIS 2.0 visibility event — the what/when/where/why of a scan.

    Kept as first-class rows (rather than derived at export time) because
    track-&-trace is an evidentiary record: the event is written when the scan
    happens and is never rewritten. ``export`` renders these to EPCIS 2.0 JSON-LD
    for a regulator or an export-market trading partner.
    """

    class EventType(models.TextChoices):
        OBJECT = "OBJECT", "ObjectEvent"
        AGGREGATION = "AGGREGATION", "AggregationEvent"
        TRANSACTION = "TRANSACTION", "TransactionEvent"
        TRANSFORMATION = "TRANSFORMATION", "TransformationEvent"

    class Action(models.TextChoices):
        ADD = "ADD", "ADD"
        OBSERVE = "OBSERVE", "OBSERVE"
        DELETE = "DELETE", "DELETE"

    class BizStep(models.TextChoices):
        COMMISSIONING = "commissioning", "Commissioning"
        PACKING = "packing", "Packing / aggregating"
        UNPACKING = "unpacking", "Unpacking / disaggregating"
        RECEIVING = "receiving", "Receiving"
        SHIPPING = "shipping", "Shipping"
        INSPECTING = "inspecting", "Inspecting"
        STORING = "storing", "Storing"
        DISPENSING = "dispensing", "Dispensing"
        DESTROYING = "destroying", "Destroying"
        HOLDING = "holding", "Holding"

    class Disposition(models.TextChoices):
        ACTIVE = "active", "Active"
        IN_PROGRESS = "in_progress", "In progress"
        IN_TRANSIT = "in_transit", "In transit"
        SELLABLE_ACCESSIBLE = "sellable_accessible", "Sellable — accessible"
        NON_SELLABLE_EXPIRED = "non_sellable_expired", "Non-sellable — expired"
        RECALLED = "recalled", "Recalled"
        DESTROYED = "destroyed", "Destroyed"
        RETAIL_SOLD = "retail_sold", "Retail sold / dispensed"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="epcis_events"
    )
    event_id = models.CharField(max_length=64, unique=True)
    event_type = models.CharField(
        max_length=20, choices=EventType.choices, default=EventType.OBJECT
    )
    action = models.CharField(max_length=10, choices=Action.choices, default=Action.OBSERVE)
    biz_step = models.CharField(max_length=30, choices=BizStep.choices, blank=True, default="")
    disposition = models.CharField(
        max_length=30, choices=Disposition.choices, blank=True, default=""
    )
    event_time = models.DateTimeField(default=timezone.now)
    record_time = models.DateTimeField(auto_now_add=True)
    read_point = models.CharField(max_length=150, blank=True, default="")
    biz_location = models.CharField(max_length=150, blank=True, default="")
    # EPC URIs touched by the event; parent_epc set for AggregationEvents.
    epc_list = models.JSONField(default=list, blank=True)
    parent_epc = models.CharField(max_length=150, blank=True, default="")
    quantity_list = models.JSONField(default=list, blank=True)
    reference_type = models.CharField(max_length=50, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-event_time"]
        indexes = [models.Index(fields=["organization", "event_time"])]

    def __str__(self) -> str:
        return f"{self.event_type}/{self.biz_step or '—'} @ {self.event_time:%Y-%m-%d %H:%M}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValueError("EPCIS events are an evidentiary record and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("EPCIS events are an evidentiary record and cannot be deleted.")


class ConsignmentAgreement(models.Model):
    """Who owns stock that is not where its owner is.

    ``SUPPLIER_OWNED`` — a supplier's stock sits in our warehouse; we owe for it
    only as it is consumed. ``CUSTOMER_HELD`` — our stock sits at a customer's site;
    it stays ours (and on our balance sheet) until they use it. Either way the
    physical location and the ownership are tracked apart, which is the whole point.
    """

    class Direction(models.TextChoices):
        SUPPLIER_OWNED = "SUPPLIER_OWNED", "Supplier-owned stock held by us (VMI in)"
        CUSTOMER_HELD = "CUSTOMER_HELD", "Our stock held at a customer (VMI out)"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        CLOSED = "CLOSED", "Closed"

    class Settlement(models.TextChoices):
        ON_CONSUMPTION = "ON_CONSUMPTION", "On each consumption"
        WEEKLY = "WEEKLY", "Weekly"
        FORTNIGHTLY = "FORTNIGHTLY", "Fortnightly"
        MONTHLY = "MONTHLY", "Monthly"

    class TitleTransfer(models.TextChoices):
        ON_CONSUMPTION = "ON_CONSUMPTION", "On consumption / sale"
        ON_RECEIPT = "ON_RECEIPT", "On receipt into the store"
        ON_PERIOD_END = "ON_PERIOD_END", "At period end"

    # The organization on *our* side of the agreement.
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="consignment_agreements"
    )
    agreement_no = models.CharField(max_length=100, unique=True)
    direction = models.CharField(
        max_length=20, choices=Direction.choices, default=Direction.SUPPLIER_OWNED
    )
    # Owner of the goods when direction = SUPPLIER_OWNED.
    owner_supplier = models.ForeignKey(
        "catalog.Supplier", null=True, blank=True, on_delete=models.PROTECT,
        related_name="consignment_agreements",
    )
    # Site holding the goods when direction = CUSTOMER_HELD.
    holder_organization = models.ForeignKey(
        "iam.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    holder_name = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    settlement_frequency = models.CharField(
        max_length=20, choices=Settlement.choices, default=Settlement.MONTHLY
    )
    title_transfer = models.CharField(
        max_length=20, choices=TitleTransfer.choices, default=TitleTransfer.ON_CONSUMPTION
    )
    payment_terms_days = models.PositiveIntegerField(default=30)
    currency = models.CharField(max_length=3, default="RWF")
    # Who carries the loss if the stock is damaged/expires while held.
    liability_holder = models.CharField(
        max_length=10,
        choices=[("OWNER", "Owner of the goods"), ("HOLDER", "Site holding the goods")],
        default="OWNER",
    )
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    terms = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"{self.agreement_no} · {self.direction} ({self.status})"

    @property
    def counterparty_name(self) -> str:
        if self.owner_supplier_id:
            return self.owner_supplier.name
        if self.holder_organization_id:
            return self.holder_organization.name
        return self.holder_name


class ConsignmentConsumption(models.Model):
    """A consumption of consigned stock — the moment that triggers payment.

    Written automatically whenever a consigned batch is drawn down (sale, transfer
    out, wastage). Until a row is settled it is the outstanding liability to the
    stock's owner.
    """

    agreement = models.ForeignKey(
        ConsignmentAgreement, on_delete=models.CASCADE, related_name="consumptions"
    )
    batch = models.ForeignKey(
        InventoryBatch, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="consignment_consumptions",
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    batch_number = models.CharField(max_length=100, blank=True, default="")
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    movement = models.ForeignKey(
        "StockMovement", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    trigger = models.CharField(max_length=30, blank=True, default="")
    settlement = models.ForeignKey(
        "ConsignmentSettlement", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="consumptions",
    )
    consumed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-consumed_at"]
        indexes = [models.Index(fields=["agreement", "settlement"])]

    def __str__(self) -> str:
        return f"{self.product} ×{self.quantity} on {self.agreement.agreement_no}"


class ConsignmentSettlement(models.Model):
    """A period's consumptions rolled up and billed to (or by) the owner."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        INVOICED = "INVOICED", "Invoiced"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"

    agreement = models.ForeignKey(
        ConsignmentAgreement, on_delete=models.CASCADE, related_name="settlements"
    )
    settlement_no = models.CharField(max_length=100, unique=True)
    period_start = models.DateField()
    period_end = models.DateField()
    total_quantity = models.PositiveIntegerField(default=0)
    total_value = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    lines_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    # The AP bill raised for a SUPPLIER_OWNED settlement (money we now owe).
    supplier_bill = models.ForeignKey(
        "finance.SupplierBill", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="consignment_settlements",
    )
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-period_end"]

    def __str__(self) -> str:
        return f"Settlement {self.settlement_no} ({self.status})"


class PutawayRule(models.Model):
    """Where a received lot should go, decided by policy rather than by whoever
    is holding the trolley.

    Rules are tried in ``priority`` order; the first whose criteria match the
    product wins, and its strategy picks the concrete bin.
    """

    class Strategy(models.TextChoices):
        FIXED_BIN = "FIXED_BIN", "Fixed bin (always the same slot)"
        ZONE_BY_CONDITION = "ZONE_BY_CONDITION", "Zone matching storage condition"
        NEAREST_EMPTY = "NEAREST_EMPTY", "Nearest empty bin in zone"
        ABC_VELOCITY = "ABC_VELOCITY", "Fast movers nearest dispatch"
        BULK_THEN_PICK = "BULK_THEN_PICK", "Bulk first, overflow to pick face"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="putaway_rules"
    )
    warehouse = models.ForeignKey(
        Warehouse, null=True, blank=True, on_delete=models.CASCADE, related_name="putaway_rules"
    )
    name = models.CharField(max_length=150)
    strategy = models.CharField(
        max_length=20, choices=Strategy.choices, default=Strategy.ZONE_BY_CONDITION
    )
    priority = models.PositiveIntegerField(default=100)  # lower runs first
    # Criteria — blank/null means "don't care".
    match_product = models.ForeignKey(
        "catalog.Product", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    match_zone_type = models.CharField(
        max_length=30, choices=StorageZone.ZoneType.choices, blank=True, default=""
    )
    match_controlled_only = models.BooleanField(default=False)
    match_cold_chain_only = models.BooleanField(default=False)
    match_abc_class = models.CharField(max_length=1, blank=True, default="")
    target_zone = models.ForeignKey(
        StorageZone, null=True, blank=True, on_delete=models.SET_NULL, related_name="putaway_rules"
    )
    target_bin = models.ForeignKey(
        BinLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="putaway_rules"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]
        indexes = [models.Index(fields=["organization", "is_active", "priority"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.strategy}, p{self.priority})"


class PickWave(models.Model):
    """A batch of orders released to the floor as one pass of picking work.

    ``DISCRETE`` walks one order at a time; ``BATCH`` merges the same product
    across orders; ``ZONE`` splits the work by storage zone so pickers stay in
    their area; ``WAVE`` is a time-boxed release of both.
    """

    class Strategy(models.TextChoices):
        DISCRETE = "DISCRETE", "Discrete — one order at a time"
        BATCH = "BATCH", "Batch — same product across orders"
        ZONE = "ZONE", "Zone — split by storage zone"
        WAVE = "WAVE", "Wave — time-boxed release"
        CLUSTER = "CLUSTER", "Cluster — multi-order cart"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        RELEASED = "RELEASED", "Released to floor"
        PICKING = "PICKING", "Picking in progress"
        PICKED = "PICKED", "Picked"
        CANCELLED = "CANCELLED", "Cancelled"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="pick_waves"
    )
    warehouse = models.ForeignKey(
        Warehouse, null=True, blank=True, on_delete=models.SET_NULL, related_name="pick_waves"
    )
    wave_no = models.CharField(max_length=50, unique=True)
    strategy = models.CharField(
        max_length=15, choices=Strategy.choices, default=Strategy.DISCRETE
    )
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    planned_for = models.DateField(null=True, blank=True)
    zone = models.ForeignKey(
        StorageZone, null=True, blank=True, on_delete=models.SET_NULL, related_name="pick_waves"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assigned_waves",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.TextField(blank=True, default="")
    released_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"Wave {self.wave_no} ({self.strategy}/{self.status})"


class PickTask(models.Model):
    """One line of picking work: take this quantity of this lot from this bin.

    Generated FEFO-first from the wave's source orders, then ordered by
    zone/aisle/bin so the picker walks the shortest sensible path.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ASSIGNED = "ASSIGNED", "Assigned"
        PICKED = "PICKED", "Picked"
        SHORT = "SHORT", "Short picked"
        CANCELLED = "CANCELLED", "Cancelled"

    wave = models.ForeignKey(PickWave, on_delete=models.CASCADE, related_name="tasks")
    sequence = models.PositiveIntegerField(default=0)
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    batch = models.ForeignKey(
        InventoryBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="pick_tasks"
    )
    batch_number = models.CharField(max_length=100, blank=True, default="")
    expiry_date = models.DateField(null=True, blank=True)
    zone = models.ForeignKey(
        StorageZone, null=True, blank=True, on_delete=models.SET_NULL, related_name="pick_tasks"
    )
    bin_location = models.ForeignKey(
        BinLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="pick_tasks"
    )
    quantity_requested = models.PositiveIntegerField()
    quantity_picked = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    picker = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="pick_tasks",
    )
    # The demand this line serves (e.g. a distribution stock order).
    reference_type = models.CharField(max_length=50, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="")
    short_reason = models.CharField(max_length=255, blank=True, default="")
    picked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["wave", "sequence"]
        indexes = [models.Index(fields=["wave", "status"])]

    def __str__(self) -> str:
        return f"#{self.sequence} {self.product} ×{self.quantity_requested}"


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
