from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.catalog.views import (
    ActiveIngredientViewSet,
    ManufacturerViewSet,
    ProductBarcodeViewSet,
    ProductIngredientViewSet,
    ProductViewSet,
    SupplierViewSet,
)

router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")
router.register("manufacturers", ManufacturerViewSet, basename="manufacturer")
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("ingredients", ActiveIngredientViewSet, basename="ingredient")
router.register("product-ingredients", ProductIngredientViewSet, basename="product-ingredient")
router.register("product-barcodes", ProductBarcodeViewSet, basename="product-barcode")

urlpatterns = router.urls
