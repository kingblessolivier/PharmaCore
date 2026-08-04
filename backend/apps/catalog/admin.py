from __future__ import annotations

from django.contrib import admin

from apps.catalog.models import Manufacturer, Product


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "is_active")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "generic_name",
        "brand_name",
        "strength",
        "dosage_form",
        "tax_class",
        "is_active",
    )
    list_filter = ("dosage_form", "tax_class", "requires_prescription", "is_active")
    search_fields = ("generic_name", "brand_name", "atc_code", "gtin")
