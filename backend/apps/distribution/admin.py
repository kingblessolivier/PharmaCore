from __future__ import annotations

from django.contrib import admin

from apps.distribution.models import (
    GoodsReceivedNote,
    GRNLine,
    OrderItem,
    Reservation,
    Shipment,
    StockOrder,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(StockOrder)
class StockOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "retail", "depot", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("order_number",)
    inlines = [OrderItemInline]


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("order", "driver_name", "vehicle_registration", "dispatched_at")
    search_fields = ("order__order_number", "driver_name", "vehicle_registration")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("order", "batch", "quantity", "created_at")


class GRNLineInline(admin.TabularInline):
    model = GRNLine
    extra = 0


@admin.register(GoodsReceivedNote)
class GRNAdmin(admin.ModelAdmin):
    list_display = ("grn_number", "order", "retail", "status", "has_discrepancy", "received_at")
    list_filter = ("status", "has_discrepancy")
    search_fields = ("grn_number", "order__order_number")
    inlines = [GRNLineInline]
