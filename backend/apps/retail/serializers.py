from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.retail.models import (
    TAX_RATES,
    ClinicalService,
    ClinicalServiceRecord,
    ControlledSubstanceRegister,
    Dispensing,
    DrawerSession,
    Payment,
    POSPromotion,
    Prescription,
    PrescriptionItem,
    Sale,
    SaleItem,
)


class PrescriptionItemSerializer(serializers.ModelSerializer):
    """What was prescribed. Without this the script records who, not what."""

    product_name = serializers.SerializerMethodField()
    outstanding = serializers.IntegerField(read_only=True)
    is_fully_dispensed = serializers.BooleanField(read_only=True)

    class Meta:
        model = PrescriptionItem
        fields = [
            "id",
            "product",
            "product_name",
            "quantity_prescribed",
            "quantity_dispensed",
            "dosage_instructions",
            "substitution_allowed",
            "outstanding",
            "is_fully_dispensed",
        ]
        read_only_fields = ["id", "outstanding", "is_fully_dispensed"]

    def get_product_name(self, obj: PrescriptionItem) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class PrescriptionSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    items = PrescriptionItemSerializer(many=True, required=False)
    remaining_refills = serializers.IntegerField(read_only=True)

    class Meta:
        model = Prescription
        fields = [
            "items",
            "id",
            "prescription_number",
            "organization",
            "organization_name",
            "patient_name",
            "patient_id_number",
            "patient_phone",
            "prescriber_name",
            "prescriber_license",
            "issue_date",
            "expiry_date",
            "refills_allowed",
            "refills_used",
            "remaining_refills",
            "status",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "remaining_refills"]


class ControlledSubstanceRegisterSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    product_name = serializers.CharField(source="product.generic_name", read_only=True)
    logged_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ControlledSubstanceRegister
        fields = [
            "id",
            "organization",
            "organization_name",
            "product",
            "product_name",
            "batch_number",
            "movement_type",
            "quantity",
            "running_balance",
            "patient_name",
            "prescriber_name",
            "witness_name",
            "rx_reference",
            "logged_by",
            "logged_by_name",
            "logged_at",
        ]
        read_only_fields = ["id", "logged_at"]

    def get_logged_by_name(self, obj: ControlledSubstanceRegister) -> str | None:
        if not obj.logged_by:
            return None
        return obj.logged_by.get_full_name() or obj.logged_by.username


class POSPromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = POSPromotion
        fields = [
            "id",
            "code",
            "name",
            "promo_type",
            "discount_value",
            "min_spend",
            "valid_from",
            "valid_until",
            "max_redemptions",
            "times_redeemed",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ClinicalServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalService
        fields = ["id", "service_code", "name", "category", "fee_amount", "is_active"]
        read_only_fields = ["id"]


class ClinicalServiceRecordSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ClinicalServiceRecord
        fields = [
            "is_paid",
            "sale",
            "id",
            "organization",
            "organization_name",
            "service",
            "service_name",
            "patient_name",
            "patient_phone",
            "performed_by",
            "performed_by_name",
            "clinical_notes",
            "fee_charged",
            "performed_at",
        ]
        read_only_fields = ["id", "performed_at"]

    def get_performed_by_name(self, obj: ClinicalServiceRecord) -> str | None:
        if not obj.performed_by:
            return None
        return obj.performed_by.get_full_name() or obj.performed_by.username


class DrawerSessionSerializer(serializers.ModelSerializer):
    cashier_name = serializers.SerializerMethodField()

    class Meta:
        model = DrawerSession
        fields = [
            "id",
            "organization",
            "cashier",
            "cashier_name",
            "status",
            "opening_float",
            "counted_cash",
            "expected_cash",
            "over_short",
            "notes",
            "opened_at",
            "closed_at",
        ]
        read_only_fields = [
            "id",
            "cashier",
            "cashier_name",
            "status",
            "counted_cash",
            "expected_cash",
            "over_short",
            "opened_at",
            "closed_at",
        ]

    def get_cashier_name(self, obj: DrawerSession) -> str | None:
        u = obj.cashier
        if not u:
            return None
        return u.get_full_name() or u.username


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
