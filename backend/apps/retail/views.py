"""Retail POS API: over-the-counter sales at a pharmacy.

Org-scoped: a member of a pharmacy (cashier / pharmacist / org-admin) rings up
sales for that pharmacy; SYS_ADMIN sees all. Prices come from the pharmacy's own
listing; stock moves via the FEFO service. See apps/retail/services.py.
"""

from __future__ import annotations

from typing import Any, cast

from django.db.models import QuerySet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.iam.audit import record_audit
from apps.iam.models import Organization, User
from apps.iam.scoping import organizations_visible_to
from apps.retail.models import Dispensing, Sale
from apps.retail.serializers import DispensingSerializer, SaleSerializer
from apps.retail.services import (
    DispensingRequired,
    InsufficientStock,
    PharmacistRequired,
    complete_sale,
    void_sale,
)


def _is_admin(user: User) -> bool:
    return bool(user.is_superuser or user.has_role("SYS_ADMIN"))


def _require_org_member(user: User, org: Organization) -> None:
    """A user may operate the POS for their own pharmacy; admins for any."""
    if _is_admin(user):
        return
    if user.organization_id != org.pk:
        raise PermissionDenied("You can only sell for your own pharmacy.")


def _parse_payments(request: Request) -> list[dict[str, Any]]:
    raw = request.data.get("payments", [])
    payments: list[dict[str, Any]] = []
    for row in raw if isinstance(raw, list) else []:
        if isinstance(row, dict) and "method" in row and "amount" in row:
            payments.append({"method": row["method"], "amount": row["amount"]})
    return payments


class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    queryset = Sale.objects.select_related("organization", "cashier").prefetch_related(
        "items__product", "payments"
    )
    http_method_names = ["get", "post", "head", "options"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Sale]:
        user = cast(User, self.request.user)
        qs = Sale.objects.select_related("organization", "cashier").prefetch_related(
            "items__product", "payments"
        )
        if not _is_admin(user):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        org = self.request.query_params.get("organization")
        if org and org.isdigit():
            qs = qs.filter(organization_id=int(org))
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Ring up a sale. Creates an OPEN cart with prices snapshotted from the
        pharmacy's listing; if ``payments`` are supplied, completes it in one shot."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = cast(User, request.user)
        org = serializer.validated_data["organization"]
        _require_org_member(user, org)
        if not serializer.validated_data.get("items"):
            raise ValidationError("A sale needs at least one item.")

        sale = serializer.save(cashier=user, status=Sale.Status.OPEN)
        sale.sale_number = f"SALE-{sale.pk:06d}"
        sale.save(update_fields=["sale_number"])
        record_audit(
            action="CREATE",
            user=user,
            organization=org,
            entity_type="sale",
            entity_id=str(sale.pk),
            request=request,
        )

        payments = _parse_payments(request)
        if payments:
            self._complete(sale, payments, user, request)

        sale.refresh_from_db()
        out = SaleSerializer(sale)
        return Response(out.data, status=status.HTTP_201_CREATED)

    def _complete(
        self, sale: Sale, payments: list[dict[str, Any]], user: User, request: Request
    ) -> None:
        raw = request.data.get("dispensing")
        dispensing = raw if isinstance(raw, dict) else None
        try:
            complete_sale(sale=sale, payments=payments, user=user, dispensing=dispensing)
        except PharmacistRequired as exc:
            raise PermissionDenied(str(exc)) from exc
        except (InsufficientStock, DispensingRequired, ValueError) as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="SALE_COMPLETE",
            user=user,
            organization=sale.organization,
            entity_type="sale",
            entity_id=str(sale.pk),
            request=request,
        )

    @action(detail=True, methods=["post"])
    def complete(self, request: Request, pk: str | None = None) -> Response:
        """Take payment for a held (OPEN) sale."""
        sale = self.get_object()
        user = cast(User, request.user)
        _require_org_member(user, sale.organization)
        if sale.status != Sale.Status.OPEN:
            raise ValidationError("This sale is not open.")
        payments = _parse_payments(request)
        if not payments:
            raise ValidationError("Provide at least one payment.")
        self._complete(sale, payments, user, request)
        sale.refresh_from_db()
        return Response(SaleSerializer(sale).data)

    @action(detail=True, methods=["post"])
    def void(self, request: Request, pk: str | None = None) -> Response:
        """Reverse a completed sale, returning its stock to the pharmacy."""
        sale = self.get_object()
        user = cast(User, request.user)
        _require_org_member(user, sale.organization)
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            raise ValidationError("A void needs a reason.")
        try:
            void_sale(sale=sale, reason=reason, user=user)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="SALE_VOID",
            user=user,
            organization=sale.organization,
            entity_type="sale",
            entity_id=str(sale.pk),
            changes={"reason": reason},
            request=request,
        )
        sale.refresh_from_db()
        return Response(SaleSerializer(sale).data)


class DispensingViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only regulatory dispensing log — every Rx / controlled sale, with the
    pharmacist, patient, and prescriber. Org-scoped; filter with ?organization."""

    serializer_class = DispensingSerializer
    permission_classes = [IsAuthenticated]
    queryset = Dispensing.objects.select_related("sale", "dispensed_by").order_by("-created_at")

    def get_queryset(self) -> QuerySet[Dispensing]:
        user = cast(User, self.request.user)
        qs = Dispensing.objects.select_related("sale", "dispensed_by").order_by("-created_at")
        if not _is_admin(user):
            qs = qs.filter(sale__organization__in=organizations_visible_to(user))
        org = self.request.query_params.get("organization")
        if org and org.isdigit():
            qs = qs.filter(sale__organization_id=int(org))
        return qs
