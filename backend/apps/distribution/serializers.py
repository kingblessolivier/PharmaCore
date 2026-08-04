from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.distribution.models import (
    GoodsReceivedNote,
    GRNLine,
    OrderItem,
    Shipment,
    StockOrder,
)


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
            "line_total",
        ]

    def get_product_name(self, obj: OrderItem) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class StockOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    depot_name = serializers.CharField(source="depot.name", read_only=True)
    retail_name = serializers.CharField(source="retail.name", read_only=True)
    total_amount = serializers.FloatField(read_only=True)
    shipments = ShipmentSerializer(many=True, read_only=True)

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
            "items",
            "shipments",
            "created_at",
        ]
        read_only_fields = ["id", "order_number", "status", "total_amount", "created_at"]

    def create(self, validated_data: dict[str, Any]) -> StockOrder:
        items = validated_data.pop("items", [])
        order = StockOrder.objects.create(**validated_data)
        for item in items:
            OrderItem.objects.create(order=order, **item)
        return order
