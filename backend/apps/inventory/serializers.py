from __future__ import annotations

from typing import Any

from django.utils import timezone
from rest_framework import serializers

from apps.catalog.models import Product, Supplier
from apps.iam.models import Organization
from apps.inventory.models import (
    BatchRecall,
    BinLocation,
    ConsignmentAgreement,
    ConsignmentConsumption,
    ConsignmentSettlement,
    EpcisEvent,
    ExcursionInvestigation,
    InventoryBatch,
    PharmacyProduct,
    PickTask,
    PickWave,
    PutawayRule,
    QualityCheck,
    ReorderRule,
    SensorCalibration,
    SerialUnit,
    StockCount,
    StockCountItem,
    StockDisposal,
    StockMovement,
    StorageZone,
    TemperatureLog,
    TemperatureSensor,
    Warehouse,
)


class WarehouseSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    zones_count = serializers.SerializerMethodField()
    bins_count = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "organization",
            "organization_name",
            "code",
            "name",
            "warehouse_type",
            "address_line",
            "district",
            "contact_person",
            "contact_phone",
            "is_default",
            "is_active",
            "zones_count",
            "bins_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_zones_count(self, obj: Warehouse) -> int:
        return obj.zones.count()

    def get_bins_count(self, obj: Warehouse) -> int:
        return BinLocation.objects.filter(zone__warehouse=obj).count()


class StorageZoneSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default=None)
    bins_count = serializers.SerializerMethodField()

    class Meta:
        model = StorageZone
        fields = [
            "id",
            "organization",
            "organization_name",
            "warehouse",
            "warehouse_name",
            "name",
            "zone_type",
            "temp_min_celsius",
            "temp_max_celsius",
            "humidity_max_percent",
            "is_active",
            "bins_count",
            "created_at",
        ]

    def get_bins_count(self, obj: StorageZone) -> int:
        return obj.bins.count()


class BinLocationSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source="zone.name", read_only=True)

    class Meta:
        model = BinLocation
        fields = [
            "id",
            "zone",
            "zone_name",
            "aisle",
            "shelf",
            "bin_code",
            "is_occupied",
            "created_at",
        ]


class TemperatureSensorSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    calibration_state = serializers.CharField(read_only=True)
    latest_reading = serializers.SerializerMethodField()

    class Meta:
        model = TemperatureSensor
        fields = [
            "id",
            "organization",
            "zone",
            "zone_name",
            "device_id",
            "name",
            "device_type",
            "manufacturer",
            "model_number",
            "serial_number",
            "accuracy_celsius",
            "installed_on",
            "last_calibration_date",
            "calibration_due_date",
            "calibration_interval_months",
            "calibration_state",
            "latest_reading",
            "is_active",
            "notes",
        ]

    def get_latest_reading(self, obj: TemperatureSensor) -> dict[str, object] | None:
        log = obj.logs.order_by("-recorded_at").first()
        if log is None:
            return None
        return {
            "temperature_celsius": str(log.temperature_celsius),
            "humidity_percent": str(log.humidity_percent) if log.humidity_percent else None,
            "excursion_status": log.excursion_status,
            "recorded_at": log.recorded_at.isoformat(),
        }


class SensorCalibrationSerializer(serializers.ModelSerializer):
    sensor_name = serializers.CharField(source="sensor.name", read_only=True)
    sensor_device_id = serializers.CharField(source="sensor.device_id", read_only=True)
    recorded_by_username = serializers.CharField(
        source="recorded_by.username", read_only=True, default=None
    )

    class Meta:
        model = SensorCalibration
        fields = [
            "id",
            "sensor",
            "sensor_name",
            "sensor_device_id",
            "certificate_no",
            "calibrated_on",
            "next_due_on",
            "calibrated_by",
            "deviation_celsius",
            "accuracy_celsius",
            "result",
            "reference_standard",
            "certificate_url",
            "notes",
            "recorded_by",
            "recorded_by_username",
            "created_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at"]


