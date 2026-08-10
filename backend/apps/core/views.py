"""Health & readiness endpoints (Phase 0 walking skeleton) + operational dashboard."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, cast

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import insights
from apps.distribution.models import InTransitStock, StockOrder
from apps.iam.models import License, User
from apps.iam.scoping import organizations_visible_to
from apps.inventory.models import InventoryBatch, PharmacyProduct
from apps.retail.models import Sale


class PharmacyDayView(APIView):
    """The morning briefing for a pharmacy that is one or two people.

    Composed rather than assembled by the client: a small pharmacy's home
    screen was otherwise seven separate requests, each of which could arrive
    late or fail on its own, producing a page that filled in raggedly and
    sometimes disagreed with itself about the date.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.core.pharmacy_day import pharmacy_day

        return Response(pharmacy_day(cast(User, request.user)))


class MoneyCentreView(APIView):
    """Where the pharmacy's money is — takings, debts both ways, and cash."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.core.money_centre import money_centre

        return Response(money_centre(cast(User, request.user)))


class PharmacyPerformanceView(APIView):
    """How the pharmacy is doing, in the words an owner would use."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.core.pharmacy_performance import pharmacy_performance

        return Response(pharmacy_performance(cast(User, request.user)))


class PharmacySetupView(APIView):
    """The four questions that decide what this pharmacy is shown.

    Only an administrator answers them: the answers change what every user of
    the organisation sees, and whether the till charges VAT.
    """

    permission_classes = [IsAuthenticated]

    def _organization(self, request: Request) -> Any:
        user = cast(User, request.user)
        organization = user.organization
        if organization is None:
            raise ValidationError("You are not attached to a pharmacy.")
        if not (user.is_superuser or user.has_role("SYS_ADMIN") or user.has_role("ORG_ADMIN")):
            raise PermissionDenied(
                "Setting up the pharmacy is limited to administrators — the answers "
                "change what everyone here sees."
            )
        return organization

    def get(self, request: Request) -> Response:
        from apps.core.setup import setup_state

        return Response(setup_state(self._organization(request)))

    def post(self, request: Request) -> Response:
        from apps.core.setup import SetupError, apply_setup, setup_state

        organization = self._organization(request)
        try:
            apply_setup(
                organization=organization,
                headcount=str(request.data.get("headcount", "")),
                branches=int(request.data.get("branches", 1) or 1),
                manages=list(request.data.get("manages") or []),
                vat_registered=bool(request.data.get("vat_registered")),
                vat_registration_no=str(request.data.get("vat_registration_no", "")),
            )
        except SetupError as exc:
            raise ValidationError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Those answers could not be read: {exc}") from exc
        return Response(setup_state(organization))


class HealthView(APIView):
    """Liveness probe — confirms the API is up."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response(
            {
                "status": "ok",
                "service": "PharmaCore API",
                "version": settings.VERSION,
                "environment": settings.MEDLINK_ENV,
            }
        )


class DashboardView(APIView):
    """Operational summary scoped to the orgs the user can see — the home screen.

    Everything a manager needs to start the day: today's sales, stock that needs
    reordering, stock expiring/expired, orders to approve or receive, units in
    transit, money owed both ways, and licences about to lapse.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        orgs = organizations_visible_to(user)
        org_ids = list(orgs.values_list("id", flat=True))
        today = timezone.localdate()
        soon = today + timedelta(days=90)

        # Sales completed today (Sale.total is computed, so sum in Python — today's
        # set is small).
        todays = Sale.objects.filter(
            organization_id__in=org_ids,
            status=Sale.Status.COMPLETED,
            completed_at__date=today,
        ).prefetch_related("items")
        sales_total = sum((s.total for s in todays), Decimal("0"))

        # Low stock: sellable on-hand below the listing's min level.
        on_hand: dict[tuple[int, int], int] = {}
        for row in (
            InventoryBatch.objects.filter(
                organization_id__in=org_ids,
                status=InventoryBatch.Status.ACTIVE,
                expiry_date__gte=today,
            )
            .values("organization_id", "product_id")
            .annotate(qty=Sum("quantity_available"))
        ):
            on_hand[(row["organization_id"], row["product_id"])] = row["qty"] or 0
        low_stock = []
        for pp in PharmacyProduct.objects.filter(
            organization_id__in=org_ids, is_active=True, min_stock_level__gt=0
        ).select_related("product", "organization"):
            have = on_hand.get((pp.organization_id, pp.product_id), 0)
            if have < pp.min_stock_level:
                low_stock.append(
                    {
                        "product": f"{pp.product.generic_name} {pp.product.strength}".strip(),
                        "organization": pp.organization.name,
                        "on_hand": have,
                        "min": pp.min_stock_level,
                    }
                )

        expiring = InventoryBatch.objects.filter(
            organization_id__in=org_ids,
            status=InventoryBatch.Status.ACTIVE,
            expiry_date__gte=today,
            expiry_date__lte=soon,
            quantity_available__gt=0,
        )
        expired = InventoryBatch.objects.filter(
            organization_id__in=org_ids,
            expiry_date__lt=today,
            quantity_available__gt=0,
        )

        pending_approvals = StockOrder.objects.filter(
            depot_id__in=org_ids, status=StockOrder.Status.PENDING
        ).count()
        awaiting_receipt = StockOrder.objects.filter(
            retail_id__in=org_ids, status=StockOrder.Status.IN_TRANSIT
        ).count()

        # Money owed both ways (amount_due is computed → sum in Python over unpaid).
        receivable = sum(
            (
                Decimal(str(o.amount_due))
                for o in StockOrder.objects.filter(depot_id__in=org_ids)
                .exclude(payment_status=StockOrder.PaymentStatus.PAID)
                .prefetch_related("items")
            ),
            Decimal("0"),
        )
        payable = sum(
            (
                Decimal(str(o.amount_due))
                for o in StockOrder.objects.filter(retail_id__in=org_ids)
                .exclude(payment_status=StockOrder.PaymentStatus.PAID)
                .prefetch_related("items")
            ),
            Decimal("0"),
        )

        in_transit_units = (
            InTransitStock.objects.filter(destination_org_id__in=org_ids).aggregate(
                q=Sum("quantity")
            )["q"]
            or 0
        )
        licences_expiring = License.objects.filter(
            organization_id__in=org_ids,
            expiry_date__isnull=False,
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=60),
        ).count()

        return Response(
            {
                "sales_today": {"count": todays.count(), "total": float(sales_total)},
                "low_stock": {"count": len(low_stock), "items": low_stock[:8]},
                "expiring_soon": {
                    "count": expiring.count(),
                    "units": expiring.aggregate(q=Sum("quantity_available"))["q"] or 0,
                },
                "expired": {
                    "count": expired.count(),
                    "units": expired.aggregate(q=Sum("quantity_available"))["q"] or 0,
                },
                "pending_approvals": pending_approvals,
                "awaiting_receipt": awaiting_receipt,
                "in_transit_units": in_transit_units,
                "receivable_due": float(receivable),
                "payable_due": float(payable),
                "licences_expiring": licences_expiring,
                "org_count": len(org_ids),
                # A single summed total told a group owner with four pharmacies
                # nothing about which one earned it, and "today" with nothing to
                # compare against told them nothing at all. See apps/core/insights.py.
                **insights.performance(org_ids=org_ids),
                "expiry_exposure": insights.expiry_exposure(org_ids=org_ids),
            }
        )


class RootView(APIView):
    """Root banner."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        data: dict[str, Any] = {
            "service": "PharmaCore API",
            "version": settings.VERSION,
            "docs": "/api/docs/",
        }
        return Response(data)
