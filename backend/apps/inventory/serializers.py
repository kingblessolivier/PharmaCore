from __future__ import annotations

from datetime import date

from rest_framework import serializers

from apps.catalog.models import Product
from apps.iam.models import Organization
from apps.inventory.models import InventoryBatch, PharmacyProduct, StockMovement


class PharmacyProductSerializer(serializers.ModelSerializer):
    # The product is a global master, so a listing inherits every characteristic —
    # these read-only mirrors let the catalog/POS show the full product.
    product_name = serializers.SerializerMethodField()
    product_form = serializers.CharField(source="product.dosage_form", read_only=True)
    product_strength = serializers.CharField(source="product.strength", read_only=True)
    product_image = serializers.CharField(source="product.image_url", read_only=True)
    product_tax_class = serializers.CharField(source="product.tax_class", read_only=True)
    requires_prescription = serializers.BooleanField(
        source="product.requires_prescription", read_only=True
    )
    on_hand = serializers.SerializerMethodField()

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
            "on_hand",
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
            "on_hand",
            "created_at",
        ]

    def get_product_name(self, obj: PharmacyProduct) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()

    def get_on_hand(self, obj: PharmacyProduct) -> int:
        # Total units on hand across all this org's active batches of the product —
        # received stock accumulates here, never as a duplicate listing.
        from django.db.models import Sum

        total = InventoryBatch.objects.filter(
            organization=obj.organization,
            product=obj.product,
            status=InventoryBatch.Status.ACTIVE,
        ).aggregate(total=Sum("quantity_available"))["total"]
        return int(total or 0)


class InventoryBatchSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    days_to_expiry = serializers.SerializerMethodField()

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
            "status",
            "created_at",
        ]

    def get_product_name(self, obj: InventoryBatch) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()

    def get_days_to_expiry(self, obj: InventoryBatch) -> int:
        return (obj.expiry_date - date.today()).days


class IntakeSerializer(serializers.Serializer):
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
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
