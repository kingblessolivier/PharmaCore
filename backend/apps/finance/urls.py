from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.finance.views import (
    AccountViewSet,
    CreditProfileViewSet,
    JournalEntryViewSet,
    SupplierBillViewSet,
)

router = DefaultRouter()
router.register("accounts", AccountViewSet, basename="finance-account")
router.register("journal-entries", JournalEntryViewSet, basename="journal-entry")
router.register("credit-profiles", CreditProfileViewSet, basename="credit-profile")
router.register("supplier-bills", SupplierBillViewSet, basename="supplier-bill")

urlpatterns = router.urls
