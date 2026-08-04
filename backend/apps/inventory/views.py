"""Inventory API: per-pharmacy product listing (products + price).

Org-scoped; reads for any authed user in the org, writes admin/manager-only and audited.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

from django.db.models import QuerySet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.iam.permissions import CanManageOrg
from apps.iam.scoping import organizations_visible_to
from apps.inventory.models import InventoryBatch, PharmacyProduct, StockMovement
from apps.inventory.serializers import (
    IntakeSerializer,
    InventoryBatchSerializer,
    PharmacyProductSerializer,
    StockMovementSerializer,
)
from apps.inventory.services import adjust_stock, log_wastage, receive_intake

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


class InventoryBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Batch stock-on-hand, org-scoped, FEFO-ordered (soonest expiry first)."""

    serializer_class = InventoryBatchSerializer
    queryset = InventoryBatch.objects.select_related("product", "organization").all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[InventoryBatch]:
        user = cast(User, self.request.user)
        qs = InventoryBatch.objects.select_related("product").filter(
            organization__in=organizations_visible_to(user)
        )
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        if self.request.query_params.get("in_stock") == "1":
            qs = qs.filter(quantity_available__gt=0)
        within = self.request.query_params.get("expiring_within")
        if within:
            qs = qs.filter(expiry_date__lte=date.today() + timedelta(days=int(within)))
        return qs  # default ordering = FEFO (expiry_date)

    def _act(self, action_name: str, batch: InventoryBatch, changes: dict[str, object]) -> None:
        record_audit(
            action=action_name,
            user=cast(User, self.request.user),
            organization=batch.organization,
            entity_type="inventory_batch",
            entity_id=str(batch.pk),
            changes=changes,
            request=self.request,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def adjust(self, request: Request, pk: str | None = None) -> Response:
        """Correct a batch to a physically-counted quantity (logs the delta)."""
        batch = self.get_object()
        try:
            counted = int(request.data["counted_quantity"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError({"counted_quantity": "An integer is required."}) from exc
        reason = str(request.data.get("reason", ""))
        try:
            adjust_stock(
                batch=batch, counted_quantity=counted, reason=reason, user=cast(User, request.user)
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        self._act("ADJUSTMENT", batch, {"counted": counted, "reason": reason})
        return Response(InventoryBatchSerializer(batch).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def waste(self, request: Request, pk: str | None = None) -> Response:
        """Remove expired/damaged stock from a batch (never below zero)."""
        batch = self.get_object()
        try:
            qty = int(request.data["quantity"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError({"quantity": "An integer is required."}) from exc
        reason = str(request.data.get("reason", ""))
        try:
            log_wastage(batch=batch, quantity=qty, reason=reason, user=cast(User, request.user))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        self._act("WASTAGE", batch, {"quantity": qty, "reason": reason})
        return Response(InventoryBatchSerializer(batch).data)


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """The immutable stock-movement ledger, org-scoped."""

    serializer_class = StockMovementSerializer
    queryset = StockMovement.objects.select_related("product", "created_by").all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[StockMovement]:
        user = cast(User, self.request.user)
        qs = StockMovement.objects.select_related("product", "created_by").filter(
            organization__in=organizations_visible_to(user)
        )
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs


class IntakeView(APIView):
    """Receive supplier stock into a pharmacy: creates/updates a batch + INTAKE
    movement (one transaction). Admin/manager-only, audited."""

    permission_classes = [IsAuthenticated, CanManageOrg]

    def post(self, request: Request) -> Response:
        ser = IntakeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        actor = cast(User, request.user)
        if not organizations_visible_to(actor).filter(pk=data["organization"].pk).exists():
            raise PermissionDenied("You cannot receive stock for that organization.")
        # Manual intake is for depots importing from suppliers. Retail pharmacies
        # must receive stock through transfers, so they never re-key (or double-count) it.
        if data["organization"].type != "DEPOT":
            raise PermissionDenied(
                "Only depots receive supplier intake. Retail branches get stock via transfers."
            )
        batch = receive_intake(
            organization=data["organization"],
            product=data["product"],
            batch_number=data["batch_number"],
            expiry_date=data["expiry_date"],
            quantity=data["quantity"],
            manufacture_date=data.get("manufacture_date"),
            wholesale_cost=data.get("wholesale_cost"),
            storage_location=data.get("storage_location", ""),
            user=actor,
            source_supplier=data.get("supplier"),
        )
        record_audit(
            action="INTAKE",
            user=actor,
            organization=data["organization"],
            entity_type="inventory_batch",
            entity_id=str(batch.pk),
            changes={"quantity": data["quantity"], "batch": data["batch_number"]},
            request=request,
        )
        return Response(InventoryBatchSerializer(batch).data, status=status.HTTP_201_CREATED)
