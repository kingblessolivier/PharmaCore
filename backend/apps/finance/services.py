"""Finance services: chart-of-accounts bootstrap, balanced journal posting,
auto-posting from B2B settlement, and the credit-override approval handler."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.utils import timezone

from apps.approvals import registry
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import request_approval
from apps.finance.models import (
    Account,
    BankAccount,
    CreditProfile,
    JournalEntry,
    JournalLine,
    SupplierBill,
    SupplierBillPayment,
)
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User

# Standard control accounts, auto-vivified per organization the first time they're
# needed (code, name, type, normal_balance).
_CONTROL_ACCOUNTS: list[tuple[str, str, str, str]] = [
    ("1000", "Cash & Bank", Account.Type.ASSET, Account.Balance.DEBIT),
    ("1100", "Accounts Receivable", Account.Type.ASSET, Account.Balance.DEBIT),
    ("2000", "Accounts Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2100", "PAYE Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2200", "RSSB Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2300", "CBHI Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2400", "Net Pay Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("3000", "Owner's Equity", Account.Type.EQUITY, Account.Balance.CREDIT),
    ("4000", "Sales Revenue", Account.Type.REVENUE, Account.Balance.CREDIT),
    ("5000", "Cost of Goods Sold", Account.Type.EXPENSE, Account.Balance.DEBIT),
    ("6000", "Salaries & Wages Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
    ("6100", "Payroll Employer Contributions Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
]


def ensure_default_accounts(organization: Organization) -> dict[str, Account]:
    """Idempotently create the standard control accounts for an org's books."""
    by_code: dict[str, Account] = {}
    for code, name, acc_type, normal_balance in _CONTROL_ACCOUNTS:
        account, _ = Account.objects.get_or_create(
            organization=organization,
            code=code,
            defaults={
                "name": name,
                "account_type": acc_type,
                "normal_balance": normal_balance,
                "is_system": True,
            },
        )
        by_code[code] = account
    return by_code


class JournalLineInput(TypedDict):
    account: Account
    side: str
    amount: Decimal
    memo: str


@transaction.atomic
def post_journal(
    *,
    organization: Organization,
    entry_date: Any = None,
    description: str = "",
    lines: list[JournalLineInput],
    reference_type: str = "",
    reference_id: str = "",
    user: User | None = None,
) -> JournalEntry:
    """Create a balanced journal entry. Raises ValueError if debits != credits."""
    debit = sum(
        (ln["amount"] for ln in lines if ln["side"] == JournalLine.Side.DEBIT), Decimal("0")
    )
    credit = sum(
        (ln["amount"] for ln in lines if ln["side"] == JournalLine.Side.CREDIT), Decimal("0")
    )
    if not lines or debit != credit:
        raise ValueError(f"Journal entry does not balance: debits={debit} credits={credit}.")

    entry = JournalEntry.objects.create(
        organization=organization,
        entry_date=entry_date or timezone.now().date(),
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        posted_by=user,
    )
    entry.entry_number = f"JE-{organization.pk}-{entry.pk:06d}"
    entry.save(update_fields=["entry_number"])
    JournalLine.objects.bulk_create(
        JournalLine(
            entry=entry,
            account=ln["account"],
            side=ln["side"],
            amount=ln["amount"],
            memo=ln.get("memo", ""),
        )
        for ln in lines
    )
    return entry


