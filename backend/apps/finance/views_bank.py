"""Bank reconciliation API.

Reconciling is not ticking a box. `summary` reports the difference between the
bank and the books that nothing accounts for, and `close` refuses to sign off
while that difference is non-zero or any statement line is still unexplained.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.finance.models import Account, BankAccount, BankStatement, CostCentre
from apps.finance.reconciliation import (
    ReconciliationError,
    auto_match,
    close_reconciliation,
    default_charge_account,
    explain_line,
    ignore_line,
    import_statement,
    match_lines,
    parse_statement_csv,
    reconciliation_summary,
    suggestions_for,
    unexplained_report,
    unmatch,
)
from apps.finance.serializers import (
    BankStatementLineSerializer,
    BankStatementSerializer,
    JournalEntrySerializer,
)
from apps.finance.views import _date_param, _require_finance_manage
from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to


class BankStatementViewSet(viewsets.ModelViewSet):
    serializer_class = BankStatementSerializer
    queryset = BankStatement.objects.select_related("bank_account", "imported_by")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[BankStatement]:
        user = cast(User, self.request.user)
        qs = BankStatement.objects.select_related("bank_account", "imported_by", "reconciled_by")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(bank_account__organization__in=organizations_visible_to(user))
        account = self.request.query_params.get("bank_account")
        if account and account.isdigit():
            qs = qs.filter(bank_account_id=int(account))
        return qs

    def _bank_account(self, request: Request, pk: Any) -> BankAccount:
        account = BankAccount.objects.filter(pk=pk).first() if pk else None
        if account is None:
            raise ValidationError("A valid 'bank_account' is required.")
        user = cast(User, request.user)
        if not (
            user.is_superuser
            or user.has_role("SYS_ADMIN")
            or account.organization in organizations_visible_to(user)
        ):
            raise PermissionDenied("You may not reconcile that account.")
        return account

    def _line(self, line_id: str | None) -> Any:
        line = self.get_object().lines.filter(pk=line_id).first()
        if line is None:
            raise ValidationError("That line does not belong to this statement.")
        return line

    @action(detail=False, methods=["post"], url_path="import-csv")
    def import_csv(self, request: Request) -> Response:
        """Import a bank CSV. Refuses a statement whose own arithmetic does not foot."""
        user = cast(User, request.user)
        _require_finance_manage(user)
        data = request.data
        account = self._bank_account(request, data.get("bank_account"))
        try:
            rows = parse_statement_csv(str(data.get("csv", "")))
            statement = import_statement(
                bank_account=account,
                rows=rows,
                start_date=date.fromisoformat(str(data["start_date"])),
                end_date=date.fromisoformat(str(data["end_date"])),
                opening_balance=Decimal(str(data.get("opening_balance", "0"))),
                closing_balance=Decimal(str(data.get("closing_balance", "0"))),
                reference=str(data.get("reference", "")),
                source_filename=str(data.get("filename", "")),
                user=user,
            )
        except KeyError as exc:
            raise ValidationError("'start_date' and 'end_date' are required.") from exc
        except (ReconciliationError, ValueError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {
                "statement": BankStatementSerializer(statement).data,
                "imported_lines": statement.lines.count(),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def lines(self, request: Request, pk: str | None = None) -> Response:
        statement = self.get_object()
        return Response(
            BankStatementLineSerializer(statement.lines.prefetch_related("matches"), many=True).data
        )

    @action(detail=True, methods=["get"])
    def summary(self, request: Request, pk: str | None = None) -> Response:
        """The four-line reconciliation statement plus the unexplained difference."""
        return Response(reconciliation_summary(self.get_object()))

    @action(detail=True, methods=["get"])
    def suggestions(self, request: Request, pk: str | None = None) -> Response:
        """Candidate ledger lines for each unmatched bank line, best first."""
        return Response(suggestions_for(self.get_object()))

    @action(detail=True, methods=["post"], url_path="auto-match")
    def auto_match_action(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        return Response(auto_match(self.get_object(), user=user))

    @action(detail=True, methods=["post"], url_path="lines/(?P<line_id>[^/.]+)/match")
    def match_line(
        self, request: Request, pk: str | None = None, line_id: str | None = None
    ) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        line = self._line(line_id)
        try:
            match_lines(
                statement_line=line,
                journal_line_ids=[int(i) for i in request.data.get("journal_line_ids", [])],
                user=user,
            )
        except (ReconciliationError, ValueError, TypeError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(BankStatementLineSerializer(line).data)

    @action(detail=True, methods=["post"], url_path="lines/(?P<line_id>[^/.]+)/unmatch")
    def unmatch_line(
        self, request: Request, pk: str | None = None, line_id: str | None = None
    ) -> Response:
        _require_finance_manage(cast(User, request.user))
        line = unmatch(statement_line=self._line(line_id))
        return Response(BankStatementLineSerializer(line).data)

    @action(detail=True, methods=["post"], url_path="lines/(?P<line_id>[^/.]+)/explain")
    def explain(
        self, request: Request, pk: str | None = None, line_id: str | None = None
    ) -> Response:
        """Post a bank line the books never knew about: charges, interest, direct debits."""
        user = cast(User, request.user)
        _require_finance_manage(user)
        statement = self.get_object()
        line = self._line(line_id)
        organization = statement.bank_account.organization

        account_id = request.data.get("account")
        account = (
            Account.objects.filter(pk=account_id, organization=organization).first()
            if account_id
            else default_charge_account(statement.bank_account)
        )
        if account is None:
            raise ValidationError("That account does not exist in this organization.")

        centre = None
        centre_id = request.data.get("cost_centre")
        if centre_id:
            centre = CostCentre.objects.filter(pk=centre_id, organization=organization).first()

        try:
            entry = explain_line(
                statement_line=line,
                account=account,
                description=str(request.data.get("description", "")),
                cost_centre=centre,
                user=user,
            )
        except (ReconciliationError, ValueError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {
                "line": BankStatementLineSerializer(line).data,
                "entry": JournalEntrySerializer(entry).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="lines/(?P<line_id>[^/.]+)/ignore")
    def ignore(
        self, request: Request, pk: str | None = None, line_id: str | None = None
    ) -> Response:
        _require_finance_manage(cast(User, request.user))
        line = self._line(line_id)
        try:
            ignore_line(statement_line=line, reason=str(request.data.get("reason", "")))
        except ReconciliationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(BankStatementLineSerializer(line).data)

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: str | None = None) -> Response:
        """Sign the reconciliation off, only if it actually reconciles."""
        user = cast(User, request.user)
        _require_finance_manage(user)
        try:
            statement = close_reconciliation(statement=self.get_object(), user=user)
        except ReconciliationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(BankStatementSerializer(statement).data)

    @action(detail=False, methods=["get"])
    def unexplained(self, request: Request) -> Response:
        """Everything still unaccounted for on one account, across all its statements."""
        account = self._bank_account(request, request.query_params.get("bank_account"))
        as_of = _date_param(request, "as_of", timezone.localdate())
        return Response(unexplained_report(account, as_of=as_of))
