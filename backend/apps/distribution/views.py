"""Distribution API: B2B purchase orders (retail → depot)."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import Q, QuerySet
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.distribution.models import StockOrder
from apps.distribution.serializers import StockOrderSerializer
from apps.distribution.services import approve_and_allocate, release_order_reservations
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

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        """Depot approves a pending order and FEFO-reserves depot stock against it."""
        order = self.get_object()
        user = cast(User, request.user)
        is_depot_admin = (
            user.is_superuser
            or user.has_role("SYS_ADMIN")
            or (user.has_role("ORG_ADMIN") and user.organization_id == order.depot_id)
        )
        if not is_depot_admin:
            raise PermissionDenied("Only the depot can approve this order.")
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
