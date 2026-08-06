"""Finance API: chart of accounts, journal entries, and customer-credit profiles."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from django.db.models import Case, DecimalField, Q, QuerySet, Sum, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.finance import reports
from apps.finance.models import (
    Account,
    AccountingPeriod,
    BankAccount,
    Budget,
    CreditProfile,
    CustomerCredit,
    CustomerInvoice,
    CustomerReceipt,
    DunningNotice,
    FixedAsset,
    JournalEntry,
    JournalLine,
    PaymentRun,
    SupplierBill,
    TaxCode,
    TaxPayment,
    TaxRecord,
)
from apps.finance.serializers import (
    AccountingPeriodSerializer,
    AccountSerializer,
    BankAccountSerializer,
    BudgetSerializer,
    CreditProfileSerializer,
    CustomerCreditSerializer,
    CustomerInvoiceSerializer,
    CustomerReceiptSerializer,
    DunningNoticeSerializer,
    FixedAssetSerializer,
    JournalEntrySerializer,
    PaymentRunSerializer,
    SupplierBillSerializer,
    TaxCodeSerializer,
    TaxPaymentSerializer,
    TaxRecordSerializer,
)
from apps.finance.services import (
    CreditHoldError,
    PaymentRunError,
    apply_dunning,
    cancel_payment_run,
    cash_book_lines,
    cash_flow_forecast,
    close_period,
    create_bank_account,
    create_payment_run,
    disburse_payment_run,
    lock_payment_run,
    reconcile_lines,
    record_customer_invoice,
    record_customer_receipt,
    record_supplier_bill,
    record_supplier_bill_payment,
    reopen_period,
    request_credit_override,
    submit_payment_run,
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
        return Response(_money_safe(cash_book_lines(account)))

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


def _money_safe(value: Any) -> Any:
    """Render Decimals as strings, recursively.

    DRF's JSON encoder turns a bare Decimal into a float, which silently trades
    exactness for binary floating point — unacceptable for money. Serializer fields
    already stringify; these reports return plain dicts, so they need the same
    treatment applied by hand.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _money_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_money_safe(v) for v in value]
    return value


def _resolve_org(request: Request, user: User) -> Organization:
    """The organization a report is for: the ?organization= param when given (and
    visible to the caller), otherwise the caller's own."""
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
        raise PermissionDenied("You may not view this organization's finances.")
    return organization


def _date_param(request: Request, name: str, default: date) -> date:
    raw = request.query_params.get(name)
    if not raw:
        return default
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError(f"'{name}' must be an ISO date (YYYY-MM-DD).") from exc


