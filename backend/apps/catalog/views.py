"""Catalog API: products & manufacturers. Read for any authed user; writes are
admin-only and audited. The catalog is a global master (not org-scoped)."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import QuerySet
from rest_framework import filters, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.serializers import BaseSerializer

from apps.catalog.models import (
    ActiveIngredient,
    Manufacturer,
    Product,
    ProductBarcode,
    ProductIngredient,
    Supplier,
)
from apps.catalog.serializers import (
    ActiveIngredientSerializer,
    ManufacturerSerializer,
    ProductBarcodeSerializer,
    ProductIngredientSerializer,
    ProductSerializer,
    SupplierSerializer,
)
from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.iam.permissions import IsAdminRole

_WRITE_ACTIONS = {"create", "update", "partial_update", "destroy"}


class _AuditedAdminViewSet(viewsets.ModelViewSet):
    """Base: reads for any authed user, writes admin-only, every write audited."""

    entity_type = ""
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in _WRITE_ACTIONS:
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def _audit(self, action: str, pk: object) -> None:
        record_audit(
            action=action,
            user=cast(User, self.request.user),
            entity_type=self.entity_type,
            entity_id=str(pk),
            request=self.request,
        )

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        obj = serializer.save()
        self._audit("CREATE", obj.pk)

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        obj = serializer.save()
        self._audit("UPDATE", obj.pk)

    def perform_destroy(self, instance: Any) -> None:
        self._audit("DELETE", instance.pk)
        instance.delete()


class ProductViewSet(_AuditedAdminViewSet):
    entity_type = "product"
    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["generic_name", "brand_name", "atc_code", "gtin"]
    ordering_fields = ["generic_name", "created_at"]


class ManufacturerViewSet(_AuditedAdminViewSet):
    entity_type = "manufacturer"
    serializer_class = ManufacturerSerializer
    queryset = Manufacturer.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "country"]


class SupplierViewSet(_AuditedAdminViewSet):
    entity_type = "supplier"
    serializer_class = SupplierSerializer
    queryset = Supplier.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "tin"]


class ActiveIngredientViewSet(_AuditedAdminViewSet):
    entity_type = "active_ingredient"
    serializer_class = ActiveIngredientSerializer
    queryset = ActiveIngredient.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "atc_code"]


class ProductIngredientViewSet(_AuditedAdminViewSet):
    entity_type = "product_ingredient"
    serializer_class = ProductIngredientSerializer
    queryset = ProductIngredient.objects.select_related("ingredient").all()

    def get_queryset(self) -> QuerySet[ProductIngredient]:
        qs = ProductIngredient.objects.select_related("ingredient").all()
        product = self.request.query_params.get("product")
        return qs.filter(product_id=product) if product else qs


class ProductBarcodeViewSet(_AuditedAdminViewSet):
    entity_type = "product_barcode"
    serializer_class = ProductBarcodeSerializer
    queryset = ProductBarcode.objects.all()

    def get_queryset(self) -> QuerySet[ProductBarcode]:
        qs = ProductBarcode.objects.all()
        product = self.request.query_params.get("product")
        return qs.filter(product_id=product) if product else qs