class ExcursionInvestigationSerializer(serializers.ModelSerializer):
    sensor_name = serializers.CharField(source="sensor.name", read_only=True, default=None)
    zone_name = serializers.CharField(source="zone.name", read_only=True, default=None)
    opened_by_username = serializers.CharField(
        source="opened_by.username", read_only=True, default=None
    )
    qa_approver_username = serializers.CharField(
        source="qa_approver.username", read_only=True, default=None
    )
    affected_batches_detail = serializers.SerializerMethodField()

    class Meta:
        model = ExcursionInvestigation
        fields = [
            "id",
            "organization",
            "reference_no",
            "sensor",
            "sensor_name",
            "zone",
            "zone_name",
            "started_at",
            "ended_at",
            "duration_minutes",
            "min_temp_celsius",
            "max_temp_celsius",
            "mkt_celsius",
            "readings_count",
            "severity",
            "affected_batches",
            "affected_batches_detail",
            "root_cause",
            "impact_assessment",
            "corrective_action",
            "disposition",
            "disposition_rationale",
            "status",
            "opened_by",
            "opened_by_username",
            "qa_approver",
            "qa_approver_username",
            "closed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "duration_minutes",
            "min_temp_celsius",
            "max_temp_celsius",
            "mkt_celsius",
            "readings_count",
            "severity",
            "opened_by",
            "qa_approver",
            "closed_at",
            "created_at",
        ]

    def get_affected_batches_detail(self, obj: ExcursionInvestigation) -> list[dict[str, object]]:
        return [
            {
                "id": b.id,
                "batch_number": b.batch_number,
                "product_name": f"{b.product.generic_name} {b.product.strength}".strip(),
                "quantity_available": b.quantity_available,
                "status": b.status,
            }
            for b in obj.affected_batches.select_related("product").all()
        ]


class TemperatureLogSerializer(serializers.ModelSerializer):
    sensor_name = serializers.CharField(source="sensor.name", read_only=True)

    class Meta:
        model = TemperatureLog
        fields = [
            "id",
            "sensor",
            "sensor_name",
            "temperature_celsius",
            "humidity_percent",
            "excursion_status",
            "recorded_at",
        ]


class QualityCheckSerializer(serializers.ModelSerializer):
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)
    product_name = serializers.SerializerMethodField()
    inspector_username = serializers.CharField(source="inspector.username", read_only=True)

    class Meta:
        model = QualityCheck
        fields = [
            "id",
            "batch",
            "batch_number",
            "product_name",
            "inspector",
            "inspector_username",
            "inspection_date",
            "status",
            "visual_integrity_ok",
            "temp_indicator_ok",
            "coa_document_url",
            "inspection_notes",
        ]
        read_only_fields = ["id", "inspector", "inspection_date"]

    def get_product_name(self, obj: QualityCheck) -> str:
        return f"{obj.batch.product.generic_name} {obj.batch.product.strength}".strip()


class BatchRecallSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()

    class Meta:
        model = BatchRecall
        fields = [
            "id",
            "company",
            "recall_reference",
            "manufacturer_name",
            "product",
            "product_name",
            "batch_number",
            "reason",
            "status",
            "recalled_at",
        ]

    def get_product_name(self, obj: BatchRecall) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class StockCountItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)

    class Meta:
        model = StockCountItem
        fields = [
            "id",
            "stock_count",
            "batch",
            "batch_number",
            "product_name",
            "system_qty",
            "counted_qty",
            "variance_qty",
            "variance_reason",
        ]

    def get_product_name(self, obj: StockCountItem) -> str:
        return f"{obj.batch.product.generic_name} {obj.batch.product.strength}".strip()


