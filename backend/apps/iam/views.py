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
from apps.iam.models import Department, Organization, User
from apps.iam.permissions import CanManageOrg
from apps.iam.scoping import organizations_visible_to
from apps.iam.serializers import (
    DepartmentSerializer,
    OrganizationSerializer,
    UserSerializer,
)


class LoginView(TokenObtainPairView):
    """Obtain a JWT access/refresh pair; records an audit entry on success."""

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            username = request.data.get("username", "")
            user = User.objects.filter(username=username).first()
            record_audit(action="LOGIN", user=user, request=request)
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
            entity_type="organization",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        obj = serializer.save()
        record_audit(
            action="UPDATE",
            user=cast(User, self.request.user),
            entity_type="organization",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_destroy(self, instance: Organization) -> None:
        record_audit(
            action="DELETE",
            user=cast(User, self.request.user),
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
            entity_type="department",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        obj = serializer.save()
        record_audit(
            action="UPDATE",
            user=cast(User, self.request.user),
            entity_type="department",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_destroy(self, instance: Department) -> None:
        record_audit(
            action="DELETE",
            user=cast(User, self.request.user),
            entity_type="department",
            entity_id=str(instance.pk),
            request=self.request,
        )
        instance.delete()
