"""Marketplace API: the storefront, unmet demand, returns and van sales.

The storefront is deliberately asymmetric. A buyer sees what a depot chose to
offer; the depot additionally sees what it is holding back and where it has
published more than it can deliver. Both come from the same engine, so the two
views can never drift apart.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.distribution import demand as demand_engine
from apps.distribution import fieldsales, marketplace, returns
from apps.distribution.models import (
    BackorderLine,
    CustomerReturn,
    CustomerReturnLine,
    SalesRepresentative,
    VanStock,
    VanStockMovement,
)
from apps.distribution.permissions import DistributionAccess
from apps.distribution.serializers import (
    BackorderLineSerializer,
    DepotProductListingSerializer,
    VanStockMovementSerializer,
    VanStockSerializer,
)
from apps.iam.models import Organization, User
from apps.iam.scoping import organizations_visible_to


def _org_param(request: Request, key: str = "organization") -> int:
    raw = request.query_params.get(key) or request.data.get(key)
    if not raw:
        user = cast(User, request.user)
        if user.organization_id:
            return int(user.organization_id)
        raise ValidationError({key: "This query needs an organization."})
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({key: "Must be an organization id."}) from exc


def _optional_org(request: Request, key: str) -> int | None:
    """Parse an optional organization id from the query string.

    A caller that stringifies a null — ``?buyer=None``, ``?buyer=`` — is asking a
    question about no buyer at all, not about an organization named "None". That
    must read as absent rather than reaching the ORM and raising.
    """
    raw = request.query_params.get(key)
    if raw is None or raw.strip().lower() in ("", "none", "null", "undefined"):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({key: "Must be an organization id."}) from exc


def _assert_may_act_for(user: User, org_id: int) -> None:
    if user.is_superuser or user.has_role("SYS_ADMIN"):
        return
    if not organizations_visible_to(user).filter(pk=org_id).exists():
        raise PermissionDenied("You cannot act for that organization.")


# ---------------------------------------------------------------------------
# Storefront
# ---------------------------------------------------------------------------


class StorefrontView(APIView):
    """What a buyer may order from a depot right now.

    ``?as_depot=1`` switches to the seller's view, which additionally reports
    withheld listings and anything published beyond what is physically sellable.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        depot_id = _org_param(request, "depot")
        as_depot = request.query_params.get("as_depot") in ("1", "true", "True")
        if as_depot:
            _assert_may_act_for(user, depot_id)

        buyer = _optional_org(request, "buyer")
        if buyer is None and not as_depot:
            buyer = user.organization_id

        rows = marketplace.storefront(depot=depot_id, buyer=buyer, include_unlisted=as_depot)
        payload = [
            {
                "listing": r.listing.pk,
                "product": r.listing.product_id,
                "product_name": str(r.listing.product),
                "price": str(r.price),
                "available": r.available,
                "offered_qty": r.listing.offered_qty,
                "min_order_qty": r.listing.min_order_qty,
                "customer_segment": r.listing.customer_segment,
                "is_published": r.listing.is_published,
                # Only ever populated in the depot's own view.
                "stock_on_hand": r.physical_free if r.show_stock_detail else None,
            }
            for r in rows
        ]
        body: dict[str, Any] = {"depot": depot_id, "rows": payload, "count": len(payload)}
        if as_depot:
            body["coverage"] = marketplace.coverage(depot=depot_id)
        return Response(body)


