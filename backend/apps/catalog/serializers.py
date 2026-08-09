"""Serializers for the catalog app."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.catalog.models import (
    ActiveIngredient,
    FormularyItem,
    Manufacturer,
    PriceList,
    Product,
    ProductBarcode,
    ProductContraindication,
    ProductIngredient,
    ProductInteraction,
    ProductPrice,
    ProductSubstitute,
    ProductUnit,
    ProductUomConversion,
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
            "ddd",
            "is_essential",
            "rxnorm_id",
            "lifecycle_status",
            "divisibility",
            "split_note",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "manufacturer_name", "created_at", "updated_at"]

    def get_manufacturer_name(self, obj: Product) -> str | None:
        return obj.manufacturer.name if obj.manufacturer else None


class ProductInteractionSerializer(serializers.ModelSerializer):
    ingredient_a_name = serializers.CharField(source="ingredient_a.name", read_only=True)
    ingredient_b_name = serializers.CharField(source="ingredient_b.name", read_only=True)

    class Meta:
        model = ProductInteraction
        fields = [
            "id",
            "ingredient_a",
            "ingredient_a_name",
            "ingredient_b",
            "ingredient_b_name",
            "severity",
            "effect",
            "management",
        ]
        read_only_fields = ["id", "ingredient_a_name", "ingredient_b_name"]


class ProductContraindicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductContraindication
        fields = [
            "id",
            "product",
            "condition",
            "icd10_code",
            "snomed_code",
            "severity",
            "message",
        ]
        read_only_fields = ["id"]


class PriceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceList
        fields = [
            "id",
            "name",
            "list_type",
            "effective_from",
            "effective_to",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ProductPriceSerializer(serializers.ModelSerializer):
    price_list_name = serializers.CharField(source="price_list.name", read_only=True)
    product_generic_name = serializers.CharField(source="product.generic_name", read_only=True)

    class Meta:
        model = ProductPrice
        fields = [
            "id",
            "price_list",
            "price_list_name",
            "product",
            "product_generic_name",
            "unit_price",
            "min_quantity",
        ]
        read_only_fields = ["id", "price_list_name", "product_generic_name"]


class FormularyItemSerializer(serializers.ModelSerializer):
    product_generic_name = serializers.CharField(source="product.generic_name", read_only=True)

    class Meta:
        model = FormularyItem
        fields = [
            "id",
            "scheme_name",
            "product",
            "product_generic_name",
            "is_covered",
            "max_reimbursable_price",
            "copay_percentage",
            "requires_prior_auth",
            "notes",
        ]
        read_only_fields = ["id", "product_generic_name"]


class ProductUnitSerializer(serializers.ModelSerializer):
    """One level of a product's packaging chain."""

    code_display = serializers.CharField(source="get_code_display", read_only=True)

    class Meta:
        model = ProductUnit
        fields = [
            "id",
            "product",
            "code",
            "code_display",
            "name",
            "factor_to_base",
            "level",
            "is_base",
            "is_purchase_default",
            "is_sale_default",
            "barcode",
            "price",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Catch what the database constraints would reject, with a readable reason.

        The constraints are the real guarantee; this exists so the screen says
        "that product already has a base unit" instead of surfacing an
        IntegrityError.
        """
        product = attrs.get("product") or getattr(self.instance, "product", None)
        if product is None:
            return attrs

        existing = ProductUnit.objects.filter(product=product)
        if isinstance(self.instance, ProductUnit):
            existing = existing.exclude(pk=self.instance.pk)

        is_base = attrs.get("is_base", getattr(self.instance, "is_base", False))
        factor = attrs.get("factor_to_base", getattr(self.instance, "factor_to_base", 1))

        if is_base:
            if Decimal(str(factor)) != 1:
                raise serializers.ValidationError(
                    {"factor_to_base": "The base unit measures one of itself."}
                )
            if existing.filter(is_base=True).exists():
                raise serializers.ValidationError(
                    {"is_base": f"{product} already has a base unit. Change that one instead."}
                )
        elif Decimal(str(factor)) <= 1 and not existing.filter(is_base=True).exists():
            raise serializers.ValidationError(
                {"factor_to_base": "Record the base unit first, then the levels above it."}
            )

        for flag, label in (("is_purchase_default", "purchase"), ("is_sale_default", "sale")):
            if (
                attrs.get(flag, getattr(self.instance, flag, False))
                and existing.filter(**{flag: True}).exists()
            ):
                raise serializers.ValidationError(
                    {flag: f"Only one {label} unit per product — clear the other one first."}
                )
        return attrs


class ProductUomConversionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductUomConversion
        fields = [
            "id",
            "product",
            "unit_name",
            "conversion_factor",
            "price_per_unit",
            "is_default_dispensing",
        ]
        read_only_fields = ["id"]


class ProductSubstituteSerializer(serializers.ModelSerializer):
    substitute_generic_name = serializers.CharField(
        source="substitute_product.generic_name", read_only=True
    )
    substitute_strength = serializers.CharField(
        source="substitute_product.strength", read_only=True
    )

    class Meta:
        model = ProductSubstitute
        fields = [
            "id",
            "product",
            "substitute_product",
            "substitute_generic_name",
            "substitute_strength",
            "substitute_type",
            "notes",
        ]
        read_only_fields = ["id", "substitute_generic_name", "substitute_strength"]
