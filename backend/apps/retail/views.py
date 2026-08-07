"""Retail POS API: over-the-counter sales at a pharmacy.

Org-scoped: a member of a pharmacy (cashier / pharmacist / org-admin) rings up
sales for that pharmacy; SYS_ADMIN sees all. Prices come from the pharmacy's own
listing; stock moves via the FEFO service. See apps/retail/services.py.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, cast

from django.db import IntegrityError
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
from apps.retail.models import (
    ClinicalService,
    ClinicalServiceRecord,
    ControlledSubstanceRegister,
    Dispensing,
    DrawerSession,
    POSPromotion,
    Prescription,
    Sale,
)
from apps.retail.serializers import (
    ClinicalServiceRecordSerializer,
    ClinicalServiceSerializer,
    ControlledSubstanceRegisterSerializer,
    DispensingSerializer,
    DrawerSessionSerializer,
    POSPromotionSerializer,
    PrescriptionSerializer,
    SaleSerializer,
)
from apps.retail.services import (
    DispensingRequired,
    InsufficientStock,
    PharmacistRequired,
    close_drawer,
    complete_sale,
    drawer_report,
    return_sale_items,
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
        # Link the sale to this cashier's open till session (if any) so the cash-up
        # can reconcile it. Sales rung up with no open drawer simply aren't counted.
        sale.drawer_session = DrawerSession.objects.filter(
            organization=org, cashier=user, status=DrawerSession.Status.OPEN
        ).first()
        sale.sale_number = f"SALE-{sale.pk:06d}"
        sale.save(update_fields=["sale_number", "drawer_session"])
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

    @action(detail=True, methods=["post"], url_path="return")
    def return_items(self, request: Request, pk: str | None = None) -> Response:
        """Return some items from a completed sale — stock back, refund, credit note."""
        sale = self.get_object()
        user = cast(User, request.user)
        _require_org_member(user, sale.organization)
        raw = request.data.get("lines", [])
        lines = [
            {"sale_item": r["sale_item"], "quantity": r.get("quantity", 0)}
            for r in raw
            if isinstance(r, dict) and "sale_item" in r
        ]
        if not lines:
            raise ValidationError("Select at least one item to return.")
        try:
            return_sale_items(
                sale=sale,
                lines=lines,
                reason=str(request.data.get("reason", "")).strip(),
                user=user,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="SALE_RETURN",
            user=user,
            organization=sale.organization,
            entity_type="sale",
            entity_id=str(sale.pk),
            request=request,
        )
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


class DrawerSessionViewSet(viewsets.ModelViewSet):
    """Cash-drawer / till sessions: open with a float, ring up sales, then cash up
    (count the cash → over/short) and close. Org-scoped; one open drawer per cashier."""

    serializer_class = DrawerSessionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    queryset = DrawerSession.objects.select_related("organization", "cashier")

    def get_queryset(self) -> QuerySet[DrawerSession]:
        user = cast(User, self.request.user)
        qs = DrawerSession.objects.select_related("organization", "cashier")
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
        """Open a drawer with a starting float. One open drawer per cashier per org."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = cast(User, request.user)
        org = serializer.validated_data["organization"]
        _require_org_member(user, org)
        try:
            session = serializer.save(cashier=user, status=DrawerSession.Status.OPEN)
        except IntegrityError as exc:
            raise ValidationError("You already have an open drawer — close it first.") from exc
        record_audit(
            action="DRAWER_OPEN",
            user=user,
            organization=org,
            entity_type="drawer_session",
            entity_id=str(session.pk),
            request=request,
        )
        return Response(DrawerSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def current(self, request: Request) -> Response:
        """The caller's open drawer for ?organization, with a live X-report (204 if none)."""
        user = cast(User, request.user)
        qs = self.get_queryset().filter(status=DrawerSession.Status.OPEN, cashier=user)
        org_id = request.query_params.get("organization")
        if org_id and org_id.isdigit():
            qs = qs.filter(organization_id=int(org_id))
        session = qs.first()
        if session is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        data = dict(DrawerSessionSerializer(session).data)
        data["report"] = drawer_report(session)
        return Response(data)

    @action(detail=True, methods=["get"])
    def report(self, request: Request, pk: str | None = None) -> Response:
        """X/Z cash report for a drawer (running while open, final once closed)."""
        session = self.get_object()
        data = dict(DrawerSessionSerializer(session).data)
        data["report"] = drawer_report(session)
        return Response(data)

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: str | None = None) -> Response:
        """Cash up: submit the counted cash → over/short, and close the drawer."""
        session = self.get_object()
        user = cast(User, request.user)
        _require_org_member(user, session.organization)
        if not _is_admin(user) and session.cashier_id != user.pk:
            raise PermissionDenied(
                "Only the cashier who opened this drawer (or an admin) can close it."
            )
        raw = request.data.get("counted_cash")
        if raw is None or raw == "":
            raise ValidationError("Enter the counted cash to close the drawer.")
        try:
            counted = Decimal(str(raw))
        except (InvalidOperation, TypeError) as exc:
            raise ValidationError("Counted cash must be a number.") from exc
        try:
            close_drawer(
                session=session,
                counted_cash=counted,
                user=user,
                notes=str(request.data.get("notes", "")).strip(),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="DRAWER_CLOSE",
            user=user,
            organization=session.organization,
            entity_type="drawer_session",
            entity_id=str(session.pk),
            changes={"over_short": str(session.over_short)},
            request=request,
        )
        session.refresh_from_db()
        data = dict(DrawerSessionSerializer(session).data)
        data["report"] = drawer_report(session)
        return Response(data)


class PrescriptionViewSet(viewsets.ModelViewSet):
    serializer_class = PrescriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Prescription]:
        user = cast(User, self.request.user)
        qs = Prescription.objects.select_related("organization")
        if not _is_admin(user):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        return qs


class ControlledSubstanceRegisterViewSet(viewsets.ModelViewSet):
    serializer_class = ControlledSubstanceRegisterSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[ControlledSubstanceRegister]:
        user = cast(User, self.request.user)
        qs = ControlledSubstanceRegister.objects.select_related(
            "organization", "product", "logged_by"
        )
        if not _is_admin(user):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        return qs


class POSPromotionViewSet(viewsets.ModelViewSet):
    queryset = POSPromotion.objects.all()
    serializer_class = POSPromotionSerializer
    permission_classes = [IsAuthenticated]


class ClinicalServiceViewSet(viewsets.ModelViewSet):
    queryset = ClinicalService.objects.all()
    serializer_class = ClinicalServiceSerializer
    permission_classes = [IsAuthenticated]


class ClinicalServiceRecordViewSet(viewsets.ModelViewSet):
    serializer_class = ClinicalServiceRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[ClinicalServiceRecord]:
        user = cast(User, self.request.user)
        qs = ClinicalServiceRecord.objects.select_related("organization", "service", "performed_by")
        if not _is_admin(user):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        return qs
