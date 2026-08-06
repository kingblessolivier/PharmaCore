from __future__ import annotations

from django.contrib import admin

from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    ImportConsignment,
    LandedCostComponent,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    RequestForQuotation,
    RequisitionLine,
    RFQLine,
    SupplierEvaluation,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierLicence,
    SupplierNote,
    SupplierPriceAgreement,
    SupplierProfile,
    SupplierQuote,
    SupplierQuoteLine,
)


class _LineInline(admin.TabularInline):
    extra = 0


class PurchaseOrderLineInline(_LineInline):
    model = PurchaseOrderLine


class RequisitionLineInline(_LineInline):
    model = RequisitionLine


class RFQLineInline(_LineInline):
    model = RFQLine


class SupplierQuoteLineInline(_LineInline):
    model = SupplierQuoteLine


class GoodsReceiptLineInline(_LineInline):
    model = GoodsReceiptLine


class SupplierInvoiceLineInline(_LineInline):
    model = SupplierInvoiceLine


class LandedCostComponentInline(_LineInline):
    model = LandedCostComponent


@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    list_display = ("supplier", "standing", "kind", "currency", "payment_terms_days")
    list_filter = ("standing", "kind", "is_import_source")
    search_fields = ("supplier__name", "trading_name")


@admin.register(SupplierLicence)
class SupplierLicenceAdmin(admin.ModelAdmin):
    list_display = ("supplier", "kind", "licence_number", "expires_on", "is_verified")
    list_filter = ("kind", "is_verified", "is_required")
    search_fields = ("supplier__name", "licence_number")


@admin.register(SupplierPriceAgreement)
class SupplierPriceAgreementAdmin(admin.ModelAdmin):
    list_display = ("supplier", "product", "unit_price", "min_quantity", "valid_from", "is_active")
    list_filter = ("is_active", "currency")
    search_fields = ("supplier__name", "product__generic_name", "contract_reference")


@admin.register(SupplierEvaluation)
class SupplierEvaluationAdmin(admin.ModelAdmin):
    list_display = ("supplier", "organization", "period_end", "overall_score")
    list_filter = ("organization",)


@admin.register(PurchaseRequisition)
class PurchaseRequisitionAdmin(admin.ModelAdmin):
    list_display = ("requisition_number", "organization", "status", "priority", "needed_by")
    list_filter = ("status", "priority", "organization")
    search_fields = ("requisition_number",)
    inlines = [RequisitionLineInline]


@admin.register(RequestForQuotation)
class RequestForQuotationAdmin(admin.ModelAdmin):
    list_display = ("rfq_number", "title", "organization", "status", "response_due")
    list_filter = ("status", "organization")
    search_fields = ("rfq_number", "title")
    inlines = [RFQLineInline]


@admin.register(SupplierQuote)
class SupplierQuoteAdmin(admin.ModelAdmin):
    list_display = ("rfq", "supplier", "status", "currency", "lead_time_days")
    list_filter = ("status", "currency")
    inlines = [SupplierQuoteLineInline]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("po_number", "organization", "supplier", "status", "currency", "order_date")
    list_filter = ("status", "is_import", "currency", "organization")
    search_fields = ("po_number", "supplier__name", "supplier_reference")
    inlines = [PurchaseOrderLineInline]


@admin.register(ImportConsignment)
class ImportConsignmentAdmin(admin.ModelAdmin):
    list_display = ("reference", "organization", "supplier", "status", "mode", "eta")
    list_filter = ("status", "mode", "organization")
    search_fields = ("reference", "bill_of_lading_number", "customs_declaration_number")
    inlines = [LandedCostComponentInline]


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ("grn_number", "order", "organization", "status", "received_on")
    list_filter = ("status", "requires_qc", "has_discrepancy", "organization")
    search_fields = ("grn_number", "supplier_delivery_note")
    inlines = [GoodsReceiptLineInline]


@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number", "supplier", "organization", "status", "match_result", "invoice_date"
    )
    list_filter = ("status", "match_result", "organization")
    search_fields = ("invoice_number", "internal_number", "supplier__name")
    inlines = [SupplierInvoiceLineInline]


@admin.register(SupplierNote)
class SupplierNoteAdmin(admin.ModelAdmin):
    list_display = ("note_number", "supplier", "kind", "reason", "status", "amount", "note_date")
    list_filter = ("kind", "status", "reason")
    search_fields = ("note_number", "supplier__name")