class StockCountSerializer(serializers.ModelSerializer):
    counter_username = serializers.CharField(source="counter_user.username", read_only=True)
    approver_username = serializers.CharField(
        source="approver_user.username", read_only=True, default=None
    )
    items = StockCountItemSerializer(many=True, read_only=True)

    class Meta:
        model = StockCount
        fields = [
            "id",
            "organization",
            "reference_no",
            "count_type",
            "status",
            "counter_user",
            "counter_username",
            "approver_user",
            "approver_username",
            "started_at",
            "completed_at",
            "items",
        ]
        read_only_fields = ["id", "counter_user", "started_at"]


class StockDisposalSerializer(serializers.ModelSerializer):
    primary_witness_username = serializers.CharField(
        source="primary_witness.username", read_only=True
    )

    class Meta:
        model = StockDisposal
        fields = [
            "id",
            "organization",
            "disposal_no",
            "status",
            "reason",
            "primary_witness",
            "primary_witness_username",
            "secondary_witness_name",
            "destruction_method",
            "certificate_no",
            "destroyed_at",
            "created_at",
        ]
        read_only_fields = ["id", "primary_witness", "created_at"]


class PharmacyProductSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    product_form = serializers.CharField(source="product.dosage_form", read_only=True)
    product_strength = serializers.CharField(source="product.strength", read_only=True)
    product_image = serializers.CharField(source="product.image_url", read_only=True)
    product_tax_class = serializers.CharField(source="product.tax_class", read_only=True)
    requires_prescription = serializers.BooleanField(
        source="product.requires_prescription", read_only=True
    )
    is_controlled = serializers.BooleanField(
        source="product.is_controlled_substance", read_only=True
    )
    on_hand = serializers.SerializerMethodField()
    avg_cost = serializers.SerializerMethodField()

    class Meta:
        model = PharmacyProduct
        fields = [
            "id",
            "organization",
            "product",
            "product_name",
            "product_form",
            "product_strength",
            "product_image",
            "product_tax_class",
            "requires_prescription",
            "is_controlled",
            "on_hand",
            "avg_cost",
            "retail_price",
            "wholesale_price",
            "min_stock_level",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "product_name",
            "product_form",
            "product_strength",
            "product_image",
            "product_tax_class",
            "requires_prescription",
            "is_controlled",
            "on_hand",
            "avg_cost",
            "created_at",
        ]

    def get_product_name(self, obj: PharmacyProduct) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()

    def get_on_hand(self, obj: PharmacyProduct) -> int:
        from django.db.models import Sum
        from django.utils import timezone

        total = InventoryBatch.objects.filter(
            organization=obj.organization,
            product=obj.product,
            status=InventoryBatch.Status.ACTIVE,
            expiry_date__gte=timezone.localdate(),
        ).aggregate(total=Sum("quantity_available"))["total"]
        return int(total or 0)

    def get_avg_cost(self, obj: PharmacyProduct) -> str | None:
        from django.db.models import Avg

        avg = InventoryBatch.objects.filter(
            organization=obj.organization,
            product=obj.product,
            wholesale_cost__isnull=False,
        ).aggregate(a=Avg("wholesale_cost"))["a"]
        return f"{avg:.2f}" if avg is not None else None


class InventoryBatchSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    days_to_expiry = serializers.SerializerMethodField()
    source_name = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default=None)
    bin_code = serializers.CharField(source="bin_location.bin_code", read_only=True, default=None)
    consignment_agreement_no = serializers.CharField(
        source="consignment_agreement.agreement_no", read_only=True, default=None
    )

    class Meta:
        model = InventoryBatch
        fields = [
            "id",
            "organization",
            "product",
            "product_name",
            "batch_number",
            "manufacture_date",
            "expiry_date",
            "days_to_expiry",
            "quantity_available",
            "quantity_reserved",
            "wholesale_cost",
            "storage_location",
            "warehouse",
            "warehouse_name",
            "bin_location",
            "bin_code",
            "is_consignment",
            "consignment_agreement",
            "consignment_agreement_no",
            "status",
            "source_supplier",
            "source_org",
            "source_name",
            "created_at",
        ]

    def get_source_name(self, obj: InventoryBatch) -> str | None:
        supplier = obj.source_supplier
        if supplier is not None:
            return supplier.name
        org = obj.source_org
        if org is not None:
            return org.name
        return None

    def get_product_name(self, obj: InventoryBatch) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()

    def get_days_to_expiry(self, obj: InventoryBatch) -> int:
        return (obj.expiry_date - timezone.localdate()).days


