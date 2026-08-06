from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.procurement.views import (
    GoodsReceiptViewSet,
    ImportConsignmentViewSet,
    LandedCostComponentViewSet,
    ProcurementOverviewView,
    PurchaseOrderViewSet,
    PurchaseRequisitionViewSet,
    RequestForQuotationViewSet,
    SupplierEvaluationViewSet,
    SupplierInvoiceViewSet,
    SupplierLicenceViewSet,
    SupplierNoteViewSet,
    SupplierPriceAgreementViewSet,
    SupplierProfileViewSet,
    SupplierQuoteViewSet,
    SupplierStatementView,
)

router = DefaultRouter()
router.register("supplier-profiles", SupplierProfileViewSet, basename="supplier-profile")
router.register("supplier-licences", SupplierLicenceViewSet, basename="supplier-licence")
router.register("price-agreements", SupplierPriceAgreementViewSet, basename="price-agreement")
router.register("evaluations", SupplierEvaluationViewSet, basename="supplier-evaluation")
router.register("requisitions", PurchaseRequisitionViewSet, basename="requisition")
router.register("rfqs", RequestForQuotationViewSet, basename="rfq")
router.register("quotes", SupplierQuoteViewSet, basename="supplier-quote")
router.register("orders", PurchaseOrderViewSet, basename="purchase-order")
router.register("consignments", ImportConsignmentViewSet, basename="import-consignment")
router.register("landed-costs", LandedCostComponentViewSet, basename="landed-cost")
router.register("receipts", GoodsReceiptViewSet, basename="goods-receipt")
router.register("invoices", SupplierInvoiceViewSet, basename="supplier-invoice")
router.register("supplier-notes", SupplierNoteViewSet, basename="supplier-note")

urlpatterns = [
    path("overview/", ProcurementOverviewView.as_view(), name="procurement-overview"),
    path("statement/", SupplierStatementView.as_view(), name="supplier-statement"),
    *router.urls,
]
