"""Finance API: chart of accounts, journal entries, and customer-credit profiles."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from django.db.models import Case, DecimalField, Q, QuerySet, Sum, When
from django.db.models.functions import Coalesce
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.finance.models import (
    Account,
    BankAccount,
    CreditProfile,
    JournalEntry,
    JournalLine,
    SupplierBill,
)
from apps.finance.serializers import (
    AccountSerializer,
    BankAccountSerializer,
    CreditProfileSerializer,
    JournalEntrySerializer,
    SupplierBillSerializer,
)
from apps.finance.services import (
    cash_book_lines,
    cash_flow_forecast,
    create_bank_account,
    reconcile_lines,
    record_supplier_bill,
    record_supplier_bill_payment,
    request_credit_override,
)
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User
from apps.iam.scoping import organizations_visible_to


def _require_finance_manage(user: User) -> None:
    if not (user.is_superuser or user.has_permission("finance.manage")):
        raise PermissionDenied("You may not manage finance records.")


def _with_balances(qs: QuerySet[Account]) -> QuerySet[Account]:
    """Annotate each account with its total debit/credit turnover in one query,
    so AccountSerializer.get_balance() never has to hit the DB per row."""
    money: DecimalField = DecimalField(max_digits=14, decimal_places=2)
    return qs.annotate(
        _debit_total=Coalesce(
            Sum(
                Case(
                    When(lines__side=JournalLine.Side.DEBIT, then="lines__amount"),
                    output_field=money,
                )
            ),
            0,
            output_field=money,
        ),
        _credit_total=Coalesce(
            Sum(
                Case(
                    When(lines__side=JournalLine.Side.CREDIT, then="lines__amount"),
                    output_field=money,
                )
            ),
            0,
            output_field=money,
        ),
        # The aggregate's GROUP BY drops Meta.ordering, which would make pagination
        # non-deterministic — restore it explicitly.
    ).order_by("code")


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
        return _with_balances(qs)

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


class BankAccountViewSet(viewsets.ModelViewSet):
    """Bank/MoMo/Airtel/cash accounts — each has its own GL sub-account, cash-book,
    and reconciliation state."""

    serializer_class = BankAccountSerializer
    queryset = BankAccount.objects.select_related("organization", "gl_account")
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[BankAccount]:
        user = cast(User, self.request.user)
        qs = BankAccount.objects.select_related("organization", "gl_account")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        org_param = self.request.query_params.get("organization")
        if org_param and org_param.isdigit():
            qs = qs.filter(organization_id=int(org_param))
        return qs

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        try:
            organization = Organization.objects.get(pk=str(request.data.get("organization")))
        except (Organization.DoesNotExist, TypeError, ValueError) as exc:
            raise ValidationError("A valid 'organization' id is required.") from exc
        try:
            account = create_bank_account(
                organization=organization,
                name=str(request.data.get("name", "")),
                kind=str(request.data.get("kind", BankAccount.Kind.BANK)),
                bank_name=str(request.data.get("bank_name", "")),
                account_number=str(request.data.get("account_number", "")),
                currency=str(request.data.get("currency", "RWF")),
                opening_balance=Decimal(str(request.data.get("opening_balance", 0))),
                user=user,
            )
        except (ValueError, TypeError) as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="CREATE",
            user=user,
            organization=organization,
            entity_type="bank_account",
            entity_id=str(account.pk),
            request=request,
        )
        return Response(BankAccountSerializer(account).data, status=201)

    @action(detail=True, methods=["get"], url_path="cash-book")
    def cash_book(self, request: Request, pk: str | None = None) -> Response:
        account = self.get_object()
        return Response(cash_book_lines(account))

    @action(detail=True, methods=["post"], url_path="reconcile")
    def reconcile(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        line_ids = request.data.get("line_ids", [])
        if not isinstance(line_ids, list) or not line_ids:
            raise ValidationError("'line_ids' must be a non-empty list.")
        count = reconcile_lines(
            line_ids=[int(i) for i in line_ids],
            statement_reference=str(request.data.get("statement_reference", "")),
            user=user,
        )
        return Response({"reconciled": count})


class CashFlowForecastView(viewsets.ViewSet):
    """A real cash-flow projection built from unpaid B2B receivables and
    supplier-bill payables due, bucketed by how soon they're due."""

    def list(self, request: Request) -> Response:
        user = cast(User, request.user)
        org_param = request.query_params.get("organization")
        if org_param and org_param.isdigit():
            try:
                organization = Organization.objects.get(pk=org_param)
            except Organization.DoesNotExist as exc:
                raise ValidationError("Organization not found.") from exc
        elif user.organization_id:
            organization = cast(Organization, user.organization)
        else:
            raise ValidationError("An 'organization' query param is required.")
        if not (
            user.is_superuser
            or user.has_role("SYS_ADMIN")
            or organization in organizations_visible_to(user)
        ):
            raise PermissionDenied("You may not view this organization's cash-flow forecast.")
        return Response(cash_flow_forecast(organization))
