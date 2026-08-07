"""Accruals and prepayments API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.lookups import lookup_pk
from apps.finance.accruals import (
    ScheduleError,
    cancel_schedule,
    create_schedule,
    run_schedules,
    schedule_summary,
)
from apps.finance.models import Account, CostCentre, RecurringSchedule, ScheduleRun
from apps.finance.views import _date_param, _require_finance_manage, _resolve_org
from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to


class ScheduleRunSerializer(serializers.ModelSerializer):
    entry_number = serializers.CharField(source="journal_entry.entry_number", read_only=True)
    reversal_number = serializers.CharField(source="reversal_entry.entry_number", read_only=True)

    class Meta:
        model = ScheduleRun
        fields = [
            "id",
            "period_month",
            "amount",
            "journal_entry",
            "entry_number",
            "reversal_entry",
            "reversal_number",
            "posted_at",
        ]
        read_only_fields = fields


class RecurringScheduleSerializer(serializers.ModelSerializer):
    """A cost spread across months. Posting happens through `run`, never here."""

    expense_account_code = serializers.CharField(source="expense_account.code", read_only=True)
    expense_account_name = serializers.CharField(source="expense_account.name", read_only=True)
    cost_centre_name = serializers.CharField(source="cost_centre.name", read_only=True)
    amount_per_period = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    posted_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    remaining = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    runs = ScheduleRunSerializer(many=True, read_only=True)

    class Meta:
        model = RecurringSchedule
        fields = [
            "id",
            "organization",
            "name",
            "kind",
            "expense_account",
            "expense_account_code",
            "expense_account_name",
            "cost_centre",
            "cost_centre_name",
            "total_amount",
            "periods",
            "start_month",
            "amount_per_period",
            "posted_total",
            "remaining",
            "status",
            "auto_reverse",
            "source_reference",
            "notes",
            "runs",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "amount_per_period",
            "posted_total",
            "remaining",
            "runs",
            "created_at",
        ]


class RecurringScheduleViewSet(viewsets.ModelViewSet):
    """Prepayments and accruals.

    A schedule is never edited into a different shape once it has started
    posting — cancel it and start another, so the history stays readable.
    """

    serializer_class = RecurringScheduleSerializer
    queryset = RecurringSchedule.objects.select_related("expense_account", "cost_centre")
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[RecurringSchedule]:
        user = cast(User, self.request.user)
        qs = RecurringSchedule.objects.select_related(
            "expense_account", "cost_centre"
        ).prefetch_related("runs__journal_entry", "runs__reversal_entry")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        org_param = self.request.query_params.get("organization")
        if org_param and org_param.isdigit():
            qs = qs.filter(organization_id=int(org_param))
        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        return qs

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = cast(User, request.user)
        _require_finance_manage(user)
        organization = _resolve_org(request, user)
        data = request.data

        account = Account.objects.filter(
            pk=lookup_pk(data.get("expense_account")), organization=organization
        ).first()
        if account is None:
            raise ValidationError("A valid 'expense_account' in this organization is required.")

        centre = None
        if data.get("cost_centre"):
            centre = CostCentre.objects.filter(
                pk=data["cost_centre"], organization=organization
            ).first()

        try:
            schedule = create_schedule(
                organization=organization,
                name=str(data.get("name", "")).strip(),
                kind=str(data.get("kind", "")),
                expense_account=account,
                total_amount=Decimal(str(data.get("total_amount", "0"))),
                periods=int(data.get("periods", 0)),
                start_month=date.fromisoformat(str(data["start_month"])),
                cost_centre=centre,
                auto_reverse=data.get("auto_reverse"),
                source_reference=str(data.get("source_reference", "")),
                notes=str(data.get("notes", "")),
                user=user,
            )
        except KeyError as exc:
            raise ValidationError("'start_month' is required.") from exc
        except (ScheduleError, ValueError, TypeError, ArithmeticError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(schedule).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        """Stop future charges. Whatever has already posted stays posted."""
        _require_finance_manage(cast(User, request.user))
        try:
            schedule = cancel_schedule(
                schedule=self.get_object(), reason=str(request.data.get("reason", ""))
            )
        except ScheduleError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(schedule).data)

    @action(detail=False, methods=["post"])
    def run(self, request: Request) -> Response:
        """Post every schedule due up to the given month, catching up if behind."""
        user = cast(User, request.user)
        _require_finance_manage(user)
        organization = _resolve_org(request, user)
        as_of = _date_param(request, "as_of", timezone.localdate())
        return Response(run_schedules(organization=organization, as_of=as_of, user=user))

    @action(detail=False, methods=["get"])
    def summary(self, request: Request) -> Response:
        """What is still sitting in prepayments and accruals, and what is overdue to post."""
        organization = _resolve_org(request, cast(User, request.user))
        as_of = _date_param(request, "as_of", timezone.localdate())
        return Response(schedule_summary(organization, as_of=as_of))
