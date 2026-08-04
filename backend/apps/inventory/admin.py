from __future__ import annotations

from django.contrib import admin

from apps.inventory.models import PharmacyProduct


@admin.register(PharmacyProduct)
class PharmacyProductAdmin(admin.ModelAdmin):
    list_display = ("organization", "product", "retail_price", "min_stock_level", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("product__generic_name", "product__brand_name")
