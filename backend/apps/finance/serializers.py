from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from rest_framework import serializers

from apps.finance.models import (
    Account,
    AccountingPeriod,
    BankAccount,
    BankStatement,
    BankStatementLine,
    Budget,
    BudgetLine,
    CostCentre,
    CreditProfile,
    CustomerCredit,
    CustomerInvoice,
    CustomerReceipt,
    DunningNotice,
    FixedAsset,
    JournalEntry,
    JournalLine,
    PaymentRun,
    PaymentRunLine,
    PeriodTask,
    SupplierBill,
    SupplierBillPayment,
    TaxCode,
    TaxPayment,
    TaxRecord,
    TenantSettings,
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
            # The statements read this; without it on the API there is no way to
            # correct a misclassified account from the chart of accounts screen.
            "classification",
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
    cost_centre_code = serializers.CharField(source="cost_centre.code", read_only=True)
    cost_centre_name = serializers.CharField(source="cost_centre.name", read_only=True)

    class Meta:
        model = JournalLine
        fields = [
            "id",
            "account",
            "account_code",
            "account_name",
            # The analysis dimension. Optional on control-account legs, which
            # belong to the entity rather than to any one branch.
            "cost_centre",
            "cost_centre_code",
            "cost_centre_name",
            "side",
            "amount",
            "memo",
            "is_reconciled",
        ]
        read_only_fields = ["id", "is_reconciled"]


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
            # Which part of the business produced this posting — the one field
            # that separates a system posting from something typed at midnight.
            "source_module",
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
            "vat_amount",
            "tax_class",
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


class TaxCodeSerializer(serializers.ModelSerializer):
    """A Rwanda VAT tax class (A/B/C/D) with its effective-dated rate."""

    class Meta:
        model = TaxCode
        fields = [
            "id",
            "organization",
            "code",
            "description",
            "rate_pct",
            "withholding_pct",
            "effective_from",
            "effective_to",
            "is_active",
            "source_reference",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TaxPaymentSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, default=None
    )

    class Meta:
        model = TaxPayment
        fields = [
            "id",
            "organization",
            "organization_name",
            "payment_number",
            "paid_on",
            "period_start",
            "period_end",
            "amount",
            "method",
            "rra_reference",
            "notes",
            "created_by",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "payment_number", "created_by", "created_by_name", "created_at"]


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


class FixedAssetSerializer(serializers.ModelSerializer):
    net_book_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    annual_depreciation = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = FixedAsset
        fields = [
            "id",
            "organization",
            "organization_name",
            "asset_number",
            "name",
            "category",
            "acquisition_date",
            "acquisition_cost",
            "useful_life_years",
            "salvage_value",
            "accumulated_depreciation",
            "net_book_value",
            "annual_depreciation",
            "is_active",
            "disposal_date",
            "disposal_amount",
            "disposal_reason",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "net_book_value",
            "annual_depreciation",
            "disposal_date",
            "disposal_amount",
            "disposal_reason",
            "created_at",
        ]


class TaxRecordSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = TaxRecord
        fields = [
            "id",
            "organization",
            "organization_name",
            "receipt_number",
            "sdc_id",
            "mrc_number",
            "taxable_amount",
            "vat_amount",
            "tax_class_a",
            "tax_class_b",
            "tax_class_c",
            "qr_code_payload",
            "fiscalized_at",
        ]
        read_only_fields = ["id", "fiscalized_at"]


class TenantSettingsSerializer(serializers.ModelSerializer):
    """Per-organization configuration. There is exactly one row per organization,
    lazily created on first read."""

    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = TenantSettings
        fields = [
            "id",
            "organization",
            "organization_name",
            "base_currency",
            "fx_provider",
            "costing_method",
            "pay_period",
            "statutory_remittance_day",
            "pit_filing_deadline_month",
            "pit_filing_deadline_day",
            "default_country",
            "timezone",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]


class CostCentreSerializer(serializers.ModelSerializer):
    """The ledger's analysis dimension."""

    parent_name = serializers.CharField(source="parent.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    manager_name = serializers.CharField(source="manager.get_full_name", read_only=True)
    path = serializers.CharField(read_only=True)

    class Meta:
        model = CostCentre
        fields = [
            "id",
            "organization",
            "code",
            "name",
            "kind",
            "parent",
            "parent_name",
            "path",
            "department",
            "department_name",
            "branch",
            "branch_name",
            "manager",
            "manager_name",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "path", "created_at"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """A centre may not be its own ancestor — a cycle would hang every roll-up."""
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if parent is not None and self.instance is not None:
            instance = cast(Any, self.instance)
            node, seen = parent, set()
            while node is not None and node.pk not in seen:
                if node.pk == instance.pk:
                    raise serializers.ValidationError(
                        {"parent": "A cost centre cannot roll up into itself."}
                    )
                seen.add(node.pk)
                node = node.parent
        return attrs


class BudgetLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    cost_centre_name = serializers.CharField(source="cost_centre.name", read_only=True)

    class Meta:
        model = BudgetLine
        fields = [
            "id",
            "account",
            "account_code",
            "account_name",
            "cost_centre",
            "cost_centre_name",
            "period_month",
            "amount",
            "note",
        ]
        read_only_fields = ["id"]

    def validate_period_month(self, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 12:
            raise serializers.ValidationError(
                "Month must be between 1 and 12, or blank for an annual figure."
            )
        return value


class BudgetSerializer(serializers.ModelSerializer):
    """A budget header with its lines.

    There is no `actual` field anywhere in here. Actuals come from the ledger via
    the `variance` action — see apps/finance/budgeting.py.
    """

    lines = BudgetLineSerializer(many=True, required=False)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True)
    line_count = serializers.IntegerField(source="lines.count", read_only=True)
    total_budgeted = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            "id",
            "organization",
            "name",
            "financial_year",
            "year_starts_month",
            "status",
            "notes",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "line_count",
            "total_budgeted",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "approved_by",
            "approved_at",
            "line_count",
            "total_budgeted",
            "created_at",
            "updated_at",
        ]

    def get_total_budgeted(self, obj: Budget) -> str:
        return str(sum((line.amount for line in obj.lines.all()), Decimal("0.00")))

    def create(self, validated_data: dict[str, Any]) -> Budget:
        lines = validated_data.pop("lines", [])
        budget = Budget.objects.create(**validated_data)
        for line in lines:
            BudgetLine.objects.create(budget=budget, **line)
        return budget

    def update(self, instance: Budget, validated_data: dict[str, Any]) -> Budget:
        lines = validated_data.pop("lines", None)
        if lines is not None and not instance.is_editable:
            raise serializers.ValidationError(
                {"lines": f"A {instance.get_status_display().lower()} budget cannot be re-planned."}
            )
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for line in lines:
                BudgetLine.objects.create(budget=instance, **line)
        return instance


class PeriodTaskSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.CharField(source="completed_by.get_full_name", read_only=True)
    is_settled = serializers.BooleanField(read_only=True)

    class Meta:
        model = PeriodTask
        fields = [
            "id",
            "period",
            "code",
            "title",
            "description",
            "sequence",
            "is_blocking",
            "status",
            "is_settled",
            "completed_by",
            "completed_by_name",
            "completed_at",
            "notes",
        ]
        read_only_fields = ["id", "is_settled", "completed_by", "completed_at"]


class CustomerReceiptSerializer(serializers.ModelSerializer):
    """Money received against an invoice. Posting is done by the service layer,
    so everything but the payment details is read-only."""

    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    customer_name = serializers.CharField(source="invoice.customer.name", read_only=True)

    class Meta:
        model = CustomerReceipt
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "customer_name",
            "receipt_number",
            "amount",
            "method",
            "reference",
            "received_on",
            "created_at",
        ]
        read_only_fields = ["id", "receipt_number", "created_at"]


class CustomerInvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    amount_due = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    receipts = CustomerReceiptSerializer(many=True, read_only=True)
    days_past_due = serializers.SerializerMethodField()

    class Meta:
        model = CustomerInvoice
        fields = [
            "id",
            "organization",
            "organization_name",
            "customer",
            "customer_name",
            "invoice_number",
            "invoice_date",
            "due_date",
            "total_amount",
            "vat_amount",
            "tax_class",
            "amount_paid",
            "amount_due",
            "status",
            "days_past_due",
            "reference_type",
            "reference_id",
            "notes",
            "receipts",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "invoice_number",
            "amount_paid",
            "amount_due",
            "status",
            "days_past_due",
            "receipts",
            "created_at",
        ]

    def get_days_past_due(self, obj: CustomerInvoice) -> int:
        """Negative until the due date passes — the sign tells you which side of
        the deadline the invoice sits on."""
        from django.utils import timezone

        return (timezone.now().date() - obj.due_date).days


class CustomerCreditSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = CustomerCredit
        fields = [
            "id",
            "organization",
            "customer",
            "customer_name",
            "amount",
            "balance",
            "source",
            "source_receipt",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class DunningNoticeSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    customer_name = serializers.CharField(source="invoice.customer.name", read_only=True)

    class Meta:
        model = DunningNotice
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "customer_name",
            "level",
            "days_past_due",
            "amount_due",
            "sent_on",
            "created_at",
        ]
        read_only_fields = fields


class PaymentRunLineSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="bill.supplier.name", read_only=True)
    bill_number = serializers.CharField(source="bill.bill_number", read_only=True)
    idempotency_key = serializers.CharField(read_only=True)

    class Meta:
        model = PaymentRunLine
        fields = [
            "id",
            "bill",
            "bill_number",
            "supplier_name",
            "amount",
            "payee_name",
            "payee_account",
            "paid",
            "idempotency_key",
        ]
        read_only_fields = fields


