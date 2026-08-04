"""Auth views: JWT login (with audit) and the current-user endpoint."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import QuerySet
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.iam.audit import record_audit
from apps.iam.models import AuditLog, Department, License, Organization, Role, User
from apps.iam.permissions import CanManageOrg, IsAdminRole
from apps.iam.scoping import organizations_visible_to
from apps.iam.serializers import (
    AuditLogSerializer,
    DepartmentSerializer,
    LicenseSerializer,
    OrganizationSerializer,
    RoleSerializer,
    UserAdminSerializer,
    UserSerializer,
)


class LoginView(TokenObtainPairView):
    """Obtain a JWT access/refresh pair; records an audit entry on success."""

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        username = request.data.get("username", "")
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            # Failed login (bad credentials / inactive) — record a security event.
            user = User.objects.filter(username=username).first()
            record_audit(action="LOGIN_FAILED", user=user, entity_type="auth", request=request)
            raise
        if response.status_code == status.HTTP_200_OK:
            user = User.objects.filter(username=username).first()
            record_audit(action="LOGIN", user=user, entity_type="auth", request=request)
        return response


class MeView(APIView):
    """Return the authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(UserSerializer(cast(User, request.user)).data)


class OrganizationViewSet(viewsets.ModelViewSet):
    """Organizations, tenant-scoped. Read for any authed user; writes need ORG/SYS admin.

    No hard delete (compliance) — deactivate via PATCH ``is_active``.
    """

    serializer_class = OrganizationSerializer
    queryset = Organization.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), CanManageOrg()]
        return [IsAuthenticated()]

    def get_queryset(self) -> QuerySet[Organization]:
        return organizations_visible_to(cast(User, self.request.user))

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        obj = serializer.save()
        record_audit(
            action="CREATE",
            user=cast(User, self.request.user),
            organization=obj,
            entity_type="organization",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        obj = serializer.save()
        record_audit(
            action="UPDATE",
            user=cast(User, self.request.user),
            organization=obj,
            entity_type="organization",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_destroy(self, instance: Organization) -> None:
        record_audit(
            action="DELETE",
            user=cast(User, self.request.user),
            organization=instance,
            entity_type="organization",
            entity_id=str(instance.pk),
            request=self.request,
        )
        instance.delete()


class DepartmentViewSet(viewsets.ModelViewSet):
    """Departments within visible organizations. Writes need ORG/SYS admin."""

    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), CanManageOrg()]
        return [IsAuthenticated()]

    def get_queryset(self) -> QuerySet[Department]:
        user = cast(User, self.request.user)
        return Department.objects.filter(organization__in=organizations_visible_to(user))

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        user = cast(User, self.request.user)
        org = serializer.validated_data["organization"]
        if not organizations_visible_to(user).filter(pk=org.pk).exists():
            raise PermissionDenied("You cannot add a department to that organization.")
        obj = serializer.save()
        record_audit(
            action="CREATE",
            user=user,
            organization=obj.organization,
            entity_type="department",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        obj = serializer.save()
        record_audit(
            action="UPDATE",
            user=cast(User, self.request.user),
            organization=obj.organization,
            entity_type="department",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_destroy(self, instance: Department) -> None:
        record_audit(
            action="DELETE",
            user=cast(User, self.request.user),
            organization=instance.organization,
            entity_type="department",
            entity_id=str(instance.pk),
            request=self.request,
        )
        instance.delete()


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list of assignable roles (for the role picker)."""

    serializer_class = RoleSerializer
    queryset = Role.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = None


class LicenseViewSet(viewsets.ModelViewSet):
    """Org + staff licences, org-scoped; admin-gated writes, audited."""

    serializer_class = LicenseSerializer
    queryset = License.objects.select_related("user", "organization").all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), CanManageOrg()]
        return [IsAuthenticated()]

    def get_queryset(self) -> QuerySet[License]:
        user = cast(User, self.request.user)
        qs = License.objects.select_related("user").filter(
            organization__in=organizations_visible_to(user)
        )
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs

    def _guard(self, serializer: BaseSerializer[Any]) -> None:
        user = cast(User, self.request.user)
        org = serializer.validated_data.get("organization")
        if org and not organizations_visible_to(user).filter(pk=org.pk).exists():
            raise PermissionDenied("You cannot manage licences for that organization.")

    def _audit(self, action: str, obj: License) -> None:
        record_audit(
            action=action,
            user=cast(User, self.request.user),
            organization=obj.organization,
            entity_type="license",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        self._guard(serializer)
        self._audit("CREATE", serializer.save())

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        self._guard(serializer)
        self._audit("UPDATE", serializer.save())

    def perform_destroy(self, instance: License) -> None:
        self._audit("DELETE", instance)
        instance.delete()


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only activity log, admin-only, org-scoped (?organization=<id>)."""

    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("user").all()
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self) -> QuerySet[AuditLog]:
        actor = cast(User, self.request.user)
        qs = AuditLog.objects.select_related("user").all()
        if not (actor.is_superuser or actor.has_role("SYS_ADMIN")):
            org_id = actor.organization_id
            qs = qs.filter(organization_id=org_id) if org_id else qs.none()
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs


class UserViewSet(viewsets.ModelViewSet):
    """Admin management of users, org-scoped. Admins only; every write audited.

    Filter by ``?organization=<id>`` (used by the pharmacy Manage view).
    """

    serializer_class = UserAdminSerializer
    queryset = User.objects.all().order_by("username")
    permission_classes = [IsAuthenticated, IsAdminRole]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet[User]:
        actor = cast(User, self.request.user)
        qs = User.objects.all().order_by("username")
        if not (actor.is_superuser or actor.has_role("SYS_ADMIN")):
            # ORG_ADMIN: only users in their own organization (deny if none).
            org_id = actor.organization_id
            qs = qs.filter(organization_id=org_id) if org_id else qs.none()
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs

    def _guard_org(self, serializer: BaseSerializer[Any]) -> None:
        actor = cast(User, self.request.user)
        org = serializer.validated_data.get("organization")
        if org and not organizations_visible_to(actor).filter(pk=org.pk).exists():
            raise PermissionDenied("You cannot manage users in that organization.")

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        self._guard_org(serializer)
        obj = serializer.save()
        record_audit(
            action="CREATE",
            user=cast(User, self.request.user),
            organization=obj.organization,
            entity_type="user",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        self._guard_org(serializer)
        obj = serializer.save()
        record_audit(
            action="UPDATE",
            user=cast(User, self.request.user),
            organization=obj.organization,
            entity_type="user",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_destroy(self, instance: User) -> None:
        record_audit(
            action="DELETE",
            user=cast(User, self.request.user),
            organization=instance.organization,
            entity_type="user",
            entity_id=str(instance.pk),
            request=self.request,
        )
        instance.delete()
