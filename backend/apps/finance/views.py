"""Finance API: chart of accounts, journal entries, and customer-credit profiles."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from django.db.models import Q, QuerySet
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.finance.models import Account, CreditProfile, JournalEntry, SupplierBill
from apps.finance.serializers import (
    AccountSerializer,
    CreditProfileSerializer,
    JournalEntrySerializer,
    SupplierBillSerializer,
)
from apps.finance.services import (
    record_supplier_bill,
    record_supplier_bill_payment,
    request_credit_override,
)
from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to


def _require_finance_manage(user: User) -> None:
    if not (user.is_superuser or user.has_permission("finance.manage")):
        raise PermissionDenied("You may not manage finance records.")


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    queryset = Account.objects.select_related("organization", "parent")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[Account]:
        user = cast(User, self.request.user)
        qs = Account.objects.select_related("organization", "parent")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        org_param = self.request.query_params.get("organization")
        if org_param and org_param.isdigit():
            qs = qs.filter(organization_id=int(org_param))
        return qs

    def perform_create(self, serializer: BaseSerializer) -> None:
        _require_finance_manage(cast(User, self.request.user))
        account = serializer.save()
        record_audit(
            action="CREATE",
            user=cast(User, self.request.user),
            organization=account.organization,
            entity_type="account",
            entity_id=str(account.pk),
            request=self.request,
        )

    def perform_update(self, serializer: BaseSerializer) -> None:
        _require_finance_manage(cast(User, self.request.user))
        serializer.save()


class JournalEntryViewSet(viewsets.ModelViewSet):
    """Journal entries: read for anyone with finance.view; posting a manual entry
    requires finance.manage. Entries are immutable once created (no update/delete)."""

    serializer_class = JournalEntrySerializer
    queryset = JournalEntry.objects.select_related("organization").prefetch_related(
        "lines__account"
    )
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[JournalEntry]:
        user = cast(User, self.request.user)
        qs = JournalEntry.objects.select_related("organization").prefetch_related("lines__account")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        org_param = self.request.query_params.get("organization")
        if org_param and org_param.isdigit():
            qs = qs.filter(organization_id=int(org_param))
        return qs

    def perform_create(self, serializer: BaseSerializer) -> None:
        user = cast(User, self.request.user)
        _require_finance_manage(user)
        entry = serializer.save(posted_by=user)
        record_audit(
            action="POST",
            user=user,
            organization=entry.organization,
            entity_type="journal_entry",
            entity_id=str(entry.pk),
            request=self.request,
        )


class CreditProfileViewSet(viewsets.ModelViewSet):
    """Customer-credit profiles. Direct edits to limit/terms/hold are blocked —
    use the ``request-override`` action, which routes through the approvals engine."""

    serializer_class = CreditProfileSerializer
    queryset = CreditProfile.objects.select_related("creditor", "debtor")
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[CreditProfile]:
        user = cast(User, self.request.user)
        qs = CreditProfile.objects.select_related("creditor", "debtor")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(Q(creditor__in=visible) | Q(debtor__in=visible))
        return qs

    def perform_create(self, serializer: BaseSerializer) -> None:
        _require_finance_manage(cast(User, self.request.user))
        serializer.save()

    @action(detail=True, methods=["post"], url_path="request-override")
    def request_override(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        profile = self.get_object()
        data = request.data
        try:
            approval = request_credit_override(
                credit_profile=profile,
                requested_by=user,
                new_limit=Decimal(str(data["credit_limit"])) if "credit_limit" in data else None,
                new_terms_days=int(data["terms_days"]) if "terms_days" in data else None,
                lift_hold=bool(data.get("lift_hold")),
                put_on_hold=bool(data.get("put_on_hold")),
                hold_reason=str(data.get("hold_reason", "")),
                reason=str(data.get("reason", "")),
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"approval_request": approval.pk, "status": approval.status}, status=201)


class SupplierBillViewSet(viewsets.ModelViewSet):
    """AP: supplier bills + payments. See SupplierBill's docstring — this is the
    2-way bill↔payment flow; full 3-way match awaits the Procurement PO module."""

    serializer_class = SupplierBillSerializer
    queryset = SupplierBill.objects.select_related("organization", "supplier").prefetch_related(
        "payments"
    )
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[SupplierBill]:
        user = cast(User, self.request.user)
        qs = SupplierBill.objects.select_related("organization", "supplier").prefetch_related(
            "payments"
        )
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        org_param = self.request.query_params.get("organization")
        if org_param and org_param.isdigit():
            qs = qs.filter(organization_id=int(org_param))
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        return qs

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        serializer = SupplierBillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            bill = record_supplier_bill(
                organization=data["organization"],
                supplier=data["supplier"],
                bill_number=data.get("bill_number", ""),
                bill_date=data["bill_date"],
                due_date=data.get("due_date"),
                total_amount=data["total_amount"],
                reference_type=data.get("reference_type", ""),
                reference_id=data.get("reference_id", ""),
                notes=data.get("notes", ""),
                user=user,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="CREATE",
            user=user,
            organization=bill.organization,
            entity_type="supplier_bill",
            entity_id=str(bill.pk),
            request=request,
        )
        return Response(SupplierBillSerializer(bill).data, status=201)

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        bill = self.get_object()
        try:
            record_supplier_bill_payment(
                bill=bill,
                amount=Decimal(str(request.data.get("amount", 0))),
                method=str(request.data.get("method", "BANK_TRANSFER")),
                reference=str(request.data.get("reference", "")),
                user=user,
            )
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="PAYMENT",
            user=user,
            organization=bill.organization,
            entity_type="supplier_bill",
            entity_id=str(bill.pk),
            changes={"amount": str(request.data.get("amount", 0))},
            request=request,
        )
        bill.refresh_from_db()
        return Response(SupplierBillSerializer(bill).data)