class IntakeSerializer(serializers.Serializer):
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    supplier = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(), required=False, allow_null=True
    )
    batch_number = serializers.CharField(max_length=100)
    expiry_date = serializers.DateField()
    manufacture_date = serializers.DateField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)
    wholesale_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    storage_location = serializers.CharField(max_length=100, required=False, allow_blank=True)


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    created_by = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "product",
            "product_name",
            "batch_number",
            "movement_type",
            "quantity_delta",
            "reference_type",
            "reason",
            "created_by",
            "occurred_at",
        ]

    def get_product_name(self, obj: StockMovement) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


# --- Replenishment ---------------------------------------------------------


class ReorderRuleSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default=None)
    preferred_supplier_name = serializers.CharField(
        source="preferred_supplier.name", read_only=True, default=None
    )
    on_hand = serializers.SerializerMethodField()

    class Meta:
        model = ReorderRule
        fields = [
            "id",
            "organization",
            "product",
            "product_name",
            "warehouse",
            "warehouse_name",
            "min_level",
            "max_level",
            "reorder_point",
            "reorder_quantity",
            "par_level",
            "safety_stock",
            "lead_time_days",
            "review_period_days",
            "service_level_percent",
            "avg_daily_demand",
            "demand_std_dev",
            "annual_consumption_value",
            "abc_class",
            "xyz_class",
            "preferred_supplier",
            "preferred_supplier_name",
            "is_auto_calculated",
            "is_active",
            "last_computed_at",
            "on_hand",
            "notes",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "avg_daily_demand",
            "demand_std_dev",
            "annual_consumption_value",
            "abc_class",
            "xyz_class",
            "last_computed_at",
            "created_at",
        ]

    def get_product_name(self, obj: ReorderRule) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()

    def get_on_hand(self, obj: ReorderRule) -> int:
        from django.db.models import Sum
        from django.utils import timezone

        total = InventoryBatch.objects.filter(
            organization=obj.organization,
            product=obj.product,
            status=InventoryBatch.Status.ACTIVE,
            expiry_date__gte=timezone.localdate(),
        ).aggregate(t=Sum("quantity_available"))["t"]
        return int(total or 0)


# --- Serialisation & track-and-trace ---------------------------------------


class SerialUnitSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    parent_epc = serializers.CharField(source="parent.epc", read_only=True, default=None)
    children_count = serializers.SerializerMethodField()
    bin_code = serializers.CharField(source="current_bin.bin_code", read_only=True, default=None)

    class Meta:
        model = SerialUnit
        fields = [
            "id",
            "organization",
            "product",
            "product_name",
            "batch",
            "level",
            "gtin",
            "serial",
            "sscc",
            "epc",
            "batch_number",
            "expiry_date",
            "quantity",
            "status",
            "parent",
            "parent_epc",
            "children_count",
            "current_bin",
            "bin_code",
            "last_scanned_at",
            "commissioned_at",
        ]
        read_only_fields = ["id", "epc", "commissioned_at", "last_scanned_at"]

    def get_product_name(self, obj: SerialUnit) -> str | None:
        product = obj.product
        if product is None:
            return None
        return f"{product.generic_name} {product.strength}".strip()

    def get_children_count(self, obj: SerialUnit) -> int:
        return obj.children.count()


class EpcisEventSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True, default=None
    )
    epc_count = serializers.SerializerMethodField()

    class Meta:
        model = EpcisEvent
        fields = [
            "id",
            "organization",
            "event_id",
            "event_type",
            "action",
            "biz_step",
            "disposition",
            "event_time",
            "record_time",
            "read_point",
            "biz_location",
            "epc_list",
            "epc_count",
            "parent_epc",
            "quantity_list",
            "reference_type",
            "reference_id",
            "created_by",
            "created_by_username",
        ]
        read_only_fields = fields

    def get_epc_count(self, obj: EpcisEvent) -> int:
        return len(obj.epc_list or [])


