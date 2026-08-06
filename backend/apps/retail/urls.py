from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.retail.views import (
    ClinicalServiceRecordViewSet,
    ClinicalServiceViewSet,
    ControlledSubstanceRegisterViewSet,
    DispensingViewSet,
    DrawerSessionViewSet,
    POSPromotionViewSet,
    PrescriptionViewSet,
    SaleViewSet,
)

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sale")
router.register("dispensing", DispensingViewSet, basename="dispensing")
router.register("drawer-sessions", DrawerSessionViewSet, basename="drawer-session")
router.register("prescriptions", PrescriptionViewSet, basename="prescription")
router.register("controlled-drugs", ControlledSubstanceRegisterViewSet, basename="controlled-drug")
router.register("promotions", POSPromotionViewSet, basename="promotion")
router.register("clinical-services", ClinicalServiceViewSet, basename="clinical-service")
router.register("clinical-encounters", ClinicalServiceRecordViewSet, basename="clinical-encounter")

urlpatterns = [*router.urls]
