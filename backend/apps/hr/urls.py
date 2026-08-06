from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.hr.views import EmployeeViewSet, PayrollRunViewSet, StatutoryRateViewSet

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")
router.register("statutory-rates", StatutoryRateViewSet, basename="statutory-rate")
router.register("payroll-runs", PayrollRunViewSet, basename="payroll-run")

urlpatterns = router.urls
