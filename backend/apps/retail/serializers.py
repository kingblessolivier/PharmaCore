from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.retail.models import TAX_RATES, Dispensing, Payment, Sale, SaleItem


class DispensingSerializer(serializers.ModelSerializer):
    sale_number = serializers.CharField(source="sale.sale_number", read_only=True)
    organization = serializers.IntegerField(source="sale.organization_id", read_only=True)
    dispensed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Dispensing
        fields = [
            "id",
            "sale",
            "sale_number",
            "organization",
            "dispensed_by_name",
            "patient_name",
            "patient_id_number",
            "prescriber_name",
            "prescriber_license",
            "prescription_reference",
            "created_at",
        ]
        read_only_fields = fields

    def get_dispensed_by_name(self, obj: Dispensing) -> str | None:
        u = obj.dispensed_by
        if not u:
            return None
        return u.get_full_name() or u.username


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    line_tax = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "returned_quantity",
            "unit_price",
            "tax_rate",
            "line_total",
            "line_tax",
        ]
        # Price and tax are snapshotted server-side from the pharmacy's listing —
        # never taken from the client.
        read_only_fields = [
            "id",
            "product_name",
            "returned_quantity",
            "unit_price",
            "tax_rate",
            "line_total",
            "line_tax",
        ]

    def get_product_name(self, obj: SaleItem) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "method", "amount", "created_at"]
        read_only_fields = ["id", "created_at"]


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    payments = PaymentSerializer(many=True, read_only=True)
    org_name = serializers.CharField(source="organization.name", read_only=True)
    cashier_name = serializers.SerializerMethodField()
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    tax_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "sale_number",
            "organization",
            "org_name",
            "cashier",
            "cashier_name",
            "status",
            "subtotal",
            "tax_total",
            "total",
            "amount_tendered",
            "change_due",
            "void_reason",
            "items",
            "payments",
            "completed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "sale_number",
            "cashier",
            "status",
            "amount_tendered",
            "change_due",
            "void_reason",
            "completed_at",
            "created_at",
        ]

    def get_cashier_name(self, obj: Sale) -> str | None:
        if not obj.cashier:
            return None
        return obj.cashier.get_full_name() or obj.cashier.username

    def create(self, validated_data: dict[str, Any]) -> Sale:
        from apps.inventory.models import PharmacyProduct

        items = validated_data.pop("items", [])
        sale = Sale.objects.create(**validated_data)
        for item in items:
            product = item["product"]
            listing = PharmacyProduct.objects.filter(
                organization=sale.organization, product=product, is_active=True
            ).first()
            if listing is None or listing.retail_price is None:
                raise serializers.ValidationError(
                    f"'{product}' has no retail price at {sale.organization.name}."
                )
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=item["quantity"],
                unit_price=listing.retail_price,
                tax_rate=TAX_RATES.get(product.tax_class, Decimal("0")),
            )
        return sale