class PaymentRunSerializer(serializers.ModelSerializer):
    lines = PaymentRunLineSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    line_count = serializers.IntegerField(read_only=True)
    # The file body can be large; the list view only needs to know it exists.
    has_disbursement_file = serializers.SerializerMethodField()

    class Meta:
        model = PaymentRun
        fields = [
            "id",
            "organization",
            "organization_name",
            "run_number",
            "method",
            "status",
            "scheduled_for",
            "total_amount",
            "approvals_required",
            "approvals_received",
            "approved_at",
            "disbursed_at",
            "locked_at",
            "disbursement_filename",
            "has_disbursement_file",
            "notes",
            "line_count",
            "lines",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "run_number",
            "status",
            "total_amount",
            "approvals_required",
            "approvals_received",
            "approved_at",
            "disbursed_at",
            "locked_at",
            "disbursement_filename",
            "has_disbursement_file",
            "line_count",
            "lines",
            "created_at",
        ]

    def get_has_disbursement_file(self, obj: PaymentRun) -> bool:
        return bool(obj.disbursement_file)


class BankStatementLineSerializer(serializers.ModelSerializer):
    """One line the bank reported. `amount` is signed from our point of view."""

    is_settled = serializers.BooleanField(read_only=True)
    matched_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    matched_line_ids = serializers.SerializerMethodField()

    class Meta:
        model = BankStatementLine
        fields = [
            "id",
            "statement",
            "line_date",
            "description",
            "reference",
            "amount",
            "balance",
            "external_id",
            "status",
            "is_settled",
            "matched_total",
            "matched_line_ids",
            "note",
        ]
        read_only_fields = ["id", "statement", "status", "is_settled", "matched_total"]

    def get_matched_line_ids(self, obj: BankStatementLine) -> list[int]:
        return [m.journal_line_id for m in obj.matches.all()]


class BankStatementSerializer(serializers.ModelSerializer):
    bank_account_name = serializers.CharField(source="bank_account.name", read_only=True)
    imported_by_name = serializers.CharField(source="imported_by.get_full_name", read_only=True)
    line_count = serializers.IntegerField(source="lines.count", read_only=True)
    movement = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = BankStatement
        fields = [
            "id",
            "bank_account",
            "bank_account_name",
            "reference",
            "start_date",
            "end_date",
            "opening_balance",
            "closing_balance",
            "movement",
            "status",
            "source_filename",
            "notes",
            "line_count",
            "imported_by",
            "imported_by_name",
            "imported_at",
            "reconciled_by",
            "reconciled_at",
        ]
        read_only_fields = [
            "id",
            "movement",
            "status",
            "line_count",
            "imported_by",
            "imported_at",
            "reconciled_by",
            "reconciled_at",
        ]
