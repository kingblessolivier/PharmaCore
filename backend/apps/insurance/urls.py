from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.insurance.views import (
    ClaimViewSet,
    EligibilityView,
    InsuranceOverviewView,
    InsuranceSchemeViewSet,
    MemberPolicyViewSet,
    RemittanceAdviceViewSet,
    SchemeFormularyViewSet,
)

router = DefaultRouter()
router.register("schemes", InsuranceSchemeViewSet, basename="insurance-scheme")
router.register("policies", MemberPolicyViewSet, basename="member-policy")
router.register("formulary", SchemeFormularyViewSet, basename="scheme-formulary")
router.register("claims", ClaimViewSet, basename="insurance-claim")
router.register("remittances", RemittanceAdviceViewSet, basename="remittance-advice")

urlpatterns = [
    path("overview/", InsuranceOverviewView.as_view(), name="insurance-overview"),
    # Asked before dispensing, not after — an expired card found at claim time is
    # a debt the pharmacy has already incurred.
    path("eligibility/", EligibilityView.as_view(), name="insurance-eligibility"),
    *router.urls,
]
