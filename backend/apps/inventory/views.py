"""Inventory API: per-pharmacy product listing (products + price).

Org-scoped; reads for any authed user in the org, writes admin/manager-only and audited.
"""

from __future__ import annotations

from typing import Any, cast

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.serializers import BaseSerializer

from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.iam.permissions import CanManageOrg
from apps.iam.scoping import organizations_visible_to
from apps.inventory.models import PharmacyProduct
from apps.inventory.serializers import PharmacyProductSerializer

_WRITE = {"create", "update", "partial_update", "destroy"}


class PharmacyProductViewSet(viewsets.ModelViewSet):
    serializer_class = PharmacyProductSerializer
    queryset = PharmacyProduct.objects.select_related("product", "organization").all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in _WRITE:
            return [IsAuthenticated(), CanManageOrg()]
        return [IsAuthenticated()]

    def get_queryset(self) -> QuerySet[PharmacyProduct]:
        user = cast(User, self.request.user)
        qs = PharmacyProduct.objects.select_related("product", "organization").filter(
            organization__in=organizations_visible_to(user)
        )
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs

    def _guard(self, serializer: BaseSerializer[Any]) -> Any:
        user = cast(User, self.request.user)
        org = serializer.validated_data.get("organization")
        if org and not organizations_visible_to(user).filter(pk=org.pk).exists():
            raise PermissionDenied("You cannot manage stock for that organization.")
        return org

    def _audit(self, action: str, obj: PharmacyProduct) -> None:
        record_audit(
            action=action,
            user=cast(User, self.request.user),
            organization=obj.organization,
            entity_type="pharmacy_product",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        self._guard(serializer)
        self._audit("CREATE", serializer.save())

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        self._guard(serializer)
        self._audit("UPDATE", serializer.save())

    def perform_destroy(self, instance: PharmacyProduct) -> None:
        self._audit("DELETE", instance)
        instance.delete()