def _month_bounds(today: date) -> tuple[date, date]:
    start = today.replace(day=1)
    next_month = date(start.year + (start.month // 12), (start.month % 12) + 1, 1)
    return start, next_month - timedelta(days=1)


class FinanceReportsView(viewsets.ViewSet):
    """Statements over the ledger: trial balance, P&L, balance sheet, cash-flow,
    the performance cockpit, and HQ consolidation.

    All are read-only derivations of posted journal entries — see apps/finance/reports.py.
    """

    def _period(self, request: Request) -> tuple[date, date]:
        today = timezone.now().date()
        default_start, default_end = _month_bounds(today)
        start = _date_param(request, "start", default_start)
        end = _date_param(request, "end", default_end)
        if end < start:
            raise ValidationError("'end' must not be before 'start'.")
        return start, end

    @action(detail=False, methods=["get"], url_path="trial-balance")
    def trial_balance(self, request: Request) -> Response:
        org = _resolve_org(request, cast(User, request.user))
        as_of = _date_param(request, "as_of", timezone.now().date())
        return Response(_money_safe(reports.trial_balance(org, as_of=as_of)))

    @action(detail=False, methods=["get"], url_path="profit-and-loss")
    def profit_and_loss(self, request: Request) -> Response:
        org = _resolve_org(request, cast(User, request.user))
        start, end = self._period(request)
        return Response(_money_safe(reports.profit_and_loss(org, start=start, end=end)))

    @action(detail=False, methods=["get"], url_path="balance-sheet")
    def balance_sheet(self, request: Request) -> Response:
        org = _resolve_org(request, cast(User, request.user))
        as_of = _date_param(request, "as_of", timezone.now().date())
        return Response(_money_safe(reports.balance_sheet(org, as_of=as_of)))

    @action(detail=False, methods=["get"], url_path="cash-flow")
    def cash_flow(self, request: Request) -> Response:
        org = _resolve_org(request, cast(User, request.user))
        start, end = self._period(request)
        return Response(_money_safe(reports.cash_flow_statement(org, start=start, end=end)))

    @action(detail=False, methods=["get"], url_path="performance")
    def performance(self, request: Request) -> Response:
        org = _resolve_org(request, cast(User, request.user))
        start, end = self._period(request)
        data = reports.performance(org, start=start, end=end)
        data["series"] = reports.revenue_vs_cogs_series(org, start=start, end=end)
        return Response(_money_safe(data))

    @action(detail=False, methods=["get"], url_path="consolidated")
    def consolidated(self, request: Request) -> Response:
        """Group view across every branch the caller can see (HQ consolidation)."""
        user = cast(User, request.user)
        start, end = self._period(request)
        if user.is_superuser or user.has_role("SYS_ADMIN"):
            orgs = list(Organization.objects.filter(is_active=True).order_by("name"))
        else:
            orgs = list(organizations_visible_to(user).order_by("name"))
        if not orgs:
            raise ValidationError("No organizations are visible to you.")
        return Response(_money_safe(reports.consolidated(orgs, start=start, end=end)))

    @action(detail=False, methods=["get"], url_path="inventory-valuation")
    def inventory_valuation(self, request: Request) -> Response:
        """Live on-hand × wholesale cost by product. Powers the inventory-
        valuation statement tab and the Finance home KPI."""
        org = _resolve_org(request, cast(User, request.user))
        return Response(_money_safe(reports.inventory_valuation(org)))

    @action(detail=False, methods=["get"], url_path="ar-aging")
    def ar_aging(self, request: Request) -> Response:
        """Open receivables bucketed by how far past due they are, per customer."""
        org = _resolve_org(request, cast(User, request.user))
        as_of = _date_param(request, "as_of", timezone.now().date())
        return Response(_money_safe(reports.ar_aging(org, as_of=as_of)))

    @action(detail=False, methods=["get"], url_path="statement")
    def statement(self, request: Request) -> Response:
        """A printable statement of account for one customer over a period."""
        user = cast(User, request.user)
        org = _resolve_org(request, user)
        customer_param = request.query_params.get("customer")
        if not (customer_param and customer_param.isdigit()):
            raise ValidationError("A 'customer' query param is required.")
        try:
            customer = Organization.objects.get(pk=int(customer_param))
        except Organization.DoesNotExist as exc:
            raise ValidationError("Customer not found.") from exc
        start, end = self._period(request)
        return Response(
            _money_safe(reports.statement_of_account(org, customer, start=start, end=end))
        )

    @action(detail=False, methods=["get"], url_path="vat-return")
    def vat_return(self, request: Request) -> Response:
        """Rwanda VAT return draft for the period: per-class Output/Input,
        withholding, net payable, paid in period, amount due, plus a CSV body
        ready for the accountant to file via RRA e-Tax."""
        org = _resolve_org(request, cast(User, request.user))
        start, end = self._period(request)
        return Response(_money_safe(reports.vat_return(org, start=start, end=end)))


class AccountingPeriodViewSet(viewsets.ModelViewSet):
    """EOD/EOM/annual closeouts. Closing freezes the window against new postings."""

    serializer_class = AccountingPeriodSerializer
    queryset = AccountingPeriod.objects.select_related("organization", "closed_by")
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[AccountingPeriod]:
        user = cast(User, self.request.user)
        qs = AccountingPeriod.objects.select_related("organization", "closed_by")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        org_param = self.request.query_params.get("organization")
        if org_param and org_param.isdigit():
            qs = qs.filter(organization_id=int(org_param))
        return qs

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Close a period."""
        user = cast(User, request.user)
        _require_finance_manage(user)
        org = _resolve_org(request, user)
        data = request.data
        try:
            period = close_period(
                organization=org,
                kind=str(data.get("kind", AccountingPeriod.Kind.MONTH)),
                start_date=date.fromisoformat(str(data["start_date"])),
                end_date=date.fromisoformat(str(data["end_date"])),
                user=user,
                notes=str(data.get("notes", "")),
            )
        except KeyError as exc:
            raise ValidationError("'start_date' and 'end_date' are required.") from exc
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(AccountingPeriodSerializer(period).data, status=201)

    @action(detail=True, methods=["post"])
    def reopen(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        period = self.get_object()
        try:
            reopen_period(period=period, user=user, reason=str(request.data.get("reason", "")))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        period.refresh_from_db()
        return Response(AccountingPeriodSerializer(period).data)


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
        return Response(_money_safe(cash_flow_forecast(organization)))


class FixedAssetViewSet(viewsets.ModelViewSet):
    serializer_class = FixedAssetSerializer
    queryset = FixedAsset.objects.select_related("organization")

    def get_queryset(self) -> QuerySet[FixedAsset]:
        user = cast(User, self.request.user)
        qs = FixedAsset.objects.select_related("organization")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        user = cast(User, self.request.user)
        _require_finance_manage(user)
        serializer.save()


class TaxRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaxRecordSerializer
    queryset = TaxRecord.objects.select_related("organization")

    def get_queryset(self) -> QuerySet[TaxRecord]:
        user = cast(User, self.request.user)
        qs = TaxRecord.objects.select_related("organization")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        return qs


class TaxCodeViewSet(viewsets.ModelViewSet):
    """Rwanda VAT tax codes (A/B/C/D). Versions are rows, not code: a new
    Finance Law = one new row with effective_from set, never a migration."""

    serializer_class = TaxCodeSerializer
    queryset = TaxCode.objects.select_related("organization")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet[TaxCode]:
        user = cast(User, self.request.user)
        qs = TaxCode.objects.select_related("organization")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        _require_finance_manage(cast(User, self.request.user))
        serializer.save()

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        _require_finance_manage(cast(User, self.request.user))
        serializer.save()


class TaxPaymentViewSet(viewsets.ModelViewSet):
    """Register of RRA remittances. Direct write is admin-only (rare); the
    normal path is ``request_tax_payment`` which routes via the approvals
    inbox (no self-approval)."""

    serializer_class = TaxPaymentSerializer
    queryset = TaxPayment.objects.select_related("organization")
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[TaxPayment]:
        user = cast(User, self.request.user)
        qs = TaxPayment.objects.select_related("organization")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        return qs


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    queryset = Budget.objects.select_related("organization", "department", "account")

    def get_queryset(self) -> QuerySet[Budget]:
        user = cast(User, self.request.user)
        qs = Budget.objects.select_related("organization", "department", "account")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        user = cast(User, self.request.user)
        _require_finance_manage(user)
        serializer.save()


class CustomerInvoiceViewSet(viewsets.ModelViewSet):
    """AR: invoices raised on B2B customers, plus the receipts against them.

    Creation and receipting both go through the service layer so the GL entry,
    the credit-limit guard, and the numbering sequence stay in one place.
    """

    serializer_class = CustomerInvoiceSerializer
    queryset = CustomerInvoice.objects.select_related("organization", "customer")
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[CustomerInvoice]:
        user = cast(User, self.request.user)
        qs = CustomerInvoice.objects.select_related("organization", "customer").prefetch_related(
            "receipts"
        )
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            # Both sides of the trade can see the invoice — the seller because
            # they raised it, the buyer because they owe it.
            qs = qs.filter(Q(organization__in=visible) | Q(customer__in=visible))
        params = self.request.query_params
        for field in ("organization", "customer"):
            value = params.get(field)
            if value and value.isdigit():
                qs = qs.filter(**{f"{field}_id": int(value)})
        status_param = params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        if params.get("outstanding") in {"1", "true", "True"}:
            qs = qs.exclude(
                status__in=[CustomerInvoice.Status.PAID, CustomerInvoice.Status.CANCELLED]
            )
        return qs

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        serializer = CustomerInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            invoice = record_customer_invoice(
                organization=data["organization"],
                customer=data["customer"],
                invoice_date=data["invoice_date"],
                due_date=data["due_date"],
                total_amount=data["total_amount"],
                vat_amount=data.get("vat_amount") or Decimal("0"),
                tax_class=data.get("tax_class", "B"),
                reference_type=data.get("reference_type", ""),
                reference_id=data.get("reference_id", ""),
                notes=data.get("notes", ""),
                user=user,
            )
        except CreditHoldError as exc:
            # 409, not 400: the request is well-formed; the customer's credit
            # state is what refuses it.
            return Response({"detail": str(exc)}, status=409)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(CustomerInvoiceSerializer(invoice).data, status=201)

    @action(detail=True, methods=["post"], url_path="record-receipt")
    def record_receipt(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        invoice = self.get_object()
        try:
            receipt = record_customer_receipt(
                invoice=invoice,
                amount=Decimal(str(request.data.get("amount", 0))),
                method=str(request.data.get("method", "CASH")),
                reference=str(request.data.get("reference", "")),
                user=user,
            )
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="PAYMENT",
            user=user,
            organization=invoice.organization,
            entity_type="customer_invoice",
            entity_id=str(invoice.pk),
            changes={"amount": str(receipt.amount), "method": receipt.method},
            request=request,
        )
        invoice.refresh_from_db()
        return Response(CustomerInvoiceSerializer(invoice).data, status=201)


class CustomerReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    """Receipt register. Receipts are created via the invoice's
    ``record-receipt`` action so they can never exist without a GL entry."""

    serializer_class = CustomerReceiptSerializer
    queryset = CustomerReceipt.objects.select_related("invoice__customer", "invoice__organization")

    def get_queryset(self) -> QuerySet[CustomerReceipt]:
        user = cast(User, self.request.user)
        qs = CustomerReceipt.objects.select_related("invoice__customer", "invoice__organization")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(Q(invoice__organization__in=visible) | Q(invoice__customer__in=visible))
        invoice_param = self.request.query_params.get("invoice")
        if invoice_param and invoice_param.isdigit():
            qs = qs.filter(invoice_id=int(invoice_param))
        return qs


class CustomerCreditViewSet(viewsets.ReadOnlyModelViewSet):
    """On-account credits (overpayments, credit notes, returns) held for a customer."""

    serializer_class = CustomerCreditSerializer
    queryset = CustomerCredit.objects.select_related("organization", "customer")

    def get_queryset(self) -> QuerySet[CustomerCredit]:
        user = cast(User, self.request.user)
        qs = CustomerCredit.objects.select_related("organization", "customer")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(Q(organization__in=visible) | Q(customer__in=visible))
        customer_param = self.request.query_params.get("customer")
        if customer_param and customer_param.isdigit():
            qs = qs.filter(customer_id=int(customer_param))
        return qs


class DunningNoticeViewSet(viewsets.ReadOnlyModelViewSet):
    """The collections queue. ``run`` walks the ladder for an organization and
    issues whatever step each overdue invoice has newly earned."""

    serializer_class = DunningNoticeSerializer
    queryset = DunningNotice.objects.select_related("invoice__customer")

    def get_queryset(self) -> QuerySet[DunningNotice]:
        user = cast(User, self.request.user)
        qs = DunningNotice.objects.select_related("invoice__customer", "invoice__organization")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            visible = organizations_visible_to(user)
            qs = qs.filter(Q(invoice__organization__in=visible) | Q(invoice__customer__in=visible))
        org_param = self.request.query_params.get("organization")
        if org_param and org_param.isdigit():
            qs = qs.filter(invoice__organization_id=int(org_param))
        level = self.request.query_params.get("level")
        if level:
            qs = qs.filter(level=level.upper())
        return qs

    @action(detail=False, methods=["post"], url_path="run")
    def run(self, request: Request) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        organization = _resolve_org(request, user)
        issued = apply_dunning(organization=organization)
        record_audit(
            action="UPDATE",
            user=user,
            organization=organization,
            entity_type="dunning_run",
            entity_id=str(organization.pk),
            changes={"issued": str(len(issued))},
            request=request,
        )
        return Response(
            {"issued": len(issued), "notices": DunningNoticeSerializer(issued, many=True).data},
            status=201,
        )


class PaymentRunViewSet(viewsets.ModelViewSet):
    """Batch supplier settlement: build a run, get it signed off, hand the file
    to the bank, then post the payments.

    Every state change is a named action rather than a PATCH — a payment run's
    status is the audit trail, not a field anyone gets to set.
    """

    serializer_class = PaymentRunSerializer
    queryset = PaymentRun.objects.select_related("organization").prefetch_related(
        "lines__bill__supplier"
    )
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[PaymentRun]:
        user = cast(User, self.request.user)
        qs = PaymentRun.objects.select_related("organization").prefetch_related(
            "lines__bill__supplier"
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
        organization = _resolve_org(request, user)
        bill_ids = request.data.get("bills") or []
        if not isinstance(bill_ids, list) or not bill_ids:
            raise ValidationError("Provide a non-empty 'bills' list.")
        bills = list(SupplierBill.objects.filter(pk__in=bill_ids, organization=organization))
        if len(bills) != len(set(bill_ids)):
            raise ValidationError("One or more bills were not found in this organization.")
        try:
            run = create_payment_run(
                organization=organization,
                bills=bills,
                method=str(request.data.get("method", PaymentRun.Method.BANK_TRANSFER)),
                scheduled_for=request.data.get("scheduled_for") or None,
                notes=str(request.data.get("notes", "")),
                user=user,
            )
        except PaymentRunError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(PaymentRunSerializer(run).data, status=201)

    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        run = self.get_object()
        try:
            approval = submit_payment_run(run=run, user=user)
        except PaymentRunError as exc:
            raise ValidationError(str(exc)) from exc
        run.refresh_from_db()
        data = PaymentRunSerializer(run).data
        data["approval_request"] = approval.pk
        return Response(data, status=201)

    @action(detail=True, methods=["post"])
    def disburse(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        run = self.get_object()
        try:
            disburse_payment_run(run=run, user=user)
        except PaymentRunError as exc:
            raise ValidationError(str(exc)) from exc
        run.refresh_from_db()
        return Response(PaymentRunSerializer(run).data)

    @action(detail=True, methods=["post"])
    def lock(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        run = self.get_object()
        try:
            lock_payment_run(run=run, user=user)
        except PaymentRunError as exc:
            raise ValidationError(str(exc)) from exc
        run.refresh_from_db()
        return Response(PaymentRunSerializer(run).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        run = self.get_object()
        try:
            cancel_payment_run(run=run, user=user, reason=str(request.data.get("reason", "")))
        except PaymentRunError as exc:
            raise ValidationError(str(exc)) from exc
        run.refresh_from_db()
        return Response(PaymentRunSerializer(run).data)

    @action(detail=True, methods=["get"], url_path="disbursement-file")
    def disbursement_file(self, request: Request, pk: str | None = None) -> HttpResponse:
        """Download the CSV the bank or MoMo aggregator expects."""
        run = self.get_object()
        if not run.disbursement_file:
            raise ValidationError("This run has no disbursement file yet — approve it first.")
        response = HttpResponse(run.disbursement_file, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{run.disbursement_filename}"'
        return response
