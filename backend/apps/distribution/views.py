"""Distribution API: B2B purchase orders (retail → depot)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.distribution.models import (
    CustomerReturn,
    DepotProductListing,
    GoodsReceivedNote,
    InTransitStock,
    JourneyPlan,
    SalesRepresentative,
    SalesVisitLog,
    StockOrder,
    TenderContract,
)
from apps.distribution.serializers import (
    CustomerReturnSerializer,
    DepotProductListingSerializer,
    GRNSerializer,
    InTransitStockSerializer,
    JourneyPlanSerializer,
    SalesRepresentativeSerializer,
    SalesVisitLogSerializer,
    StockOrderSerializer,
    TenderContractSerializer,
)
from apps.distribution.services import (
    approve_and_ship,
    generate_po_document,
    receive_all,
    record_order_payment,
    release_order_reservations,
)
from apps.finance.services import (
    CreditHoldError,
    assert_may_order_on_credit,
    post_payment_journal,
)
from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to
from apps.workspace.notify import notify_org_admins


class CreditHoldConflict(APIException):
    """409, not 400: the order is well-formed — the buyer's credit standing is
    what refuses it, and it will succeed unchanged once the account is cleared."""

    status_code = 409
    default_detail = "The buyer's credit standing blocks this order."
    default_code = "credit_hold"


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
        # A status filter was being sent by the overview and silently ignored, so
        # the "pending approval" count was really the total order count. An ignored
        # filter is worse than a rejected one — the number looks plausible.
        status = self.request.query_params.get("status")
        if status:
            valid = {choice.value for choice in StockOrder.Status}
            if status not in valid:
                raise ValidationError({"status": f"Must be one of {sorted(valid)}."})
            qs = qs.filter(status=status)
        payment_status = self.request.query_params.get("payment_status")
        if payment_status:
            valid = {choice.value for choice in StockOrder.PaymentStatus}
            if payment_status not in valid:
                raise ValidationError({"payment_status": f"Must be one of {sorted(valid)}."})
            qs = qs.filter(payment_status=payment_status)
        for key, field in (("depot", "depot_id"), ("retail", "retail_id")):
            raw = self.request.query_params.get(key)
            if raw and raw.isdigit():
                qs = qs.filter(**{field: int(raw)})
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        user = cast(User, self.request.user)
        retail = serializer.validated_data["retail"]
        is_admin = user.is_superuser or user.has_role("SYS_ADMIN") or user.has_role("ORG_ADMIN")
        if not is_admin and user.organization_id != retail.pk:
            raise PermissionDenied("You can only create orders for your own organization.")
        if not serializer.validated_data.get("items"):
            raise ValidationError("An order needs at least one item.")
        depot = serializer.validated_data["depot"]
        # Cheap refusals first — hold and overdue need no line prices, so a blocked
        # buyer never touches the database.
        try:
            assert_may_order_on_credit(seller=depot, buyer=retail)
        except CreditHoldError as exc:
            raise CreditHoldConflict(str(exc)) from exc
        try:
            with transaction.atomic():
                # order_number is stamped inside the serializer's atomic create().
                order = serializer.save(ordered_by=user, status=StockOrder.Status.DRAFT)
                # Lines are priced by the depot during create(), so the exposure
                # check can only run once the order exists. The rollback undoes it.
                assert_may_order_on_credit(
                    seller=order.depot,
                    buyer=order.retail,
                    order_amount=Decimal(str(order.total_amount)),
                )
        except CreditHoldError as exc:
            raise CreditHoldConflict(str(exc)) from exc
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
        # A draft can sit for days; re-check in case the account went on hold since.
        try:
            assert_may_order_on_credit(
                seller=order.depot,
                buyer=order.retail,
                order_amount=Decimal(str(order.total_amount)),
            )
        except CreditHoldError as exc:
            raise CreditHoldConflict(str(exc)) from exc
        order.status = StockOrder.Status.PENDING
        order.save(update_fields=["status", "updated_at"])
        generate_po_document(order=order, user=cast(User, request.user))
        notify_org_admins(
            organization=order.depot,
            title=f"New order {order.order_number} from {order.retail.name}",
            body="Awaiting your approval.",
            link_entity_type="stock_order",
            link_entity_id=str(order.pk),
        )
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
        notify_org_admins(
            organization=order.retail,
            title=f"Order {order.order_number} approved & shipped",
            body=f"On the way from {order.depot.name}.",
            link_entity_type="stock_order",
            link_entity_id=str(order.pk),
        )
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
        notify_org_admins(
            organization=order.depot,
            title=f"Order {order.order_number} received by {order.retail.name}",
            link_entity_type="stock_order",
            link_entity_id=str(order.pk),
        )
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
        # Auto-post the settlement to both parties' books (see docs/06 §9, ROADMAP "9. Finance").
        post_payment_journal(
            order=order, amount=Decimal(str(request.data.get("amount", 0))), user=user
        )
        # Notify the other party (the one who didn't record it).
        counterpart = order.depot if user.organization_id == order.retail_id else order.retail
        notify_org_admins(
            organization=counterpart,
            title=f"Payment recorded on {order.order_number}",
            body=f"Amount due is now {order.amount_due:,.0f}.",
            link_entity_type="stock_order",
            link_entity_id=str(order.pk),
            exclude_user_id=user.pk,
        )
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


class DepotProductListingViewSet(viewsets.ModelViewSet):
    serializer_class = DepotProductListingSerializer
    queryset = DepotProductListing.objects.select_related("depot", "product")

    def get_queryset(self) -> QuerySet[DepotProductListing]:
        user = cast(User, self.request.user)
        qs = DepotProductListing.objects.select_related("depot", "product")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(depot__in=visible)
        return qs


class SalesRepresentativeViewSet(viewsets.ModelViewSet):
    serializer_class = SalesRepresentativeSerializer
    queryset = SalesRepresentative.objects.select_related("organization", "user", "employee")

    def get_queryset(self) -> QuerySet[SalesRepresentative]:
        user = cast(User, self.request.user)
        qs = SalesRepresentative.objects.select_related("organization", "user", "employee")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(organization__in=visible)
        return qs


class JourneyPlanViewSet(viewsets.ModelViewSet):
    serializer_class = JourneyPlanSerializer
    queryset = JourneyPlan.objects.select_related("rep", "customer_org")

    def get_queryset(self) -> QuerySet[JourneyPlan]:
        user = cast(User, self.request.user)
        qs = JourneyPlan.objects.select_related("rep", "customer_org")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(rep__organization__in=visible)
        return qs


class SalesVisitLogViewSet(viewsets.ModelViewSet):
    serializer_class = SalesVisitLogSerializer
    queryset = SalesVisitLog.objects.select_related("rep", "customer_org", "order")

    def get_queryset(self) -> QuerySet[SalesVisitLog]:
        user = cast(User, self.request.user)
        qs = SalesVisitLog.objects.select_related("rep", "customer_org", "order")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(rep__organization__in=visible)
        return qs


class TenderContractViewSet(viewsets.ModelViewSet):
    serializer_class = TenderContractSerializer
    queryset = TenderContract.objects.select_related("depot", "client_org", "product")

    def get_queryset(self) -> QuerySet[TenderContract]:
        user = cast(User, self.request.user)
        qs = TenderContract.objects.select_related("depot", "client_org", "product")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(Q(depot__in=visible) | Q(client_org__in=visible))
        return qs


class CustomerReturnViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerReturnSerializer
    queryset = CustomerReturn.objects.select_related("depot", "retail")

    def get_queryset(self) -> QuerySet[CustomerReturn]:
        user = cast(User, self.request.user)
        qs = CustomerReturn.objects.select_related("depot", "retail")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(Q(depot__in=visible) | Q(retail__in=visible))
        return qs
