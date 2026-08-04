"""Serializers for the catalog app."""

from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import (
    ActiveIngredient,
    Manufacturer,
    Product,
    ProductBarcode,
    ProductIngredient,
    Supplier,
)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "tin",
            "email",
            "phone",
            "lead_time_days",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ActiveIngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActiveIngredient
        fields = ["id", "name", "atc_code"]
        read_only_fields = ["id"]


class ProductIngredientSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source="ingredient.name", read_only=True)

    class Meta:
        model = ProductIngredient
        fields = ["id", "product", "ingredient", "ingredient_name", "amount"]
        read_only_fields = ["id", "ingredient_name"]


class ProductBarcodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductBarcode
        fields = ["id", "product", "barcode", "packaging_level", "units_per_level"]
        read_only_fields = ["id"]


class ManufacturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manufacturer
        fields = ["id", "name", "country", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class ProductSerializer(serializers.ModelSerializer):
    manufacturer_name = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "generic_name",
            "brand_name",
            "manufacturer",
            "manufacturer_name",
            "dosage_form",
            "strength",
            "pack_size",
            "unit_of_measure",
            "units_per_pack",
            "route_of_administration",
            "atc_code",
            "gtin",
            "fda_registration_number",
            "tax_class",
            "requires_prescription",
            "is_controlled_substance",
            "controlled_schedule",
            "storage_condition",
            "reorder_level",
            "reorder_quantity",
            "rra_item_code",
            "image_url",
            "leaflet_url",
            "min_temp_c",
            "max_temp_c",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "manufacturer_name", "created_at", "updated_at"]

    def get_manufacturer_name(self, obj: Product) -> str | None:
        return obj.manufacturer.name if obj.manufacturer else None
