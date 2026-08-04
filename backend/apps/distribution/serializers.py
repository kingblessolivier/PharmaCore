from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.distribution.models import (
    GoodsReceivedNote,
    GRNLine,
    InTransitStock,
    OrderItem,
    OrderPayment,
    Shipment,
    StockOrder,
)


class OrderPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderPayment
        fields = ["id", "amount", "method", "reference", "paid_at"]
        read_only_fields = ["id", "paid_at"]


class InTransitStockSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    source_name = serializers.CharField(source="source_org.name", read_only=True)
    destination_name = serializers.CharField(source="destination_org.name", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = InTransitStock
        fields = [
            "id",
            "order",
            "order_number",
            "source_org",
            "source_name",
            "destination_org",
            "destination_name",
            "product",
            "product_name",
            "batch_number",
            "expiry_date",
            "quantity",
            "dispatched_at",
        ]
        read_only_fields = fields

    def get_product_name(self, obj: InTransitStock) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ["id", "driver_name", "vehicle_registration", "dispatched_at"]
        read_only_fields = fields


class GRNLineSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    has_discrepancy = serializers.BooleanField(read_only=True)

    class Meta:
        model = GRNLine
        fields = [
            "id",
            "product",
            "product_name",
            "batch_number",
            "expiry_date",
            "quantity_expected",
            "quantity_received",
            "quantity_damaged",
            "has_discrepancy",
        ]
        read_only_fields = fields

    def get_product_name(self, obj: GRNLine) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class GRNSerializer(serializers.ModelSerializer):
    lines = GRNLineSerializer(many=True, read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = GoodsReceivedNote
        fields = [
            "id",
            "grn_number",
            "order",
            "order_number",
            "status",
            "has_discrepancy",
            "received_at",
            "lines",
        ]
        read_only_fields = fields


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    line_total = serializers.FloatField(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "quantity_ordered",
            "quantity_approved",
            "quantity_shipped",
            "quantity_received",
            "price_per_unit",
            "line_total",
        ]
        read_only_fields = [
            "id",
            "product_name",
            "quantity_approved",
            "quantity_shipped",
            "quantity_received",
            # Price is NOT set by the buyer — it is pulled from the depot's wholesale price.
            "price_per_unit",
            "line_total",
        ]

    def get_product_name(self, obj: OrderItem) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class StockOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    depot_name = serializers.CharField(source="depot.name", read_only=True)
    retail_name = serializers.CharField(source="retail.name", read_only=True)
    total_amount = serializers.FloatField(read_only=True)
    amount_due = serializers.FloatField(read_only=True)
    shipments = ShipmentSerializer(many=True, read_only=True)
    order_payments = OrderPaymentSerializer(many=True, read_only=True)
    in_transit = InTransitStockSerializer(many=True, read_only=True)

    class Meta:
        model = StockOrder
        fields = [
            "id",
            "order_number",
            "depot",
            "depot_name",
            "retail",
            "retail_name",
            "status",
            "expected_delivery",
            "notes",
            "total_amount",
            "payment_status",
            "amount_paid",
            "amount_due",
            "payment_due_date",
            "order_payments",
            "in_transit",
            "items",
            "shipments",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "status",
            "total_amount",
            "payment_status",
            "amount_paid",
            "amount_due",
            "order_payments",
            "created_at",
        ]

    def create(self, validated_data: dict[str, Any]) -> StockOrder:
        from apps.inventory.models import PharmacyProduct

        items = validated_data.pop("items", [])
        order = StockOrder.objects.create(**validated_data)
        for item in items:
            product = item["product"]
            listing = PharmacyProduct.objects.filter(
                organization=order.depot, product=product, is_active=True
            ).first()
            if listing is None or listing.wholesale_price is None:
                raise serializers.ValidationError(
                    f"'{product}' is not offered by {order.depot.name} (no wholesale price set)."
                )
            # Authoritative: the depot's wholesale price, never the buyer's input.
            OrderItem.objects.create(order=order, price_per_unit=listing.wholesale_price, **item)
        return order
