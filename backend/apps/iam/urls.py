from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.iam.views import (
    AuditLogViewSet,
    CompanyViewSet,
    DepartmentViewSet,
    ImpersonateView,
    LicenseViewSet,
    LoginView,
    MeView,
    OrganizationViewSet,
    PermissionViewSet,
    RoleViewSet,
    StopImpersonateView,
    UserViewSet,
)

router = DefaultRouter()
router.register("companies", CompanyViewSet, basename="company")
router.register("organizations", OrganizationViewSet, basename="organization")
router.register("departments", DepartmentViewSet, basename="department")
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")
router.register("licenses", LicenseViewSet, basename="license")
router.register("audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me", MeView.as_view(), name="me"),
    path("auth/impersonate", ImpersonateView.as_view(), name="impersonate"),
    path("auth/impersonate/stop", StopImpersonateView.as_view(), name="impersonate-stop"),
    *router.urls,
]
