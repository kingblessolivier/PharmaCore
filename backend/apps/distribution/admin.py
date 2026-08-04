from __future__ import annotations

from django.contrib import admin

from apps.distribution.models import OrderItem, StockOrder


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(StockOrder)
class StockOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "retail", "depot", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("order_number",)
    inlines = [OrderItemInline]