class AvailabilityView(APIView):
    """Resolve one product's availability and price for one buyer.

    The ordering screen calls this before it lets a line be added, so a buyer is
    told what they can have *before* they commit, rather than after.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        depot_id = _org_param(request, "depot")
        raw_product = request.query_params.get("product")
        if not raw_product:
            raise ValidationError({"product": "Required."})
        try:
            product_id = int(raw_product)
        except (TypeError, ValueError) as exc:
            raise ValidationError({"product": "Must be a product id."}) from exc
        buyer_id = _optional_org(request, "buyer") or user.organization_id

        avail = marketplace.availability(depot=depot_id, product=product_id, buyer=buyer_id)
        contract = marketplace.active_contract(depot=depot_id, product=product_id, buyer=buyer_id)
        return Response(
            {
                "depot": depot_id,
                "product": product_id,
                "available": avail.available,
                "price": str(avail.price),
                "min_order_qty": avail.min_order_qty,
                "is_listed": avail.is_listed,
                "is_orderable": avail.is_orderable,
                "reason": avail.reason,
                "can_backorder": True,
                "tender": (
                    {
                        "number": contract.tender_number,
                        "price": str(contract.contract_price),
                        "remaining": contract.total_committed_qty - contract.drawn_qty,
                        "valid_until": contract.valid_until,
                    }
                    if contract
                    else None
                ),
            }
        )


class PublishListingView(APIView):
    """Create or update what a depot offers — including withdrawing it from sale."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        depot_id = _org_param(request, "depot")
        _assert_may_act_for(user, depot_id)

        product = request.data.get("product")
        if not product:
            raise ValidationError({"product": "Required."})
        try:
            price = Decimal(str(request.data.get("price_per_unit", "0")))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"price_per_unit": "Must be a number."}) from exc

        listing = marketplace.publish(
            depot=depot_id,
            product=int(product),
            offered_qty=int(request.data.get("offered_qty", 0)),
            price_per_unit=price,
            buffer_qty=int(request.data.get("buffer_qty", 0)),
            min_order_qty=int(request.data.get("min_order_qty", 1)),
            customer_segment=request.data.get("customer_segment", "ALL"),
            is_published=bool(request.data.get("is_published", True)),
        )
        return Response(
            DepotProductListingSerializer(listing, context={"request": request}).data,
            status=201,
        )


# ---------------------------------------------------------------------------
# Demand
# ---------------------------------------------------------------------------


class BackorderViewSet(viewsets.ReadOnlyModelViewSet):
    """Unmet demand — read-only here; it is created by the ordering flow."""

    permission_classes = [IsAuthenticated, DistributionAccess]

    serializer_class = BackorderLineSerializer
    queryset = BackorderLine.objects.select_related("depot", "retail", "product", "order")

    def get_queryset(self) -> QuerySet[BackorderLine]:
        user = cast(User, self.request.user)
        qs = BackorderLine.objects.select_related("depot", "retail", "product", "order")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(Q(depot__in=visible) | Q(retail__in=visible))
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        depot = self.request.query_params.get("depot")
        if depot:
            qs = qs.filter(depot_id=int(depot))
        return qs

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        line = self.get_object()
        _assert_may_act_for(cast(User, request.user), line.depot_id)
        try:
            demand_engine.cancel_backorder(line=line, reason=request.data.get("reason", ""))
        except demand_engine.DemandError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(BackorderLineSerializer(line).data)


class DemandBoardView(APIView):
    """Aggregated demand at a depot — the import shopping list."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        depot_id = _org_param(request, "depot")
        _assert_may_act_for(user, depot_id)
        board = demand_engine.demand_board(depot=depot_id)
        return Response(
            {
                "depot": depot_id,
                "summary": demand_engine.summary(depot=depot_id),
                "rows": [
                    {
                        "product": r.product_id,
                        "product_name": r.product_name,
                        "quantity": r.quantity,
                        "buyers": r.buyers,
                        "lines": r.lines,
                        "sourcing": r.sourcing,
                        "age_days": r.age_days,
                        "oldest": r.oldest,
                    }
                    for r in board
                ],
            }
        )


class SourceDemandView(APIView):
    """Turn open demand into a purchase requisition and hand it to procurement."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        depot_id = _org_param(request, "depot")
        _assert_may_act_for(user, depot_id)

        raw_products = request.data.get("products") or []
        needed_raw = request.data.get("needed_by")
        needed_by = (
            date.fromisoformat(needed_raw)
            if needed_raw
            else timezone.localdate() + timedelta(days=30)
        )

        try:
            requisition = demand_engine.raise_requisition_from_demand(
                depot=depot_id,
                product_ids=[int(p) for p in raw_products] or None,
                user=user,
                needed_by=needed_by,
                justification=request.data.get("justification", ""),
            )
        except demand_engine.DemandError as exc:
            raise ValidationError(str(exc)) from exc

        return Response(
            {
                "requisition": requisition.pk,
                "requisition_number": requisition.requisition_number,
                "status": requisition.status,
                "lines": [
                    {
                        "product": ln.product_id,
                        "product_name": str(ln.product),
                        "quantity": ln.quantity,
                        "estimated_unit_cost": str(ln.estimated_unit_cost),
                    }
                    for ln in requisition.lines.select_related("product")
                ],
                "next": "Submit the requisition in Procurement to start the import.",
            },
            status=201,
        )


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------