def post_payment_journal(*, order: Any, amount: Decimal, user: User | None) -> None:
    """Auto-post a B2B settlement payment to both parties' books.

    Depot (seller) books: Dr Cash & Bank / Cr Accounts Receivable.
    Retail (buyer) books: Dr Accounts Payable / Cr Cash & Bank.
    """
    depot_accounts = ensure_default_accounts(order.depot)
    post_journal(
        organization=order.depot,
        description=f"Settlement received for {order.order_number}",
        lines=[
            {
                "account": depot_accounts["1000"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": "",
            },
            {
                "account": depot_accounts["1100"],
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": "",
            },
        ],
        reference_type="stock_order",
        reference_id=str(order.pk),
        user=user,
    )
    retail_accounts = ensure_default_accounts(order.retail)
    post_journal(
        organization=order.retail,
        description=f"Settlement paid for {order.order_number}",
        lines=[
            {
                "account": retail_accounts["2000"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": "",
            },
            {
                "account": retail_accounts["1000"],
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": "",
            },
        ],
        reference_type="stock_order",
        reference_id=str(order.pk),
        user=user,
    )


def post_payroll_journal(
    *,
    organization: Organization,
    period_label: str,
    total_gross: Decimal,
    total_paye: Decimal,
    total_rssb_employee: Decimal,
    total_rssb_employer: Decimal,
    total_cbhi: Decimal,
    total_net_pay: Decimal,
    user: User | None,
    reference_id: str = "",
) -> None:
    """Auto-post a payroll run to the GL: gross expense funds statutory payables +
    net-pay payable; employer-side RSSB contributions post as a second, separate
    expense (never mixed with the employee-withheld portion)."""
    accounts = ensure_default_accounts(organization)
    post_journal(
        organization=organization,
        description=f"Payroll — {period_label}",
        lines=[
            {
                "account": accounts["6000"],
                "side": JournalLine.Side.DEBIT,
                "amount": total_gross,
                "memo": "",
            },
            {
                "account": accounts["2100"],
                "side": JournalLine.Side.CREDIT,
                "amount": total_paye,
                "memo": "PAYE",
            },
            {
                "account": accounts["2200"],
                "side": JournalLine.Side.CREDIT,
                "amount": total_rssb_employee,
                "memo": "RSSB (employee)",
            },
            {
                "account": accounts["2300"],
                "side": JournalLine.Side.CREDIT,
                "amount": total_cbhi,
                "memo": "CBHI",
            },
            {
                "account": accounts["2400"],
                "side": JournalLine.Side.CREDIT,
                "amount": total_net_pay,
                "memo": "Net pay",
            },
        ],
        reference_type="payroll_run",
        reference_id=reference_id,
        user=user,
    )
    if total_rssb_employer > 0:
        post_journal(
            organization=organization,
            description=f"Payroll employer contributions — {period_label}",
            lines=[
                {
                    "account": accounts["6100"],
                    "side": JournalLine.Side.DEBIT,
                    "amount": total_rssb_employer,
                    "memo": "",
                },
                {
                    "account": accounts["2200"],
                    "side": JournalLine.Side.CREDIT,
                    "amount": total_rssb_employer,
                    "memo": "RSSB (employer)",
                },
            ],
            reference_type="payroll_run",
            reference_id=reference_id,
            user=user,
        )


def request_credit_override(
    *,
    credit_profile: CreditProfile,
    requested_by: User,
    new_limit: Decimal | None = None,
    new_terms_days: int | None = None,
    lift_hold: bool = False,
    put_on_hold: bool = False,
    hold_reason: str = "",
    reason: str = "",
) -> ApprovalRequest:
    """Propose a change to a customer's credit limit/terms/hold — routed through
    the approvals engine rather than applied directly (no self-approval)."""
    payload: dict[str, Any] = {}
    if new_limit is not None:
        payload["credit_limit"] = str(new_limit)
    if new_terms_days is not None:
        payload["terms_days"] = new_terms_days
    if lift_hold:
        payload["status"] = CreditProfile.Status.ACTIVE
    if put_on_hold:
        payload["status"] = CreditProfile.Status.HOLD
        payload["hold_reason"] = hold_reason
    return request_approval(
        resource_type="finance.credit_override",
        resource_id=str(credit_profile.pk),
        organization=credit_profile.creditor,
        requested_by=requested_by,
        payload=payload,
        reason=reason,
    )


@registry.register("finance.credit_override")
def _apply_credit_override(approval: ApprovalRequest) -> None:
    profile = CreditProfile.objects.get(pk=int(approval.resource_id))
    payload = approval.payload
    fields: list[str] = []
    if "credit_limit" in payload:
        profile.credit_limit = Decimal(payload["credit_limit"])
        fields.append("credit_limit")
    if "terms_days" in payload:
        profile.terms_days = int(payload["terms_days"])
        fields.append("terms_days")
    if "status" in payload:
        profile.status = payload["status"]
        fields.append("status")
        if payload["status"] == CreditProfile.Status.HOLD:
            profile.hold_reason = payload.get("hold_reason", "")
            fields.append("hold_reason")
        else:
            profile.hold_reason = ""
            fields.append("hold_reason")
    if fields:
        profile.save(update_fields=[*fields, "updated_at"])
    record_audit(
        action="CREDIT_OVERRIDE_APPLIED",
        user=approval.decided_by,
        organization=profile.creditor,
        entity_type="credit_profile",
        entity_id=str(profile.pk),
        changes=payload,
    )


@transaction.atomic
def record_supplier_bill(
    *,
    organization: Organization,
    supplier: Any,
    bill_number: str,
    bill_date: Any,
    due_date: Any,
    total_amount: Decimal,
    reference_type: str = "",
    reference_id: str = "",
    notes: str = "",
    user: User | None = None,
) -> SupplierBill:
    """Record a supplier invoice (AP) and post it to the GL: Dr an expense/asset
    account, Cr Accounts Payable — the liability is recognised the moment the bill
    is booked, before any cash moves."""
    bill = SupplierBill.objects.create(
        organization=organization,
        supplier=supplier,
        bill_number=bill_number,
        bill_date=bill_date,
        due_date=due_date,
        total_amount=total_amount,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
        created_by=user,
    )
    accounts = ensure_default_accounts(organization)
    post_journal(
        organization=organization,
        entry_date=bill_date,
        description=f"Supplier bill {bill.bill_number or bill.pk} — {supplier.name}",
        lines=[
            {
                "account": accounts["5000"],
                "side": JournalLine.Side.DEBIT,
                "amount": total_amount,
                "memo": "",
            },
            {
                "account": accounts["2000"],
                "side": JournalLine.Side.CREDIT,
                "amount": total_amount,
                "memo": "",
            },
        ],
        reference_type="supplier_bill",
        reference_id=str(bill.pk),
        user=user,
    )
    return bill


@transaction.atomic
def record_supplier_bill_payment(
    *, bill: SupplierBill, amount: Decimal, method: str, reference: str, user: User | None
) -> SupplierBill:
    """Record a payment against a supplier bill and roll up its settlement status;
    posts Dr Accounts Payable / Cr Cash & Bank."""
    if amount <= 0:
        raise ValueError("Payment amount must be positive.")
    SupplierBillPayment.objects.create(
        bill=bill, amount=amount, method=method, reference=reference, recorded_by=user
    )
    bill.amount_paid = bill.amount_paid + amount
    if bill.amount_paid >= bill.total_amount:
        bill.status = SupplierBill.Status.PAID
    elif bill.amount_paid > 0:
        bill.status = SupplierBill.Status.PARTIAL
    bill.save(update_fields=["amount_paid", "status", "updated_at"])

    accounts = ensure_default_accounts(bill.organization)
    post_journal(
        organization=bill.organization,
        description=f"Payment on supplier bill {bill.bill_number or bill.pk}",
        lines=[
            {
                "account": accounts["2000"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": "",
            },
            {
                "account": accounts["1000"],
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": "",
            },
        ],
        reference_type="supplier_bill",
        reference_id=str(bill.pk),
        user=user,
    )
    return bill


@transaction.atomic
def create_bank_account(
    *,
    organization: Organization,
    name: str,
    kind: str,
    bank_name: str = "",
    account_number: str = "",
    currency: str = "RWF",
    opening_balance: Decimal = Decimal("0"),
    user: User | None = None,
) -> BankAccount:
    """Open a bank/MoMo/Airtel/cash account — creates its own GL sub-account under
    the "1000 Cash & Bank" control account so its cash-book is tracked separately,
    and posts an opening-balance entry if one is given."""
    control = ensure_default_accounts(organization)
    existing = BankAccount.objects.filter(organization=organization).count()
    gl_account = Account.objects.create(
        organization=organization,
        code=f"1000-{existing + 1:02d}",
        name=name,
        account_type=Account.Type.ASSET,
        normal_balance=Account.Balance.DEBIT,
        parent=control["1000"],
    )
    account = BankAccount.objects.create(
        organization=organization,
        name=name,
        kind=kind,
        bank_name=bank_name,
        account_number=account_number,
        currency=currency,
        opening_balance=opening_balance,
        gl_account=gl_account,
    )
    if opening_balance != 0:
        post_journal(
            organization=organization,
            description=f"Opening balance — {name}",
            lines=[
                {
                    "account": gl_account,
                    "side": JournalLine.Side.DEBIT,
                    "amount": opening_balance,
                    "memo": "Opening balance",
                },
                {
                    "account": control["3000"],
                    "side": JournalLine.Side.CREDIT,
                    "amount": opening_balance,
                    "memo": "Opening balance",
                },
            ],
            reference_type="bank_account",
            reference_id=str(account.pk),
            user=user,
        )
    return account


def cash_book_lines(bank_account: BankAccount) -> list[dict[str, Any]]:
    """The running ledger (cash-book) for one bank account: every journal line
    posted to its GL sub-account, oldest first, with a running balance.

    Starts at 0, not ``opening_balance`` — the opening balance is itself posted
    as a journal line by ``create_bank_account``, so seeding the running total
    with it too would double-count it."""
    lines = (
        JournalLine.objects.filter(account=bank_account.gl_account)
        .select_related("entry")
        .order_by("entry__entry_date", "entry_id", "id")
    )
    running = Decimal("0")
    rows: list[dict[str, Any]] = []
    for line in lines:
        running += line.amount if line.side == JournalLine.Side.DEBIT else -line.amount
        rows.append(
            {
                "line_id": line.pk,
                "entry_date": line.entry.entry_date,
                "entry_number": line.entry.entry_number,
                "description": line.entry.description,
                "side": line.side,
                "amount": line.amount,
                "running_balance": running,
                "is_reconciled": line.is_reconciled,
                "reconciled_at": line.reconciled_at,
                "statement_reference": line.statement_reference,
            }
        )
    return rows


def reconcile_lines(*, line_ids: list[int], statement_reference: str, user: User | None) -> int:
    """Mark journal lines as matched against a bank/MoMo statement. Returns the
    count reconciled."""
    updated = JournalLine.objects.filter(pk__in=line_ids, is_reconciled=False).update(
        is_reconciled=True, reconciled_at=timezone.now(), statement_reference=statement_reference
    )
    if updated:
        record_audit(
            action="RECONCILE",
            user=user,
            entity_type="journal_line",
            entity_id=",".join(str(i) for i in line_ids),
            changes={"statement_reference": statement_reference, "count": updated},
        )
    return updated


def cash_flow_forecast(organization: Organization) -> dict[str, Any]:
    """A real (not simulated) cash-flow projection: current cash on hand, plus
    expected inflows (unpaid B2B receivables where this org is the depot) and
    outflows (unpaid supplier bills), bucketed by how soon they're due."""
    from apps.distribution.models import StockOrder

    today = timezone.now().date()
    buckets = ["d30", "d60", "d90", "over90"]
    empty = dict.fromkeys(buckets, Decimal("0"))

    def bucket_for(due: Any) -> str:
        days = (due - today).days if due else 999
        if days <= 30:
            return "d30"
        if days <= 60:
            return "d60"
        if days <= 90:
            return "d90"
        return "over90"

    inflows = dict(empty)
    for order in StockOrder.objects.filter(depot=organization).exclude(
        payment_status=StockOrder.PaymentStatus.PAID
    ):
        due = Decimal(str(order.amount_due))
        if due > 0:
            inflows[bucket_for(order.payment_due_date)] += due

    outflows = dict(empty)
    for bill in SupplierBill.objects.filter(organization=organization).exclude(
        status=SupplierBill.Status.PAID
    ):
        if bill.amount_due > 0:
            outflows[bucket_for(bill.due_date)] += bill.amount_due

    cash_on_hand = Decimal("0")
    for acc in BankAccount.objects.filter(organization=organization, is_active=True):
        rows = cash_book_lines(acc)
        cash_on_hand += rows[-1]["running_balance"] if rows else acc.opening_balance

    running = cash_on_hand
    projection = []
    for b in buckets:
        running = running + inflows[b] - outflows[b]
        projection.append(
            {
                "bucket": b,
                "inflows": inflows[b],
                "outflows": outflows[b],
                "projected_balance": running,
            }
        )

    return {"cash_on_hand": cash_on_hand, "projection": projection}
