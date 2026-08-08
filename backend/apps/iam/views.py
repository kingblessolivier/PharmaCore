"""Auth views: JWT login (with audit) and the current-user endpoint."""

from __future__ import annotations

import csv
from typing import Any, cast

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, QuerySet
from django.http import HttpResponse
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

from apps.iam import authority
from apps.iam.audit import _client_ip, record_audit
from apps.iam.authentication import (
    VersionedTokenObtainPairSerializer,
    generate_api_key,
)
from apps.iam.models import (
    ApiKey,
    AuditLog,
    Company,
    Department,
    ImpersonationSession,
    License,
    Organization,
    OrganizationDocument,
    Permission,
    Role,
    User,
    UserDocument,
)
from apps.iam.permissions import CanManageOrg, IsAdminRole, IsSysAdmin
from apps.iam.scoping import organizations_visible_to
from apps.iam.serializers import (
    ApiKeySerializer,
    AuditLogSerializer,
    CompanySerializer,
    DepartmentSerializer,
    LicenseSerializer,
    OrganizationDocumentSerializer,
    OrganizationSerializer,
    PermissionSerializer,
    RoleSerializer,
    UserAdminSerializer,
    UserDocumentSerializer,
    UserSerializer,
)


def _token_claim(request: Request, key: str) -> Any:
    """Read a custom claim off the request's validated JWT (None if absent or if the
    request was authenticated by something else, e.g. an API key)."""
    token = request.auth
    if token is None or not hasattr(token, "get"):
        return None
    return token.get(key)


def _check_password_strength(password: str, user: User | None = None) -> None:
    """Run Django's configured password validators; re-raise as a DRF 400."""
    if not password:
        raise ValidationError("A password is required.")
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError(list(exc.messages)) from exc


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

    serializer_class = VersionedTokenObtainPairSerializer  # type: ignore[assignment]

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
        data["must_change_password"] = user.must_change_password
        admin_id = _token_claim(request, "act_as_admin_id")
        if admin_id:
            admin = User.objects.filter(pk=admin_id).first()
            data["impersonator"] = {"id": admin.pk, "username": admin.username} if admin else None
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
        token["tv"] = target.token_version
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