class ReturnActionsView(APIView):
    """Inspect, approve or reject a customer return."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk: int, verb: str) -> Response:
        user = cast(User, request.user)
        return_request = get_object_or_404(
            CustomerReturn.objects.select_related("depot", "retail"), pk=pk
        )
        _assert_may_act_for(user, return_request.depot_id)

        try:
            if verb == "inspect":
                returns.start_inspection(return_request=return_request, user=user)
                for row in request.data.get("lines", []):
                    line = get_object_or_404(
                        CustomerReturnLine, pk=row["id"], return_request=return_request
                    )
                    returns.record_inspection(
                        line=line,
                        quantity_accepted=int(row.get("quantity_accepted", 0)),
                        quantity_rejected=int(row.get("quantity_rejected", 0)),
                        note=row.get("note", ""),
                    )
                return Response({"status": return_request.status})

            if verb == "approve":
                outcome = returns.approve_return(return_request=return_request, user=user)
                return Response(
                    {
                        "status": outcome.return_request.status,
                        "restocked_units": outcome.restocked_units,
                        "rejected_units": outcome.rejected_units,
                        "credit_amount": str(outcome.credit_amount),
                        "credit_note": outcome.credit_note.pk if outcome.credit_note else None,
                        "credit_note_number": (
                            outcome.credit_note.doc_number if outcome.credit_note else ""
                        ),
                    }
                )

            if verb == "reject":
                returns.reject_return(
                    return_request=return_request,
                    reason=request.data.get("reason", ""),
                    user=user,
                )
                return Response({"status": return_request.status})
        except returns.ReturnError as exc:
            raise ValidationError(str(exc)) from exc

        raise ValidationError(f"Unknown action '{verb}'.")


# ---------------------------------------------------------------------------
# Van sales
# ---------------------------------------------------------------------------


class VanStockViewSet(viewsets.ReadOnlyModelViewSet):
    """What is on each van. Quantities move only through the actions below."""

    permission_classes = [IsAuthenticated, DistributionAccess]

    serializer_class = VanStockSerializer
    queryset = VanStock.objects.select_related("rep", "rep__user", "product")

    def get_queryset(self) -> QuerySet[VanStock]:
        user = cast(User, self.request.user)
        qs = VanStock.objects.select_related("rep", "rep__user", "product")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(rep__organization__in=organizations_visible_to(user))
        rep = self.request.query_params.get("rep")
        if rep:
            qs = qs.filter(rep_id=int(rep))
        return qs


class VanActionsView(APIView):
    """Load, sell from, or return stock to the depot for a rep's van."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk: int, verb: str) -> Response:
        from apps.catalog.models import Product

        user = cast(User, request.user)
        rep = get_object_or_404(
            SalesRepresentative.objects.select_related("organization", "user"), pk=pk
        )
        _assert_may_act_for(user, rep.organization_id)

        product = get_object_or_404(Product, pk=request.data.get("product"))
        batch_number = request.data.get("batch_number", "")
        quantity = int(request.data.get("quantity", 0))

        try:
            if verb == "load":
                van = fieldsales.load_van(
                    rep=rep,
                    product=product,
                    batch_number=batch_number,
                    quantity=quantity,
                    user=user,
                )
            elif verb == "sell":
                van = fieldsales.sell_from_van(
                    rep=rep,
                    product=product,
                    batch_number=batch_number,
                    quantity=quantity,
                    reference=request.data.get("reference", ""),
                    user=user,
                )
            elif verb == "return":
                van = fieldsales.return_to_depot(
                    rep=rep,
                    product=product,
                    batch_number=batch_number,
                    quantity=quantity,
                    user=user,
                )
            else:
                raise ValidationError(f"Unknown van action '{verb}'.")
        except fieldsales.VanError as exc:
            raise ValidationError(str(exc)) from exc

        return Response(
            {
                "van": VanStockSerializer(van).data,
                "manifest": fieldsales.van_manifest(rep=rep),
            }
        )


