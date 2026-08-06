from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.hr.views import (
    AttendanceLogViewSet,
    EmployeeViewSet,
    LeaveRequestViewSet,
    PayrollRunViewSet,
    ShiftRosterViewSet,
    StatutoryRateViewSet,
)

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")
router.register("statutory-rates", StatutoryRateViewSet, basename="statutory-rate")
router.register("payroll-runs", PayrollRunViewSet, basename="payroll-run")
router.register("attendance", AttendanceLogViewSet, basename="attendance")
router.register("roster", ShiftRosterViewSet, basename="roster")
router.register("leave", LeaveRequestViewSet, basename="leave")

urlpatterns = router.urls