class ScanSerializer(serializers.Serializer):
    """A raw DataMatrix / barcode payload straight off the scanner wedge."""

    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all())
    scan = serializers.CharField(max_length=512)
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False, allow_null=True
    )
    batch = serializers.PrimaryKeyRelatedField(
        queryset=InventoryBatch.objects.all(), required=False, allow_null=True
    )
    read_point = serializers.CharField(max_length=150, required=False, allow_blank=True)


class AggregateSerializer(serializers.Serializer):
    children = serializers.PrimaryKeyRelatedField(
        queryset=SerialUnit.objects.all(), many=True, allow_empty=False
    )


class DisaggregateSerializer(serializers.Serializer):
    children = serializers.PrimaryKeyRelatedField(
        queryset=SerialUnit.objects.all(), many=True, required=False
    )


class ObserveSerializer(serializers.Serializer):
    units = serializers.PrimaryKeyRelatedField(
        queryset=SerialUnit.objects.all(), many=True, allow_empty=False
    )
    biz_step = serializers.ChoiceField(choices=EpcisEvent.BizStep.choices)
    read_point = serializers.CharField(max_length=150, required=False, allow_blank=True)
    reference_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    reference_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    cascade = serializers.BooleanField(required=False, default=True)


# --- Consignment / VMI -----------------------------------------------------


class ConsignmentAgreementSerializer(serializers.ModelSerializer):
    counterparty_name = serializers.CharField(read_only=True)
    owner_supplier_name = serializers.CharField(
        source="owner_supplier.name", read_only=True, default=None
    )
    holder_organization_name = serializers.CharField(
        source="holder_organization.name", read_only=True, default=None
    )
    position = serializers.SerializerMethodField()

    class Meta:
        model = ConsignmentAgreement
        fields = [
            "id",
            "organization",
            "agreement_no",
            "direction",
            "owner_supplier",
            "owner_supplier_name",
            "holder_organization",
            "holder_organization_name",
            "holder_name",
            "counterparty_name",
            "status",
            "start_date",
            "end_date",
            "settlement_frequency",
            "title_transfer",
            "payment_terms_days",
            "currency",
            "liability_holder",
            "credit_limit",
            "terms",
            "position",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]

    def get_position(self, obj: ConsignmentAgreement) -> dict[str, object]:
        from apps.inventory.warehouse_services import consignment_position

        return consignment_position(obj)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        direction = attrs.get("direction") or getattr(self.instance, "direction", None)
        owner = attrs.get("owner_supplier", getattr(self.instance, "owner_supplier", None))
        holder_org = attrs.get(
            "holder_organization", getattr(self.instance, "holder_organization", None)
        )
        holder_name = attrs.get("holder_name", getattr(self.instance, "holder_name", ""))
        if direction == ConsignmentAgreement.Direction.SUPPLIER_OWNED and owner is None:
            raise serializers.ValidationError(
                {"owner_supplier": "Supplier-owned stock must name the supplier that owns it."}
            )
        if direction == ConsignmentAgreement.Direction.CUSTOMER_HELD and not (
            holder_org or holder_name
        ):
            raise serializers.ValidationError(
                {"holder_name": "Name the site holding our stock (organization or free text)."}
            )
        start: Any = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end: Any = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date precedes the start date."})
        return attrs


class ConsignmentConsumptionSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    agreement_no = serializers.CharField(source="agreement.agreement_no", read_only=True)
    settlement_no = serializers.CharField(
        source="settlement.settlement_no", read_only=True, default=None
    )

    class Meta:
        model = ConsignmentConsumption
        fields = [
            "id",
            "agreement",
            "agreement_no",
            "batch",
            "product",
            "product_name",
            "batch_number",
            "quantity",
            "unit_cost",
            "total_value",
            "trigger",
            "settlement",
            "settlement_no",
            "consumed_at",
        ]
        read_only_fields = fields

    def get_product_name(self, obj: ConsignmentConsumption) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class ConsignmentSettlementSerializer(serializers.ModelSerializer):
    agreement_no = serializers.CharField(source="agreement.agreement_no", read_only=True)
    counterparty_name = serializers.CharField(source="agreement.counterparty_name", read_only=True)
    supplier_bill_no = serializers.CharField(
        source="supplier_bill.bill_number", read_only=True, default=None
    )

    class Meta:
        model = ConsignmentSettlement
        fields = [
            "id",
            "agreement",
            "agreement_no",
            "counterparty_name",
            "settlement_no",
            "period_start",
            "period_end",
            "total_quantity",
            "total_value",
            "lines_count",
            "status",
            "supplier_bill",
            "supplier_bill_no",
            "notes",
            "created_by",
            "created_at",
            "settled_at",
        ]
        read_only_fields = fields


class SettleConsignmentSerializer(serializers.Serializer):
    settlement_no = serializers.CharField(max_length=100, required=False, allow_blank=True)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    raise_bill = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["period_end"] < attrs["period_start"]:
            raise serializers.ValidationError({"period_end": "The period ends before it starts."})
        return attrs


# --- Put-away & wave picking -----------------------------------------------


class PutawayRuleSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default=None)
    target_zone_name = serializers.CharField(
        source="target_zone.name", read_only=True, default=None
    )
    target_bin_code = serializers.CharField(
        source="target_bin.bin_code", read_only=True, default=None
    )
    match_product_name = serializers.SerializerMethodField()

    class Meta:
        model = PutawayRule
        fields = [
            "id",
            "organization",
            "warehouse",
            "warehouse_name",
            "name",
            "strategy",
            "priority",
            "match_product",
            "match_product_name",
            "match_zone_type",
            "match_controlled_only",
            "match_cold_chain_only",
            "match_abc_class",
            "target_zone",
            "target_zone_name",
            "target_bin",
            "target_bin_code",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_match_product_name(self, obj: PutawayRule) -> str | None:
        product = obj.match_product
        if product is None:
            return None
        return f"{product.generic_name} {product.strength}".strip()

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        strategy = attrs.get("strategy") or getattr(self.instance, "strategy", None)
        target_bin = attrs.get("target_bin", getattr(self.instance, "target_bin", None))
        if strategy == PutawayRule.Strategy.FIXED_BIN and target_bin is None:
            raise serializers.ValidationError(
                {"target_bin": "A fixed-bin rule has to name the bin it always uses."}
            )
        return attrs


class PickTaskSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    zone_name = serializers.CharField(source="zone.name", read_only=True, default=None)
    bin_code = serializers.CharField(source="bin_location.bin_code", read_only=True, default=None)
    picker_username = serializers.CharField(source="picker.username", read_only=True, default=None)

    class Meta:
        model = PickTask
        fields = [
            "id",
            "wave",
            "sequence",
            "product",
            "product_name",
            "batch",
            "batch_number",
            "expiry_date",
            "zone",
            "zone_name",
            "bin_location",
            "bin_code",
            "quantity_requested",
            "quantity_picked",
            "status",
            "picker",
            "picker_username",
            "reference_type",
            "reference_id",
            "short_reason",
            "picked_at",
        ]
        read_only_fields = fields

    def get_product_name(self, obj: PickTask) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class PickWaveSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default=None)
    zone_name = serializers.CharField(source="zone.name", read_only=True, default=None)
    assigned_to_username = serializers.CharField(
        source="assigned_to.username", read_only=True, default=None
    )
    tasks = PickTaskSerializer(many=True, read_only=True)
    task_summary = serializers.SerializerMethodField()

    class Meta:
        model = PickWave
        fields = [
            "id",
            "organization",
            "warehouse",
            "warehouse_name",
            "wave_no",
            "strategy",
            "status",
            "planned_for",
            "zone",
            "zone_name",
            "assigned_to",
            "assigned_to_username",
            "created_by",
            "notes",
            "released_at",
            "completed_at",
            "created_at",
            "tasks",
            "task_summary",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_by",
            "released_at",
            "completed_at",
            "created_at",
        ]

    def get_task_summary(self, obj: PickWave) -> dict[str, int]:
        tasks = list(obj.tasks.all())
        return {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.status == PickTask.Status.PENDING),
            "assigned": sum(1 for t in tasks if t.status == PickTask.Status.ASSIGNED),
            "picked": sum(1 for t in tasks if t.status == PickTask.Status.PICKED),
            "short": sum(1 for t in tasks if t.status == PickTask.Status.SHORT),
            "units_requested": sum(t.quantity_requested for t in tasks),
            "units_picked": sum(t.quantity_picked for t in tasks),
        }


