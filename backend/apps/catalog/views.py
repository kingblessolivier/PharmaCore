"""Catalog API: products & manufacturers. Read for any authed user; writes are
admin-only and audited. The catalog is a global master (not org-scoped)."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import QuerySet
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
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

_WRITE_ACTIONS = {"create", "update", "partial_update", "destroy", "bulk_import"}


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


_IMPORT_TEXT = {
    "generic_name",
    "brand_name",
    "strength",
    "pack_size",
    "unit_of_measure",
    "atc_code",
    "gtin",
    "fda_registration_number",
    "rra_item_code",
    "controlled_schedule",
    "dosage_form",
    "storage_condition",
    "route_of_administration",
    "tax_class",
}
_IMPORT_INT = {"units_per_pack", "reorder_level", "reorder_quantity"}
_IMPORT_BOOL = {"requires_prescription", "is_controlled_substance"}


def _clean_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only known Product fields from a CSV row, coercing types."""
    out: dict[str, Any] = {}
    for k, v in raw.items():
        key = str(k).strip().lower()
        val = str(v).strip() if v is not None else ""
        if key in _IMPORT_TEXT:
            out[key] = val
        elif key in _IMPORT_INT:
            out[key] = int(val) if val.isdigit() else 0
        elif key in _IMPORT_BOOL:
            out[key] = val.lower() in {"1", "true", "yes", "y"}
    return out


class ProductViewSet(_AuditedAdminViewSet):
    entity_type = "product"
    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["generic_name", "brand_name", "atc_code", "gtin"]
    ordering_fields = ["generic_name", "created_at"]

    @action(detail=False, methods=["post"], url_path="import")
    def bulk_import(self, request: Request) -> Response:
        """Bulk create/update products from CSV rows. Admin-only.

        Matches an existing product by GTIN (if given) else by
        generic_name+strength+brand_name. Unknown columns are ignored."""
        rows = request.data.get("rows", [])
        if not isinstance(rows, list) or not rows:
            return Response({"detail": "No rows provided."}, status=400)
        created = updated = 0
        errors: list[dict[str, Any]] = []
        for i, raw in enumerate(rows):
            if not isinstance(raw, dict):
                continue
            data = _clean_row(raw)
            if not data.get("generic_name"):
                errors.append({"row": i + 1, "error": "generic_name is required"})
                continue
            try:
                existing = None
                if data.get("gtin"):
                    existing = Product.objects.filter(gtin=data["gtin"]).first()
                if existing is None:
                    existing = Product.objects.filter(
                        generic_name__iexact=data["generic_name"],
                        strength=data.get("strength", ""),
                        brand_name=data.get("brand_name", ""),
                    ).first()
                if existing is None:
                    Product.objects.create(**data)
                    created += 1
                else:
                    for k, v in data.items():
                        setattr(existing, k, v)
                    existing.save()
                    updated += 1
            except Exception as exc:  # noqa: BLE001 - report the row, keep importing
                errors.append({"row": i + 1, "error": str(exc)})
        self._audit("IMPORT", f"created={created},updated={updated}")
        return Response({"created": created, "updated": updated, "errors": errors})


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