class VanManifestView(APIView):
    """The van's current contents and whether it reconciles."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, pk: int) -> Response:
        rep = get_object_or_404(
            SalesRepresentative.objects.select_related("organization", "user"), pk=pk
        )
        _assert_may_act_for(cast(User, request.user), rep.organization_id)
        return Response(fieldsales.van_manifest(rep=rep))


class RepPerformanceView(APIView):
    """A rep's attainment and commission over a period."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        org_id = _org_param(request)
        _assert_may_act_for(user, org_id)

        today = timezone.localdate()
        start_raw = request.query_params.get("start")
        end_raw = request.query_params.get("end")
        start = date.fromisoformat(start_raw) if start_raw else today.replace(day=1)
        end = date.fromisoformat(end_raw) if end_raw else today

        rows = []
        for rep in SalesRepresentative.objects.filter(
            organization_id=org_id, is_active=True
        ).select_related("user"):
            perf = fieldsales.performance(rep=rep, start=start, end=end)
            rows.append(
                {
                    "rep": rep.pk,
                    "name": rep.user.get_full_name() or rep.user.username,
                    "territory": rep.territory_code,
                    "orders": perf.orders,
                    "revenue": str(perf.revenue),
                    "target": str(perf.target),
                    "attainment_pct": round(perf.attainment_pct, 1),
                    "commission": str(perf.commission),
                    "visits": perf.visits,
                    "visits_converted": perf.visits_converted,
                    "conversion_pct": round(perf.conversion_pct, 1),
                }
            )
        rows.sort(key=lambda r: float(str(r["revenue"])), reverse=True)
        return Response({"organization": org_id, "start": start, "end": end, "rows": rows})


class VanMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """The audit trail behind every van quantity."""

    permission_classes = [IsAuthenticated, DistributionAccess]

    serializer_class = VanStockMovementSerializer
    queryset = VanStockMovement.objects.select_related("rep", "product")

    def get_queryset(self) -> QuerySet[VanStockMovement]:
        user = cast(User, self.request.user)
        qs = VanStockMovement.objects.select_related("rep", "product")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(rep__organization__in=organizations_visible_to(user))
        rep = self.request.query_params.get("rep")
        if rep:
            qs = qs.filter(rep_id=int(rep))
        return qs


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


class DistributionOverviewView(APIView):
    """The distribution home: is the storefront healthy, and what is unmet."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        depot_id = _org_param(request, "depot")
        _assert_may_act_for(user, depot_id)
        return Response(
            {
                "depot": depot_id,
                "storefront": marketplace.coverage(depot=depot_id),
                "demand": demand_engine.summary(depot=depot_id),
                "returns": returns.summary(depot=depot_id),
            }
        )


class TradingPartnersView(APIView):
    """Who this organization may trade with — deliberately not the same question
    as which organizations it may *see*.

    ``organizations_visible_to`` governs data access: a branch sees its own orders
    and nobody else's, which is right. But a marketplace cannot run on that — to
    buy from a depot you must first be able to name it. Reusing the administrative
    scope for the buyer/seller pickers meant every dropdown was empty for everyone
    except a superuser, so no B2B order could be raised at all.

    This returns identity only — id, name, type — never anything about the other
    party's stock, orders or money. Enough to trade with them, nothing more.
    """

    permission_classes = [IsAuthenticated]

    #: Organization types that sell into the trade. Drawn from ``Organization.OrgType``
    #: rather than written out, because the literal list previously carried
    #: "DISTRIBUTOR" and "RETAIL_PHARMACY" — neither of which is a real org type, so
    #: neither could ever match. The behaviour was right by accident and the code
    #: stated something false about the domain.
    SELLER_TYPES = (Organization.OrgType.DEPOT, Organization.OrgType.HQ)
    #: Organization types that buy from it.
    BUYER_TYPES = (Organization.OrgType.RETAIL,)

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        role = (request.query_params.get("role") or "seller").lower()
        if role not in ("seller", "buyer"):
            raise ValidationError({"role": "Must be 'seller' or 'buyer'."})

        wanted = self.SELLER_TYPES if role == "seller" else self.BUYER_TYPES
        qs = Organization.objects.filter(type__in=wanted, is_active=True)
        # You are never your own trading partner.
        if user.organization_id:
            qs = qs.exclude(pk=user.organization_id)

        return Response(
            {
                "role": role,
                "results": [
                    {"id": o.pk, "name": o.name, "type": o.type, "district": o.district}
                    for o in qs.order_by("name")
                ],
            }
        )