class BuildTasksSerializer(serializers.Serializer):
    """Demand lines to turn into FEFO pick tasks."""

    class _Demand(serializers.Serializer):
        product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
        quantity = serializers.IntegerField(min_value=1)
        reference_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
        reference_id = serializers.CharField(max_length=64, required=False, allow_blank=True)

    demands = _Demand(many=True, allow_empty=False)


class ConfirmPickSerializer(serializers.Serializer):
    quantity_picked = serializers.IntegerField(min_value=0)
    short_reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class PutawaySuggestSerializer(serializers.Serializer):
    batch = serializers.PrimaryKeyRelatedField(queryset=InventoryBatch.objects.all())


class ApplyPutawaySerializer(serializers.Serializer):
    bin_location = serializers.PrimaryKeyRelatedField(queryset=BinLocation.objects.all())


class RecordCalibrationSerializer(serializers.Serializer):
    certificate_no = serializers.CharField(max_length=100)
    calibrated_on = serializers.DateField()
    next_due_on = serializers.DateField(required=False, allow_null=True)
    calibrated_by = serializers.CharField(max_length=150, required=False, allow_blank=True)
    deviation_celsius = serializers.DecimalField(
        max_digits=5, decimal_places=3, required=False, allow_null=True
    )
    accuracy_celsius = serializers.DecimalField(
        max_digits=4, decimal_places=2, required=False, allow_null=True
    )
    result = serializers.ChoiceField(
        choices=SensorCalibration.Result.choices,
        required=False,
        default=SensorCalibration.Result.PASS,
    )
    reference_standard = serializers.CharField(max_length=150, required=False, allow_blank=True)
    certificate_url = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class OpenInvestigationSerializer(serializers.Serializer):
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all())
    reference_no = serializers.CharField(max_length=100, required=False, allow_blank=True)
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(required=False, allow_null=True)
    sensor = serializers.PrimaryKeyRelatedField(
        queryset=TemperatureSensor.objects.all(), required=False, allow_null=True
    )
    zone = serializers.PrimaryKeyRelatedField(
        queryset=StorageZone.objects.all(), required=False, allow_null=True
    )
    auto_quarantine = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs.get("sensor") and not attrs.get("zone"):
            raise serializers.ValidationError(
                "An investigation needs a sensor or a zone — otherwise there is no "
                "reading set and no stock to assess."
            )
        return attrs


class CloseInvestigationSerializer(serializers.Serializer):
    disposition = serializers.ChoiceField(
        choices=[
            c
            for c in ExcursionInvestigation.Disposition.choices
            if c[0] != ExcursionInvestigation.Disposition.PENDING
        ]
    )
    rationale = serializers.CharField(required=False, allow_blank=True)
    root_cause = serializers.CharField(required=False, allow_blank=True)
    corrective_action = serializers.CharField(required=False, allow_blank=True)
    impact_assessment = serializers.CharField(required=False, allow_blank=True)