class ChangePasswordView(APIView):
    """Let the signed-in user change their own password (old + new, strength-checked)."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        old = str(request.data.get("old_password", ""))
        new = str(request.data.get("new_password", ""))
        if not user.check_password(old):
            raise ValidationError({"old_password": "Current password is incorrect."})
        _check_password_strength(new, user)
        user.set_password(new)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        record_audit(
            action="PASSWORD_CHANGE",
            user=user,
            organization=user.organization,
            entity_type="user",
            entity_id=str(user.pk),
            request=request,
        )
        return Response({"detail": "Password changed."})


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

    def _set_status(self, request: Request, status_value: str, action_name: str) -> Response:
        org = self.get_object()
        user = cast(User, request.user)
        is_admin = user.is_superuser or user.has_role("SYS_ADMIN")
        if not is_admin and not organizations_visible_to(user).filter(pk=org.pk).exists():
            raise PermissionDenied("You cannot manage that organization.")
        org.onboarding_status = status_value
        org.is_active = status_value == Organization.OnboardingStatus.ACTIVE
        org.save(update_fields=["onboarding_status", "is_active", "updated_at"])
        record_audit(
            action=action_name,
            user=user,
            organization=org,
            entity_type="organization",
            entity_id=str(org.pk),
            changes={"onboarding_status": status_value},
            request=request,
        )
        return Response(OrganizationSerializer(org).data)

    @action(detail=True, methods=["post"])
    def activate(self, request: Request, pk: str | None = None) -> Response:
        """Pass the activation gate — the organization may now trade."""
        return self._set_status(request, Organization.OnboardingStatus.ACTIVE, "ORG_ACTIVATE")

    @action(detail=True, methods=["post"])
    def suspend(self, request: Request, pk: str | None = None) -> Response:
        """Suspend an organization (stops it trading) — reversible via activate."""
        return self._set_status(request, Organization.OnboardingStatus.SUSPENDED, "ORG_SUSPEND")

    @action(detail=True, methods=["get"])
    def performance(self, request: Request, pk: str | None = None) -> Response:
        """How a branch is performing: sales, dispensing, and its staff headcount."""
        org = self.get_object()
        from apps.retail.models import Dispensing, Sale

        completed = Sale.objects.filter(organization=org, status=Sale.Status.COMPLETED)
        return Response(
            {
                "sales_count": completed.count(),
                "dispensing_count": Dispensing.objects.filter(sale__organization=org).count(),
                "users": User.objects.filter(organization=org).count(),
                "active_users": User.objects.filter(organization=org, is_active=True).count(),
            }
        )


class OrganizationDocumentViewSet(viewsets.ModelViewSet):
    """Registration / compliance documents for organizations. Admin-gated, org-scoped;
    filter with ``?organization=<id>``. Verifiable; every write is audited."""

    serializer_class = OrganizationDocumentSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    queryset = OrganizationDocument.objects.select_related("organization", "verified_by")

    def get_queryset(self) -> QuerySet[OrganizationDocument]:
        user = cast(User, self.request.user)
        qs = OrganizationDocument.objects.select_related("organization", "verified_by").filter(
            organization__in=organizations_visible_to(user)
        )
        org = self.request.query_params.get("organization")
        if org and org.isdigit():
            qs = qs.filter(organization_id=int(org))
        return qs

    def _guard(self, serializer: BaseSerializer[Any]) -> None:
        user = cast(User, self.request.user)
        org = serializer.validated_data.get("organization")
        if org and not organizations_visible_to(user).filter(pk=org.pk).exists():
            raise PermissionDenied("That organization is outside your scope.")

    def _audit(self, action: str, obj: OrganizationDocument) -> None:
        record_audit(
            action=action,
            user=cast(User, self.request.user),
            organization=obj.organization,
            entity_type="organization_document",
            entity_id=str(obj.pk),
            changes={"doc_type": obj.doc_type},
            request=self.request,
        )

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        self._guard(serializer)
        self._audit("CREATE", serializer.save())

    def perform_destroy(self, instance: OrganizationDocument) -> None:
        self._audit("DELETE", instance)
        instance.delete()

    @action(detail=True, methods=["post"])
    def verify(self, request: Request, pk: str | None = None) -> Response:
        doc = self.get_object()
        doc.is_verified = True
        doc.verified_by = cast(User, request.user)
        doc.save(update_fields=["is_verified", "verified_by"])
        self._audit("VERIFY", doc)
        return Response(OrganizationDocumentSerializer(doc).data)


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

    @action(detail=False, methods=["get"])
    def export(self, request: Request) -> HttpResponse:
        """Download the (filtered) audit trail as CSV — same filters as the list."""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit-log.csv"'
        writer = csv.writer(response)
        writer.writerow(
            ["when", "user", "action", "entity_type", "entity_id", "organization", "ip"]
        )
        for row in self.filter_queryset(self.get_queryset())[:10000]:
            writer.writerow(
                [
                    row.created_at.isoformat(),
                    row.user.username if row.user else "",
                    row.action,
                    row.entity_type,
                    row.entity_id,
                    row.organization_id or "",
                    row.ip_address or "",
                ]
            )
        return response


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

    def _assert_may_grant(self, serializer: BaseSerializer[Any]) -> None:
        """R4 — you cannot give away what you do not hold.

        ``authority.can_delegate`` existed and was called from exactly one place:
        reassigning an approval. Assigning a *role* was unchecked, so an ORG_ADMIN
        could grant SYS_ADMIN and an approval limit larger than their own — which
        makes every other rule in the authority model optional, since anyone who
        can administer users can simply grant themselves past it.
        """
        actor = cast(User, self.request.user)
        if actor.is_superuser or actor.has_role("SYS_ADMIN"):
            return

        roles = serializer.validated_data.get("roles")
        if roles:
            # SYS_ADMIN carries no explicit permission rows — it holds every
            # permission implicitly (see User.has_permission). Comparing
            # permission sets therefore waved it straight through: the role with
            # the most power was the one the ceiling could not see. It is named
            # here rather than inferred, because "grants everything" is a
            # property of the code, not of the data.
            if any(role.code == "SYS_ADMIN" for role in roles):
                raise PermissionDenied("Only a system administrator may grant the SYS_ADMIN role.")
            wanted: set[str] = set()
            for role in roles:
                wanted |= set(role.permissions.values_list("code", flat=True))
            check = authority.can_delegate(granter=actor, permission_codes=wanted)
            if not check.allowed:
                raise PermissionDenied(check.reason)

        limit = serializer.validated_data.get("approval_limit")
        if limit is not None:
            mine = authority.approval_limit(actor)
            # `None` is an unlimited ceiling — only SYS_ADMIN reaches here with one.
            if mine is not None and limit > mine:
                raise PermissionDenied(
                    f"You cannot grant an approval limit of {limit}; your own is {mine}."
                )

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

    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request: Request, pk: str | None = None) -> Response:
        """Admin resets a user's password (strength-checked); the user must then change
        it on next sign-in (``must_change_password``). Org-scoped via ``get_object``."""
        target = self.get_object()
        actor = cast(User, request.user)
        if target.pk == actor.pk:
            raise ValidationError("Use 'change password' to update your own password.")
        new = str(request.data.get("password", ""))
        _check_password_strength(new, target)
        target.set_password(new)
        target.must_change_password = True
        target.save(update_fields=["password", "must_change_password"])
        record_audit(
            action="PASSWORD_RESET",
            user=actor,
            organization=target.organization,
            entity_type="user",
            entity_id=str(target.pk),
            request=request,
        )
        return Response({"detail": "Password reset. The user must change it on next sign-in."})

    @action(detail=True, methods=["post"], url_path="force-logout")
    def force_logout(self, request: Request, pk: str | None = None) -> Response:
        """Revoke all of a user's sessions: bump token_version so every outstanding
        token (access + refresh) is rejected on next use. Audited."""
        target = self.get_object()
        target.token_version += 1
        target.save(update_fields=["token_version"])
        record_audit(
            action="FORCE_LOGOUT",
            user=cast(User, request.user),
            organization=target.organization,
            entity_type="user",
            entity_id=str(target.pk),
            request=request,
        )
        return Response({"detail": "All of this user's sessions have been ended."})

    @action(detail=True, methods=["get"])
    def performance(self, request: Request, pk: str | None = None) -> Response:
        """How a person is performing: sales rung, items dispensed, returns/voids,
        logins, last login. Org-scoped via ``get_object``."""
        user = self.get_object()
        from apps.retail.models import Dispensing, Sale

        completed = Sale.objects.filter(cashier=user, status=Sale.Status.COMPLETED)
        counts = {
            row["action"]: row["n"]
            for row in AuditLog.objects.filter(user=user).values("action").annotate(n=Count("id"))
        }
        return Response(
            {
                "sales_count": completed.count(),
                "dispensing_count": Dispensing.objects.filter(dispensed_by=user).count(),
                "returns": counts.get("SALE_RETURN", 0),
                "voids": counts.get("SALE_VOID", 0),
                "logins": counts.get("LOGIN", 0),
                "last_login": user.last_login,
            }
        )

    def _guard_org(self, serializer: BaseSerializer[Any]) -> None:
        actor = cast(User, self.request.user)
        org = serializer.validated_data.get("organization")
        if org and not organizations_visible_to(actor).filter(pk=org.pk).exists():
            raise PermissionDenied("You cannot manage users in that organization.")

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        self._guard_org(serializer)
        self._assert_may_grant(serializer)
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
        self._assert_may_grant(serializer)
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


class ApiKeyViewSet(viewsets.ModelViewSet):
    """Service-account API keys. Admin-gated, org-scoped (a key acts as its user).
    Creating one returns the raw key **once**; only its hash is stored. Filter by
    ``?user=<id>``."""

    serializer_class = ApiKeySerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    http_method_names = ["get", "post", "delete", "head", "options"]
    queryset = ApiKey.objects.select_related("user")

    def _visible_users(self) -> QuerySet[User]:
        actor = cast(User, self.request.user)
        if actor.is_superuser or actor.has_role("SYS_ADMIN"):
            return User.objects.all()
        return User.objects.filter(organization__in=organizations_visible_to(actor))

    def get_queryset(self) -> QuerySet[ApiKey]:
        qs = ApiKey.objects.select_related("user").filter(user__in=self._visible_users())
        if user_id := self.request.query_params.get("user"):
            qs = qs.filter(user_id=user_id)
        return qs

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        actor = cast(User, request.user)
        name = str(request.data.get("name", "")).strip()
        target = get_object_or_404(User, pk=request.data.get("user"))
        if not name:
            raise ValidationError("Give the key a name.")
        if not self._visible_users().filter(pk=target.pk).exists():
            raise PermissionDenied("That user is outside your organization.")
        raw, prefix, key_hash = generate_api_key()
        key = ApiKey.objects.create(
            name=name, user=target, prefix=prefix, key_hash=key_hash, created_by=actor
        )
        record_audit(
            action="API_KEY_CREATE",
            user=actor,
            organization=target.organization,
            entity_type="api_key",
            entity_id=str(key.pk),
            changes={"name": name, "for_user": target.username},
            request=request,
        )
        data = dict(ApiKeySerializer(key).data)
        data["key"] = raw  # shown once
        return Response(data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance: ApiKey) -> None:
        record_audit(
            action="API_KEY_REVOKE",
            user=cast(User, self.request.user),
            organization=instance.user.organization,
            entity_type="api_key",
            entity_id=str(instance.pk),
            request=self.request,
        )
        instance.delete()


class UserDocumentViewSet(viewsets.ModelViewSet):
    """Identity documents attached to a user account. Admin-gated, org-scoped;
    filter with ``?user=<id>``. Every write is audited; documents can be verified."""

    serializer_class = UserDocumentSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    queryset = UserDocument.objects.select_related("user", "verified_by")

    def _visible_users(self) -> QuerySet[User]:
        actor = cast(User, self.request.user)
        if actor.is_superuser or actor.has_role("SYS_ADMIN"):
            return User.objects.all()
        return User.objects.filter(organization__in=organizations_visible_to(actor))

    def get_queryset(self) -> QuerySet[UserDocument]:
        qs = UserDocument.objects.select_related("user", "verified_by").filter(
            user__in=self._visible_users()
        )
        user_id = self.request.query_params.get("user")
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs

    def _guard(self, serializer: BaseSerializer[Any]) -> None:
        target = serializer.validated_data.get("user")
        if target and not self._visible_users().filter(pk=target.pk).exists():
            raise PermissionDenied("That user is outside your organization.")

    def _audit(self, action: str, obj: UserDocument) -> None:
        record_audit(
            action=action,
            user=cast(User, self.request.user),
            organization=obj.user.organization,
            entity_type="user_document",
            entity_id=str(obj.pk),
            changes={"doc_type": obj.doc_type, "user": obj.user_id},
            request=self.request,
        )

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        self._guard(serializer)
        self._audit("CREATE", serializer.save())

    def perform_destroy(self, instance: UserDocument) -> None:
        self._audit("DELETE", instance)
        instance.delete()

    @action(detail=True, methods=["post"])
    def verify(self, request: Request, pk: str | None = None) -> Response:
        """Mark a document as verified (identity confirmed) by the acting admin."""
        doc = self.get_object()
        doc.is_verified = True
        doc.verified_by = cast(User, request.user)
        doc.save(update_fields=["is_verified", "verified_by"])
        self._audit("VERIFY", doc)
        return Response(UserDocumentSerializer(doc).data)
