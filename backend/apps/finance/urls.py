from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.finance.views import (
    AccountingPeriodViewSet,
    AccountViewSet,
    BankAccountViewSet,
    BudgetViewSet,
    CashFlowForecastView,
    CreditProfileViewSet,
    FinanceReportsView,
    FixedAssetViewSet,
    JournalEntryViewSet,
    SupplierBillViewSet,
    TaxCodeViewSet,
    TaxPaymentViewSet,
    TaxRecordViewSet,
)

router = DefaultRouter()
router.register("accounts", AccountViewSet, basename="finance-account")
router.register("journal-entries", JournalEntryViewSet, basename="journal-entry")
router.register("credit-profiles", CreditProfileViewSet, basename="credit-profile")
router.register("supplier-bills", SupplierBillViewSet, basename="supplier-bill")
router.register("bank-accounts", BankAccountViewSet, basename="bank-account")
router.register("cash-flow-forecast", CashFlowForecastView, basename="cash-flow-forecast")
router.register("reports", FinanceReportsView, basename="finance-reports")
router.register("periods", AccountingPeriodViewSet, basename="accounting-period")
router.register("fixed-assets", FixedAssetViewSet, basename="fixed-asset")
router.register("tax-records", TaxRecordViewSet, basename="tax-record")
router.register("tax-codes", TaxCodeViewSet, basename="tax-code")
router.register("tax-payments", TaxPaymentViewSet, basename="tax-payment")
router.register("budgets", BudgetViewSet, basename="budget")

urlpatterns = router.urls
