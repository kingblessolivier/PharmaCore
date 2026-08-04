"""DRF permission classes for base RBAC."""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.iam.models import User


class HasRole(BasePermission):
    """Grant access only to authenticated users holding a given role code.

    Use via ``HasRole.require("SYS_ADMIN")`` in a view's ``permission_classes``.
    Superusers always pass.
    """

    required_role: str = ""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        if user.is_superuser:
            return True
        return user.has_role(self.required_role)

    @classmethod
    def require(cls, role_code: str) -> type[HasRole]:
        return type(f"HasRole_{role_code}", (cls,), {"required_role": role_code})


class CanManageOrg(BasePermission):
    """Allow only SYS_ADMIN / ORG_ADMIN (or superuser) to create/modify org data."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        return user.is_superuser or user.has_role("SYS_ADMIN") or user.has_role("ORG_ADMIN")
