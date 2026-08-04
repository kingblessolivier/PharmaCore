from __future__ import annotations

from django.contrib import admin

from apps.retail.models import Payment, Sale, SaleBatchAllocation, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("sale_number", "organization", "status", "cashier", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("sale_number",)
    inlines = [SaleItemInline, PaymentInline]


admin.site.register(SaleBatchAllocation)
