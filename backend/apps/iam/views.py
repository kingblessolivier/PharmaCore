"""Auth views: JWT login (with audit) and the current-user endpoint."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import Count, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.iam.audit import _client_ip, record_audit
from apps.iam.models import (
    AuditLog,
    Company,
    Department,
    ImpersonationSession,
    License,
    Organization,
    Permission,
    Role,
    User,
)
from apps.iam.permissions import CanManageOrg, IsAdminRole, IsSysAdmin
from apps.iam.scoping import organizations_visible_to
from apps.iam.serializers import (
    AuditLogSerializer,
    CompanySerializer,
    DepartmentSerializer,
    LicenseSerializer,
    OrganizationSerializer,
    PermissionSerializer,
    RoleSerializer,
    UserAdminSerializer,
    UserSerializer,
)


def _token_claim(request: Request, key: str) -> Any:
    """Read a custom claim off the request's validated JWT (None if absent)."""
    token = request.auth
    if token is None:
        return None
    return token.get(key)  # type: ignore[union-attr]


def _user_by_identifier(identifier: str) -> User | None:
    """Look up a user by username or (non-empty) PF number — mirrors the login backend."""
    from django.db.models import Q

    if not identifier:
        return None
    return User.objects.filter(
        Q(username=identifier) | Q(pf_number=identifier, pf_number__gt="")
    ).first()


class LoginView(TokenObtainPairView):
    """Obtain a JWT access/refresh pair; records an audit entry on success.

    The ``username`` field accepts either a username or a PF/staff number.
    """

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        identifier = request.data.get("username", "")
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            # Failed login (bad credentials / inactive) — record a security event.
            user = _user_by_identifier(identifier)
            record_audit(action="LOGIN_FAILED", user=user, entity_type="auth", request=request)
            raise
        if response.status_code == status.HTTP_200_OK:
            user = _user_by_identifier(identifier)
            record_audit(action="LOGIN", user=user, entity_type="auth", request=request)
        return response


