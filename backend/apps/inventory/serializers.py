from __future__ import annotations

from rest_framework import serializers

from apps.inventory.models import PharmacyProduct


class PharmacyProductSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    product_form = serializers.CharField(source="product.dosage_form", read_only=True)
    requires_prescription = serializers.BooleanField(
        source="product.requires_prescription", read_only=True
    )

    class Meta:
        model = PharmacyProduct
        fields = [
            "id",
            "organization",
            "product",
            "product_name",
            "product_form",
            "requires_prescription",
            "retail_price",
            "min_stock_level",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "product_name",
            "product_form",
            "requires_prescription",
            "created_at",
        ]

    def get_product_name(self, obj: PharmacyProduct) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()
