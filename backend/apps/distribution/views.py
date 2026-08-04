"""Distribution API: B2B purchase orders (retail → depot)."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import Q, QuerySet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.distribution.models import GoodsReceivedNote, StockOrder
from apps.distribution.serializers import GRNSerializer, StockOrderSerializer
from apps.distribution.services import (
    approve_and_allocate,
    dispatch_order,
    finalize_grn,
    open_grn,
    release_order_reservations,
)
from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to


class StockOrderViewSet(viewsets.ModelViewSet):
    """Purchase orders. A retail org creates orders to a depot; both parties see them.

    Scoping: SYS_ADMIN sees all; others see orders where their org is the depot or
    the retail party. Create is limited to your own retail org (admins: any).
    """

    serializer_class = StockOrderSerializer
    queryset = StockOrder.objects.select_related("depot", "retail").prefetch_related("items")
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[StockOrder]:
        user = cast(User, self.request.user)
        qs = StockOrder.objects.select_related("depot", "retail").prefetch_related("items")
        if user.is_superuser or user.has_role("SYS_ADMIN"):
            pass
        else:
            visible = organizations_visible_to(user)
            qs = qs.filter(Q(depot__in=visible) | Q(retail__in=visible))
        role = self.request.query_params.get("role")
        org_param = self.request.query_params.get("organization")
        if org_param and org_param.isdigit():
            if role == "depot":
                qs = qs.filter(depot_id=int(org_param))
            elif role == "retail":
                qs = qs.filter(retail_id=int(org_param))
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        user = cast(User, self.request.user)
        retail = serializer.validated_data["retail"]
        is_admin = user.is_superuser or user.has_role("SYS_ADMIN") or user.has_role("ORG_ADMIN")
        if not is_admin and user.organization_id != retail.pk:
            raise PermissionDenied("You can only create orders for your own organization.")
        if not serializer.validated_data.get("items"):
            raise ValidationError("An order needs at least one item.")
        order = serializer.save(ordered_by=user, status=StockOrder.Status.DRAFT)
        order.order_number = f"PO-{order.pk:05d}"
        order.save(update_fields=["order_number"])
        record_audit(
            action="CREATE",
            user=user,
            organization=retail,
            entity_type="stock_order",
            entity_id=str(order.pk),
            request=self.request,
        )

    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        order = self.get_object()
        if order.status != StockOrder.Status.DRAFT:
            raise ValidationError("Only draft orders can be submitted.")
        order.status = StockOrder.Status.PENDING
        order.save(update_fields=["status", "updated_at"])
        record_audit(
            action="SUBMIT",
            user=cast(User, request.user),
            organization=order.retail,
            entity_type="stock_order",
            entity_id=str(order.pk),
            request=request,
        )
        return Response(StockOrderSerializer(order).data)

    def _require_depot_admin(self, request: Request, order: StockOrder) -> User:
        user = cast(User, request.user)
        is_depot_admin = (
            user.is_superuser
            or user.has_role("SYS_ADMIN")
            or (user.has_role("ORG_ADMIN") and user.organization_id == order.depot_id)
        )
        if not is_depot_admin:
            raise PermissionDenied("Only the depot can perform this action.")
        return user

    def _require_retail_admin(self, request: Request, order: StockOrder) -> User:
        user = cast(User, request.user)
        is_retail_admin = (
            user.is_superuser
            or user.has_role("SYS_ADMIN")
            or (user.has_role("ORG_ADMIN") and user.organization_id == order.retail_id)
        )
        if not is_retail_admin:
            raise PermissionDenied("Only the receiving pharmacy can perform this action.")
        return user

    @action(detail=True, methods=["post"])
    def receive(self, request: Request, pk: str | None = None) -> Response:
        """Retail opens a GRN for an in-transit order, pre-filled from the manifest."""
        order = self.get_object()
        user = self._require_retail_admin(request, order)
        if order.status != StockOrder.Status.IN_TRANSIT:
            raise ValidationError("Only in-transit orders can be received.")
        grn = open_grn(order=order, user=user)
        record_audit(
            action="GRN_OPEN",
            user=user,
            organization=order.retail,
            entity_type="grn",
            entity_id=str(grn.pk),
            request=request,
        )
        return Response(GRNSerializer(grn).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        """Depot approves a pending order and FEFO-reserves depot stock against it."""
        order = self.get_object()
        user = self._require_depot_admin(request, order)
        if order.status != StockOrder.Status.PENDING:
            raise ValidationError("Only pending orders can be approved.")
        approve_and_allocate(order=order, user=user)
        record_audit(
            action="APPROVE",
            user=user,
            organization=order.depot,
            entity_type="stock_order",
            entity_id=str(order.pk),
            request=request,
        )
        order.refresh_from_db()
        return Response(StockOrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def pick(self, request: Request, pk: str | None = None) -> Response:
        """Depot begins picking an approved order (APPROVED → PICKING)."""
        order = self.get_object()
        user = self._require_depot_admin(request, order)
        if order.status != StockOrder.Status.APPROVED:
            raise ValidationError("Only approved orders can be picked.")
        order.status = StockOrder.Status.PICKING
        order.save(update_fields=["status", "updated_at"])
        record_audit(
            action="PICK",
            user=user,
            organization=order.depot,
            entity_type="stock_order",
            entity_id=str(order.pk),
            request=request,
        )
        return Response(StockOrderSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="dispatch")
    def ship(self, request: Request, pk: str | None = None) -> Response:
        """Depot dispatches a picked order (PICKING → IN_TRANSIT): stock leaves the depot."""
        order = self.get_object()
        user = self._require_depot_admin(request, order)
        if order.status != StockOrder.Status.PICKING:
            raise ValidationError("Only orders being picked can be dispatched.")
        dispatch_order(
            order=order,
            driver_name=str(request.data.get("driver_name", "")),
            vehicle_registration=str(request.data.get("vehicle_registration", "")),
            user=user,
        )
        record_audit(
            action="DISPATCH",
            user=user,
            organization=order.depot,
            entity_type="stock_order",
            entity_id=str(order.pk),
            request=request,
        )
        order.refresh_from_db()
        return Response(StockOrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        order = self.get_object()
        cancellable = {
            StockOrder.Status.DRAFT,
            StockOrder.Status.PENDING,
            StockOrder.Status.APPROVED,
            StockOrder.Status.PICKING,
        }
        if order.status not in cancellable:
            raise ValidationError("This order can no longer be cancelled.")
        # Release any depot stock this order was holding.
        if order.reservations.exists():
            release_order_reservations(order=order)
        order.status = StockOrder.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])
        record_audit(
            action="CANCEL",
            user=cast(User, request.user),
            organization=order.retail,
            entity_type="stock_order",
            entity_id=str(order.pk),
            request=request,
        )
        return Response(StockOrderSerializer(order).data)


class GRNViewSet(viewsets.ReadOnlyModelViewSet):
    """Goods Received Notes — read, plus a finalize action (retail side)."""

    serializer_class = GRNSerializer
    queryset = GoodsReceivedNote.objects.select_related("order", "retail").prefetch_related("lines")

    def get_queryset(self) -> QuerySet[GoodsReceivedNote]:
        user = cast(User, self.request.user)
        qs = GoodsReceivedNote.objects.select_related("order", "retail").prefetch_related("lines")
        if user.is_superuser or user.has_role("SYS_ADMIN"):
            return qs
        visible = organizations_visible_to(user)
        return qs.filter(Q(retail__in=visible) | Q(order__depot__in=visible))

    @action(detail=True, methods=["post"])
    def finalize(self, request: Request, pk: str | None = None) -> Response:
        """Finalize a GRN: write good stock into retail inventory and close the order."""
        grn = self.get_object()
        user = cast(User, request.user)
        is_retail_admin = (
            user.is_superuser
            or user.has_role("SYS_ADMIN")
            or (user.has_role("ORG_ADMIN") and user.organization_id == grn.retail_id)
        )
        if not is_retail_admin:
            raise PermissionDenied("Only the receiving pharmacy can finalize this GRN.")
        if grn.status != GoodsReceivedNote.Status.DRAFT:
            raise ValidationError("This GRN is already finalized.")

        lines_data: dict[int, dict[str, object]] = {}
        for row in request.data.get("lines", []):
            if isinstance(row, dict) and "id" in row:
                lines_data[int(row["id"])] = row
        finalize_grn(grn=grn, lines_data=lines_data, user=user)
        record_audit(
            action="GRN_FINALIZE",
            user=user,
            organization=grn.retail,
            entity_type="grn",
            entity_id=str(grn.pk),
            request=request,
        )
        grn.refresh_from_db()
        return Response(GRNSerializer(grn).data)
