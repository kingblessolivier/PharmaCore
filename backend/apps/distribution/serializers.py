from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.distribution.models import OrderItem, StockOrder


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
            "created_at",
        ]
        read_only_fields = ["id", "order_number", "status", "total_amount", "created_at"]

    def create(self, validated_data: dict[str, Any]) -> StockOrder:
        items = validated_data.pop("items", [])
        order = StockOrder.objects.create(**validated_data)
        for item in items:
            OrderItem.objects.create(order=order, **item)
        return order
