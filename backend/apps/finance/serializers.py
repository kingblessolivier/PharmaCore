from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.finance.models import (
    Account,
    AccountingPeriod,
    BankAccount,
    CreditProfile,
    JournalEntry,
    JournalLine,
    SupplierBill,
    SupplierBillPayment,
)


class AccountSerializer(serializers.ModelSerializer):
    """A chart-of-accounts line, with its current balance — signed so the account's
    own normal side (debit or credit) always reads as a positive number, the way
    every real chart of accounts presents it."""

    balance = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "id",
            "organization",
            "code",
            "name",
            "account_type",
            "normal_balance",
            "parent",
            "is_system",
            "is_active",
            "balance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_system", "created_at", "updated_at"]

    def get_balance(self, obj: Account) -> str:
        # AccountViewSet.get_queryset() annotates these to avoid N+1; fall back to a
        # direct aggregate for any Account instance reached another way.
        debit_total = getattr(obj, "_debit_total", None)
        credit_total = getattr(obj, "_credit_total", None)
        if debit_total is None or credit_total is None:
            from django.db.models import Sum

            debit_total = obj.lines.filter(side=JournalLine.Side.DEBIT).aggregate(t=Sum("amount"))[
                "t"
            ] or Decimal("0")
            credit_total = obj.lines.filter(side=JournalLine.Side.CREDIT).aggregate(
                t=Sum("amount")
            )["t"] or Decimal("0")
        signed = (
            debit_total - credit_total
            if obj.normal_balance == Account.Balance.DEBIT
            else credit_total - debit_total
        )
        return str(signed)


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = JournalLine
        fields = ["id", "account", "account_code", "account_name", "side", "amount", "memo"]


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True)
    total_debit = serializers.FloatField(read_only=True)
    total_credit = serializers.FloatField(read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "organization",
            "organization_name",
            "entry_number",
            "entry_date",
            "description",
            "reference_type",
            "reference_id",
            "status",
            "total_debit",
            "total_credit",
            "lines",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "entry_number",
            "status",
            "total_debit",
            "total_credit",
            "created_at",
        ]

    def validate_lines(self, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not lines:
            raise serializers.ValidationError("A journal entry needs at least one line.")
        debit = sum(
            (ln["amount"] for ln in lines if ln["side"] == JournalLine.Side.DEBIT), Decimal("0")
        )
        credit = sum(
            (ln["amount"] for ln in lines if ln["side"] == JournalLine.Side.CREDIT), Decimal("0")
        )
        if debit != credit:
            raise serializers.ValidationError(
                f"Entry does not balance: debits={debit} credits={credit}."
            )
        return lines

    def create(self, validated_data: dict[str, Any]) -> JournalEntry:
        lines = validated_data.pop("lines")
        entry = JournalEntry.objects.create(**validated_data)
        entry.entry_number = f"JE-{entry.organization_id}-{entry.pk:06d}"
        entry.save(update_fields=["entry_number"])
        JournalLine.objects.bulk_create(JournalLine(entry=entry, **line) for line in lines)
        return entry


class CreditProfileSerializer(serializers.ModelSerializer):
    creditor_name = serializers.CharField(source="creditor.name", read_only=True)
    debtor_name = serializers.CharField(source="debtor.name", read_only=True)

    class Meta:
        model = CreditProfile
        fields = [
            "id",
            "creditor",
            "creditor_name",
            "debtor",
            "debtor_name",
            "credit_limit",
            "terms_days",
            "status",
            "hold_reason",
            "created_at",
            "updated_at",
        ]
        # Limit/terms/hold changes only ever happen through the approval flow.
        read_only_fields = [
            "id",
            "credit_limit",
            "terms_days",
            "status",
            "hold_reason",
            "created_at",
            "updated_at",
        ]


class SupplierBillPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierBillPayment
        fields = ["id", "amount", "method", "reference", "paid_at"]
        read_only_fields = ["id", "paid_at"]


class SupplierBillSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    amount_due = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    payments = SupplierBillPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierBill
        fields = [
            "id",
            "organization",
            "supplier",
            "supplier_name",
            "bill_number",
            "bill_date",
            "due_date",
            "total_amount",
            "amount_paid",
            "amount_due",
            "status",
            "reference_type",
            "reference_id",
            "notes",
            "payments",
            "created_at",
        ]
        read_only_fields = ["id", "amount_paid", "amount_due", "status", "payments", "created_at"]


class AccountingPeriodSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    closed_by_name = serializers.CharField(source="closed_by.username", read_only=True)

    class Meta:
        model = AccountingPeriod
        fields = [
            "id",
            "organization",
            "organization_name",
            "kind",
            "start_date",
            "end_date",
            "status",
            "closing_totals",
            "closed_by",
            "closed_by_name",
            "closed_at",
            "reopened_at",
            "notes",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "closing_totals",
            "closed_by",
            "closed_at",
            "reopened_at",
            "created_at",
        ]


class BankAccountSerializer(serializers.ModelSerializer):
    gl_account_code = serializers.CharField(source="gl_account.code", read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "organization",
            "name",
            "kind",
            "bank_name",
            "account_number",
            "currency",
            "opening_balance",
            "gl_account",
            "gl_account_code",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "gl_account", "gl_account_code", "created_at"]
