from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.catalog.views import (
    ActiveIngredientViewSet,
    FormularyItemViewSet,
    ManufacturerViewSet,
    PriceListViewSet,
    ProductBarcodeViewSet,
    ProductContraindicationViewSet,
    ProductIngredientViewSet,
    ProductInteractionViewSet,
    ProductPriceViewSet,
    ProductSubstituteViewSet,
    ProductUomConversionViewSet,
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
router.register("product-interactions", ProductInteractionViewSet, basename="product-interaction")
router.register("product-contraindications", ProductContraindicationViewSet, basename="product-contraindication")
router.register("price-lists", PriceListViewSet, basename="price-list")
router.register("product-prices", ProductPriceViewSet, basename="product-price")
router.register("formulary-items", FormularyItemViewSet, basename="formulary-item")
router.register("product-uom-conversions", ProductUomConversionViewSet, basename="product-uom-conversion")
router.register("product-substitutes", ProductSubstituteViewSet, basename="product-substitute")

urlpatterns = router.urls