class MeView(APIView):
    """Return the authenticated user's profile (plus the impersonator, if any)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        data = dict(UserSerializer(user).data)
        data["permissions"] = sorted(user.permission_codes())
        admin_id = _token_claim(request, "act_as_admin_id")
        if admin_id:
            admin = User.objects.filter(pk=admin_id).first()
            data["impersonator"] = (
                {"id": admin.pk, "username": admin.username} if admin else None
            )
        return Response(data)


class ImpersonateView(APIView):
    """Admin **view-as**: start a session and return an access token *for the target
    user*, carrying the admin's id + session id so the app can show a banner and the
    action is fully audited. Admin-only, scope-checked, never self/other-admin."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request: Request) -> Response:
        actor = cast(User, request.user)
        if _token_claim(request, "act_as_admin_id"):
            raise PermissionDenied("Already viewing as another user — exit first.")
        target = get_object_or_404(User, pk=request.data.get("user_id"))
        if target.pk == actor.pk:
            raise PermissionDenied("You cannot view as yourself.")
        if target.is_superuser or target.has_role("SYS_ADMIN"):
            raise PermissionDenied("You cannot view as another system admin.")
        if not (actor.is_superuser or actor.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(actor)
            if not target.organization_id or not visible.filter(pk=target.organization_id).exists():
                raise PermissionDenied("That user is outside your organization.")
        session = ImpersonationSession.objects.create(
            admin=actor, target=target, ip_address=_client_ip(request)
        )
        token = AccessToken.for_user(target)
        token["act_as_admin_id"] = actor.pk
        token["imp"] = session.pk
        record_audit(
            action="IMPERSONATE_START",
            user=actor,
            organization=target.organization,
            entity_type="user",
            entity_id=str(target.pk),
            changes={"target": target.username, "session": session.pk},
            request=request,
        )
        return Response({"access": str(token), "target": UserSerializer(target).data})


class StopImpersonateView(APIView):
    """End the current view-as session (called with the impersonation token)."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        session_id = _token_claim(request, "imp")
        if session_id:
            session = ImpersonationSession.objects.filter(
                pk=session_id, ended_at__isnull=True
            ).first()
            if session:
                session.ended_at = timezone.now()
                session.save(update_fields=["ended_at"])
                record_audit(
                    action="IMPERSONATE_STOP",
                    user=session.admin,
                    organization=session.target.organization,
                    entity_type="user",
                    entity_id=str(session.target_id),
                    changes={"target": session.target.username, "session": session.pk},
                    request=request,
                )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CompanyViewSet(viewsets.ModelViewSet):
    """The legal business entities that own branches. SYS_ADMIN sees all; an
    ORG_ADMIN sees only the company their organization belongs to. Writes are
    admin-gated and audited; a company with branches can't be hard-deleted."""

    serializer_class = CompanySerializer
    queryset = Company.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), CanManageOrg()]
        return [IsAuthenticated()]

    def get_queryset(self) -> QuerySet[Company]:
        user = cast(User, self.request.user)
        qs = Company.objects.all()
        if user.is_superuser or user.has_role("SYS_ADMIN"):
            return qs
        company_id = user.organization.company_id if user.organization else None
        return qs.filter(pk=company_id) if company_id else qs.none()

    def _audit(self, action: str, obj: Company) -> None:
        record_audit(
            action=action,
            user=cast(User, self.request.user),
            entity_type="company",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        self._audit("CREATE", serializer.save())

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        self._audit("UPDATE", serializer.save())

    def perform_destroy(self, instance: Company) -> None:
        if instance.branches.exists():
            raise ValidationError("Detach this company's branches before deleting it.")
        self._audit("DELETE", instance)
        instance.delete()


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


class RoleViewSet(viewsets.ModelViewSet):
    """Roles = bundles of permissions. Read for any authed user (the role picker +
    the permission matrix); **editing a role's permissions is SYS_ADMIN‑only** since
    roles are system‑wide, and every change is audited."""

    serializer_class = RoleSerializer
    queryset = Role.objects.prefetch_related("permissions").all()
    pagination_class = None
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in {"update", "partial_update"}:
            return [IsAuthenticated(), IsSysAdmin()]
        return [IsAuthenticated()]

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        role = serializer.save()
        record_audit(
            action="UPDATE",
            user=cast(User, self.request.user),
            entity_type="role",
            entity_id=str(role.pk),
            changes={"permissions": sorted(role.permissions.values_list("code", flat=True))},
            request=self.request,
        )


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """The full permission catalogue (resource × action) for the matrix."""

    serializer_class = PermissionSerializer
    queryset = Permission.objects.all()
    permission_classes = [IsAuthenticated, IsAdminRole]
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
        params = self.request.query_params
        if org := params.get("organization"):
            qs = qs.filter(organization_id=org)
        if user_id := params.get("user"):
            qs = qs.filter(user_id=user_id)
        if act := params.get("action"):
            qs = qs.filter(action=act)
        if entity := params.get("entity_type"):
            qs = qs.filter(entity_type=entity)
        if since := params.get("since"):
            qs = qs.filter(created_at__date__gte=since)
        if until := params.get("until"):
            qs = qs.filter(created_at__date__lte=until)
        return qs.order_by("-created_at")


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

    @action(detail=True, methods=["get"])
    def activity(self, request: Request, pk: str | None = None) -> Response:
        """What this user has been doing: recent audit trail + action counts + last login.

        Org-scoped via ``get_object`` (uses ``get_queryset``), so an ORG_ADMIN can only
        inspect users in their own organization.
        """
        user = self.get_object()
        logs = AuditLog.objects.filter(user=user).order_by("-created_at")
        counts = {
            row["action"]: row["n"]
            for row in logs.values("action").annotate(n=Count("id")).order_by("-n")
        }
        return Response(
            {
                "user": UserSerializer(user).data,
                "last_login": user.last_login,
                "counts": counts,
                "recent": AuditLogSerializer(logs[:50], many=True).data,
            }
        )

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
