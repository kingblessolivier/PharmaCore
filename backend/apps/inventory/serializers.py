from __future__ import annotations

from datetime import date

from rest_framework import serializers

from apps.catalog.models import Product, Supplier
from apps.iam.models import Organization
from apps.inventory.models import (
    BatchRecall,
    BinLocation,
    InventoryBatch,
    PharmacyProduct,
    QualityCheck,
    StockCount,
    StockCountItem,
    StockDisposal,
    StockMovement,
    StorageZone,
    TemperatureLog,
    TemperatureSensor,
)


class StorageZoneSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    bins_count = serializers.SerializerMethodField()

    class Meta:
        model = StorageZone
        fields = [
            "id",
            "organization",
            "organization_name",
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

    class Meta:
        model = TemperatureSensor
        fields = [
            "id",
            "organization",
            "zone",
            "zone_name",
            "device_id",
            "name",
            "calibration_due_date",
            "is_active",
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
    approver_username = serializers.CharField(source="approver_user.username", read_only=True, default=None)
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
    primary_witness_username = serializers.CharField(source="primary_witness.username", read_only=True)

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
            expiry_date__gte=timezone.now().date(),
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
            "wholesale_cost",
            "storage_location",
            "bin_location",
            "is_consignment",
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
        return (obj.expiry_date - date.today()).days


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
