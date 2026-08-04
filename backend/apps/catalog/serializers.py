"""Serializers for the catalog app."""

from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import Manufacturer, Product


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
            "atc_code",
            "gtin",
            "tax_class",
            "requires_prescription",
            "is_controlled_substance",
            "storage_condition",
            "reorder_level",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "manufacturer_name", "created_at", "updated_at"]

    def get_manufacturer_name(self, obj: Product) -> str | None:
        return obj.manufacturer.name if obj.manufacturer else None
