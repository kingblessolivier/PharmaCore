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


class HasPermission(BasePermission):
    """Grant access only to users whose roles include a given permission code.

    Use via ``HasPermission.require("sale.void")``. Superusers / SYS_ADMIN always pass
    (see ``User.has_permission``).
    """

    required_permission: str = ""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        return user.has_permission(self.required_permission)

    @classmethod
    def require(cls, code: str) -> type[HasPermission]:
        return type(f"HasPermission_{code}", (cls,), {"required_permission": code})


class IsSysAdmin(BasePermission):
    """Only a superuser or SYS_ADMIN — for system-wide config like the role matrix."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        return bool(user.is_superuser or user.has_role("SYS_ADMIN"))


class IsAdminRole(BasePermission):
    """Reusable check: superuser, SYS_ADMIN, or ORG_ADMIN. Used to gate admin writes."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        return user.is_superuser or user.has_role("SYS_ADMIN") or user.has_role("ORG_ADMIN")


class CanManageOrg(IsAdminRole):
    """Allow only SYS_ADMIN / ORG_ADMIN (or superuser) to create/modify org data."""
