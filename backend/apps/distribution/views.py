"""Distribution API: B2B purchase orders (retail → depot)."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.distribution.models import GoodsReceivedNote, InTransitStock, StockOrder
from apps.distribution.serializers import (
    GRNSerializer,
    InTransitStockSerializer,
    StockOrderSerializer,
)
from apps.distribution.services import (
    approve_and_ship,
    generate_po_document,
    receive_all,
    record_order_payment,
    release_order_reservations,
)
from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to


def _age_bucket(due, today) -> str:  # type: ignore[no-untyped-def]
    days = (today - due).days
    if days <= 0:
        return "current"
    if days <= 30:
        return "d30"
    if days <= 60:
        return "d60"
    if days <= 90:
        return "d90"
    return "over90"


class AgingView(APIView):
    """Aged receivables (owed to you) and payables (you owe) across visible orgs,
    bucketed by how overdue each unpaid order is, and grouped by trading partner."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        visible_ids = set(organizations_visible_to(user).values_list("id", flat=True))
        today = timezone.now().date()
        empty = {"current": 0.0, "d30": 0.0, "d60": 0.0, "d90": 0.0, "over90": 0.0}

        def side(orders: QuerySet[StockOrder], partner_attr: str) -> dict[str, Any]:
            buckets = dict(empty)
            by_partner: dict[str, dict[str, Any]] = {}
            total = 0.0
            for o in (
                orders.exclude(payment_status=StockOrder.PaymentStatus.PAID)
                .select_related("depot", "retail")
                .prefetch_related("items")
            ):
                due = o.amount_due
                if due <= 0:
                    continue
                bucket = _age_bucket(o.payment_due_date or o.created_at.date(), today)
                buckets[bucket] += due
                total += due
                partner = getattr(o, partner_attr)
                row = by_partner.setdefault(
                    partner.name, {"partner": partner.name, "total": 0.0, **dict(empty)}
                )
                row["total"] += due
                row[bucket] += due
            return {
                "total": total,
                "buckets": buckets,
                "by_partner": sorted(by_partner.values(), key=lambda r: -r["total"]),
            }

        receivables = side(StockOrder.objects.filter(depot_id__in=visible_ids), "retail")
        payables = side(StockOrder.objects.filter(retail_id__in=visible_ids), "depot")
        return Response({"receivables": receivables, "payables": payables})


class StockOrderViewSet(viewsets.ModelViewSet):
    """Purchase orders. A retail org creates orders to a depot; both parties see them.

    Scoping: SYS_ADMIN sees all; others see orders where their org is the depot or
    the retail party. Create is limited to your own retail org (admins: any).
    """

    serializer_class = StockOrderSerializer
    queryset = StockOrder.objects.select_related("depot", "retail").prefetch_related(
        "items", "shipments", "order_payments", "in_transit"
    )
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[StockOrder]:
        user = cast(User, self.request.user)
        qs = StockOrder.objects.select_related("depot", "retail").prefetch_related(
            "items", "shipments", "order_payments", "in_transit"
        )
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
        generate_po_document(order=order, user=cast(User, request.user))
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
    def approve(self, request: Request, pk: str | None = None) -> Response:
        """Depot approves a pending order — and the stock leaves in the same step.

        Lean flow: approve FEFO-reserves and immediately dispatches, so the order
        goes PENDING → IN_TRANSIT. No separate picking or driver step.
        """
        order = self.get_object()
        user = self._require_depot_admin(request, order)
        if order.status != StockOrder.Status.PENDING:
            raise ValidationError("Only pending orders can be approved.")
        approve_and_ship(order=order, user=user)
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
    def receive(self, request: Request, pk: str | None = None) -> Response:
        """Pharmacy confirms the goods arrived; stock lands in one click.

        Lean flow: opens and finalizes the GRN as fully received, so the order
        goes IN_TRANSIT → DELIVERED and the stock (with all product details) is
        added to the pharmacy's inventory and catalog — nothing is re-entered.
        """
        order = self.get_object()
        user = self._require_retail_admin(request, order)
        if order.status != StockOrder.Status.IN_TRANSIT:
            raise ValidationError("Only in-transit orders can be received.")
        receive_all(order=order, user=user)
        record_audit(
            action="RECEIVE",
            user=user,
            organization=order.retail,
            entity_type="stock_order",
            entity_id=str(order.pk),
            request=request,
        )
        order.refresh_from_db()
        return Response(StockOrderSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request: Request, pk: str | None = None) -> Response:
        """Record a payment the pharmacy made to the wholesaler for this order.

        Either party (buyer or seller) may record it; the order's settlement status
        rolls up to UNPAID / PARTIAL / PAID.
        """
        order = self.get_object()
        user = cast(User, request.user)
        is_party = (
            user.is_superuser
            or user.has_role("SYS_ADMIN")
            or user.organization_id in (order.depot_id, order.retail_id)
        )
        if not is_party:
            raise PermissionDenied("Only the buyer or the wholesaler can record a payment.")
        try:
            record_order_payment(
                order=order,
                amount=request.data.get("amount", 0),
                method=str(request.data.get("method", "BANK_TRANSFER")),
                reference=str(request.data.get("reference", "")),
                user=user,
            )
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="PAYMENT",
            user=user,
            organization=order.retail,
            entity_type="stock_order",
            entity_id=str(order.pk),
            changes={"amount": str(request.data.get("amount", 0))},
            request=request,
        )
        order.refresh_from_db()
        return Response(StockOrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        order = self.get_object()
        # Only cancellable before the depot approves & ships it.
        cancellable = {StockOrder.Status.DRAFT, StockOrder.Status.PENDING}
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


class InTransitStockViewSet(viewsets.ReadOnlyModelViewSet):
    """Live view of stock on trucks — units dispatched but not yet received.

    Scoped to orgs the user can see; filter with ?destination=<org> ('what's coming
    to me') or ?source=<org> ('what I've sent out').
    """

    serializer_class = InTransitStockSerializer
    queryset = InTransitStock.objects.select_related(
        "order", "source_org", "destination_org", "product"
    )

    def get_queryset(self) -> QuerySet[InTransitStock]:
        user = cast(User, self.request.user)
        qs = InTransitStock.objects.select_related(
            "order", "source_org", "destination_org", "product"
        )
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(Q(source_org__in=visible) | Q(destination_org__in=visible))
        dest = self.request.query_params.get("destination")
        if dest and dest.isdigit():
            qs = qs.filter(destination_org_id=int(dest))
        src = self.request.query_params.get("source")
        if src and src.isdigit():
            qs = qs.filter(source_org_id=int(src))
        return qs


class GRNViewSet(viewsets.ReadOnlyModelViewSet):
    """Goods Received Notes — read-only record of what a pharmacy received.

    Reception itself happens in one click via the order's ``receive`` action
    (lean flow); this viewset just exposes the resulting GRN records.
    """

    serializer_class = GRNSerializer
    queryset = GoodsReceivedNote.objects.select_related("order", "retail").prefetch_related("lines")

    def get_queryset(self) -> QuerySet[GoodsReceivedNote]:
        user = cast(User, self.request.user)
        qs = GoodsReceivedNote.objects.select_related("order", "retail").prefetch_related("lines")
        if user.is_superuser or user.has_role("SYS_ADMIN"):
            return qs
        visible = organizations_visible_to(user)
        return qs.filter(Q(retail__in=visible) | Q(order__depot__in=visible))
