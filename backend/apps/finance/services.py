"""Finance services: chart-of-accounts bootstrap, balanced journal posting,
auto-posting from B2B settlement, and the credit-override approval handler."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.utils import timezone

from apps.approvals import registry
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import request_approval
from apps.core.sequences import next_number
from apps.finance.models import (
    Account,
    AccountingPeriod,
    BankAccount,
    CreditProfile,
    CustomerCredit,
    CustomerInvoice,
    CustomerReceipt,
    DunningNotice,
    JournalEntry,
    JournalLine,
    OpeningBalance,
    PaymentRun,
    PaymentRunLine,
    SupplierBill,
    SupplierBillPayment,
    TenantSettings,
)
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User

# Standard control accounts, auto-vivified per organization the first time they're
# needed (code, name, type, normal_balance). See PR F3 (roadmap §F3) for the full
# Rwanda statutory sub-ledger chart of accounts — every statutory liability gets
# its own 2200-level account so the RRA sub-ledger reconciles per statute.
_CONTROL_ACCOUNTS: list[tuple[str, str, str, str]] = [
    # Cash & equivalents (three buckets: physical cash, bank, mobile money).
    ("1100", "Cash on Hand", Account.Type.ASSET, Account.Balance.DEBIT),
    ("1200", "Bank", Account.Type.ASSET, Account.Balance.DEBIT),
    ("1300", "Mobile Money", Account.Type.ASSET, Account.Balance.DEBIT),
    # VAT charged by suppliers, recoverable from the RRA on the next return —
    # an asset, and the input side of every VAT return.
    ("1350", "VAT Input — Recoverable", Account.Type.ASSET, Account.Balance.DEBIT),
    ("1400", "Accounts Receivable — Trade", Account.Type.ASSET, Account.Balance.DEBIT),
    ("1500", "Inventory on Hand", Account.Type.ASSET, Account.Balance.DEBIT),
    ("1700", "Fixed Assets (cost)", Account.Type.ASSET, Account.Balance.DEBIT),
    ("1701", "Accumulated Depreciation", Account.Type.ASSET, Account.Balance.CREDIT),
    # Trade payables.
    ("2100", "Accounts Payable — Trade", Account.Type.LIABILITY, Account.Balance.CREDIT),
    # Money held for a customer but not yet earned (overpayments, credit notes,
    # returns). Kept out of 2100 so the AP ageing is purely supplier debt.
    (
        # 2150 is taken by Procurement's GRNI control account.
        "2160",
        "Customer Deposits & On-Account Credits",
        Account.Type.LIABILITY,
        Account.Balance.CREDIT,
    ),
    # Statutory sub-ledger — Rwanda (employee/employer portions each post to a
    # distinct account so the RRA returns tie out line-by-line).
    ("2200", "PAYE Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2210", "RSSB Pension Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2220", "RSSB Maternity Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2230", "CBHI Payable", Account.Type.ASSET, Account.Balance.DEBIT),
    ("2240", "Occupational Hazards Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2250", "RAMA Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    # Tax + regulatory liabilities (output VAT, EBM device-levy, WHT).
    ("2300", "VAT Payable (Output)", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2400", "EBM Liability", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2500", "WHT Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    # Net pay cleared on payment — interim holding account for the
    # payroll run's payable before funds disburse.
    ("2600", "Net Pay Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    # Equity.
    ("3000", "Owner's Equity", Account.Type.EQUITY, Account.Balance.CREDIT),
    # Revenue — split by channel so gross-margin reports can roll up cleanly.
    ("4100", "Retail Revenue", Account.Type.REVENUE, Account.Balance.CREDIT),
    ("4200", "Wholesale Revenue", Account.Type.REVENUE, Account.Balance.CREDIT),
    ("4300", "Services Revenue", Account.Type.REVENUE, Account.Balance.CREDIT),
    # Cost of sales / inventory adjustments / shrinkage.
    ("5000", "Cost of Goods Sold", Account.Type.EXPENSE, Account.Balance.DEBIT),
    ("5100", "Inventory Adjustments", Account.Type.EXPENSE, Account.Balance.DEBIT),
    ("5900", "Shrinkage Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
    # Payroll — employee-side gross salary + employer statutory contributions.
    # Each employer-side contribution posts to its own 61xx account so the
    # P&L by cost-line is auditable.
    ("6100", "Salaries & Wages Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
    ("6110", "Employer RSSB Pension Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
    ("6120", "Employer Maternity Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
    ("6130", "Occupational Hazards Insurance Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
    ("6140", "RAMA Employer Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
    # Statutory tax expense (corporate income tax — distinct from withholding).
    ("7000", "Tax Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
    # Realised FX difference between the rate a foreign bill was booked at and
    # the rate it was settled at. A gain posts as a credit to the same account.
    ("7100", "FX Gain / Loss", Account.Type.EXPENSE, Account.Balance.DEBIT),
]


# Pre-F3 codes that were renamed/restructured when the statutory sub-ledger was
# introduced. Older tenants may have rows with these codes; we rename them in
# place so the new posts (which reference new codes) do not collide and the old
# ones are not orphaned. Each tuple is ``(old_code, new_code, new_name,
# new_account_type, new_normal_balance)``; rows that match the old code but
# already carry the new code are no-ops. Idempotent: re-running is harmless.
#
# Note: the old ``2200 RSSB Payable`` row (which bundled pension+maternity
# employee contributions in a single control) is intentionally left alone —
# that liability still exists on the books, and the new payroll posts to the
# finer-grained 2210/2220/2230 accounts going forward. Same for ``2300 CBHI``.
_LEGACY_ACCOUNT_REMAP: list[tuple[str, str, str, str, str]] = [
    ("1000", "1100", "Cash on Hand", Account.Type.ASSET, Account.Balance.DEBIT),
    ("1100", "1400", "Accounts Receivable — Trade", Account.Type.ASSET, Account.Balance.DEBIT),
    ("1200", "1500", "Inventory on Hand", Account.Type.ASSET, Account.Balance.DEBIT),
    ("1300", "2400", "EBM Liability", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2000", "2100", "Accounts Payable — Trade", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2050", "2300", "VAT Payable (Output)", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2060", "2500", "WHT Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2100", "2200", "PAYE Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2400", "2600", "Net Pay Payable", Account.Type.LIABILITY, Account.Balance.CREDIT),
    ("2500", "5100", "Inventory Adjustments", Account.Type.EXPENSE, Account.Balance.DEBIT),
    ("4000", "4100", "Retail Revenue", Account.Type.REVENUE, Account.Balance.CREDIT),
    ("6000", "6100", "Salaries & Wages Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
    ("6100", "6110", "Employer RSSB Pension Expense", Account.Type.EXPENSE, Account.Balance.DEBIT),
]


def ensure_default_accounts(organization: Organization) -> dict[str, Account]:
    """Idempotently create the standard control accounts for an org's books.

    On first call for an org seeded under the pre-F3 chart, the legacy
    ``old_code`` rows are renamed to their ``new_code`` equivalents so the new
    payroll / inventory posts (which reference the new codes) land on the right
    accounts and the historical rows aren't orphaned. New orgs see only the
    post-F3 chart. Re-running on a current org is a no-op.
    """
    for old_code, new_code, new_name, new_type, new_balance in _LEGACY_ACCOUNT_REMAP:
        try:
            legacy = Account.objects.get(organization=organization, code=old_code)
        except Account.DoesNotExist:
            continue
        # Skip if the new code already exists — org already modernised, leave
        # both rows alone rather than guessing which carries the real balance.
        if Account.objects.filter(organization=organization, code=new_code).exists():
            continue
        legacy.code = new_code
        legacy.name = new_name
        legacy.account_type = new_type
        legacy.normal_balance = new_balance
        legacy.save(update_fields=["code", "name", "account_type", "normal_balance", "updated_at"])

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


class PeriodClosedError(ValueError):
    """Raised when something tries to post into a closed accounting period."""


def assert_period_open(organization: Organization, day: Any) -> None:
    """Refuse to touch a period that has been closed out.

    This is the whole point of a close: once EOM is signed off, the month's numbers
    are final. Without this check the close would be decorative.
    """
    if AccountingPeriod.objects.filter(
        organization=organization,
        status=AccountingPeriod.Status.CLOSED,
        start_date__lte=day,
        end_date__gte=day,
    ).exists():
        raise PeriodClosedError(
            f"The accounting period covering {day} is closed. "
            "Reopen it, or date the entry in an open period."
        )


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
    """Create a balanced journal entry. Raises ValueError if debits != credits, or
    PeriodClosedError if the entry would land inside a closed period.

    Idempotent on ``(organization, reference_type, reference_id)`` when a
    reference is supplied (ADR-011 contract): a re-run with the same source
    doc id returns the existing posted entry instead of creating a duplicate.
    Manual / adjustment postings (``reference_type == ""``) are not deduplicated.
    """
    debit = sum(
        (ln["amount"] for ln in lines if ln["side"] == JournalLine.Side.DEBIT), Decimal("0")
    )
    credit = sum(
        (ln["amount"] for ln in lines if ln["side"] == JournalLine.Side.CREDIT), Decimal("0")
    )
    if not lines or debit != credit:
        raise ValueError(f"Journal entry does not balance: debits={debit} credits={credit}.")

    # Idempotency check — only when we have a meaningful reference. Empty
    # ``reference_type`` is reserved for manual postings / adjustments which
    # legitimately do not deduplicate.
    if reference_type:
        existing = JournalEntry.objects.filter(
            organization=organization,
            reference_type=reference_type,
            reference_id=str(reference_id),
        ).first()
        if existing is not None:
            return existing

    assert_period_open(organization, entry_date or timezone.now().date())

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

    Depot (seller) books: Dr Cash / Cr Accounts Receivable — Trade.
    Retail (buyer) books: Dr Accounts Payable — Trade / Cr Cash.
    """
    depot_accounts = ensure_default_accounts(order.depot)
    post_journal(
        organization=order.depot,
        description=f"Settlement received for {order.order_number}",
        lines=[
            {
                "account": depot_accounts["1100"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": "",
            },
            {
                "account": depot_accounts["1400"],
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
                "account": retail_accounts["2100"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": "",
            },
            {
                "account": retail_accounts["1100"],
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
    total_pension_employee: Decimal,
    total_pension_employer: Decimal,
    total_maternity_employee: Decimal,
    total_maternity_employer: Decimal,
    total_cbhi: Decimal,
    total_occupational_hazard: Decimal,
    total_rama: Decimal,
    total_net_pay: Decimal,
    user: User | None,
    reference_id: str = "",
) -> None:
    """Auto-post a payroll run to the GL (F3 chart of accounts).

    The employee-side posting funds the per-statute 2200-level payables:

        Dr 6100 Salaries (gross)
            Cr 2200 PAYE Payable
            Cr 2210 RSSB Pension Payable  (employee share)
            Cr 2220 RSSB Maternity Payable  (employee share)
            Cr 2230 CBHI Payable
            Cr 2240 Occupational Hazards Payable
            Cr 2250 RAMA Payable
            Cr 2600 Net Pay Payable

    Each employer-side statutory contribution posts to its own 61xx expense
    account and credits the matching 22xx payable — never bundled, so the P&L
    by cost-line is auditable and the statutory sub-ledger reconciles per
    statute.
    """
    accounts = ensure_default_accounts(organization)
    employee_credit_lines: list[JournalLineInput] = [
        {
            "account": accounts["2200"],
            "side": JournalLine.Side.CREDIT,
            "amount": total_paye,
            "memo": "PAYE",
        },
        {
            "account": accounts["2210"],
            "side": JournalLine.Side.CREDIT,
            "amount": total_pension_employee,
            "memo": "RSSB pension (employee)",
        },
        {
            "account": accounts["2220"],
            "side": JournalLine.Side.CREDIT,
            "amount": total_maternity_employee,
            "memo": "RSSB maternity (employee)",
        },
        {
            "account": accounts["2230"],
            "side": JournalLine.Side.CREDIT,
            "amount": total_cbhi,
            "memo": "CBHI",
        },
    ]
    if total_occupational_hazard > 0:
        employee_credit_lines.append(
            {
                "account": accounts["2240"],
                "side": JournalLine.Side.CREDIT,
                "amount": total_occupational_hazard,
                "memo": "Occupational hazards",
            }
        )
    if total_rama > 0:
        employee_credit_lines.append(
            {
                "account": accounts["2250"],
                "side": JournalLine.Side.CREDIT,
                "amount": total_rama,
                "memo": "RAMA",
            }
        )
    employee_credit_lines.append(
        {
            "account": accounts["2600"],
            "side": JournalLine.Side.CREDIT,
            "amount": total_net_pay,
            "memo": "Net pay",
        }
    )
    post_journal(
        organization=organization,
        description=f"Payroll — {period_label}",
        lines=[
            {
                "account": accounts["6100"],
                "side": JournalLine.Side.DEBIT,
                "amount": total_gross,
                "memo": "",
            },
            *employee_credit_lines,
        ],
        reference_type="payroll_run",
        reference_id=reference_id,
        user=user,
    )
    # Each employer-side statutory posts as its own balanced entry so the P&L
    # breaks out per statute and the matching payable gets credited.
    _employer_post(
        accounts=accounts,
        organization=organization,
        period_label=period_label,
        expense_account=accounts["6110"],
        payable_account=accounts["2210"],
        amount=total_pension_employer,
        memo="RSSB pension (employer)",
        statute="RSSB_PENSION",
        reference_id=reference_id,
        user=user,
    )
    _employer_post(
        accounts=accounts,
        organization=organization,
        period_label=period_label,
        expense_account=accounts["6120"],
        payable_account=accounts["2220"],
        amount=total_maternity_employer,
        memo="RSSB maternity (employer)",
        statute="RSSB_MATERNITY",
        reference_id=reference_id,
        user=user,
    )
    if total_occupational_hazard > 0:
        _employer_post(
            accounts=accounts,
            organization=organization,
            period_label=period_label,
            expense_account=accounts["6130"],
            payable_account=accounts["2240"],
            amount=total_occupational_hazard,
            memo="Occupational hazards (employer)",
            statute="OCCUPATIONAL_HAZARDS",
            reference_id=reference_id,
            user=user,
        )
    if total_rama > 0:
        _employer_post(
            accounts=accounts,
            organization=organization,
            period_label=period_label,
            expense_account=accounts["6140"],
            payable_account=accounts["2250"],
            amount=total_rama,
            memo="RAMA (employer)",
            statute="RAMA",
            reference_id=reference_id,
            user=user,
        )


def _employer_post(
    *,
    accounts: dict[str, Account],
    organization: Organization,
    period_label: str,
    expense_account: Account,
    payable_account: Account,
    amount: Decimal,
    memo: str,
    statute: str,
    reference_id: str,
    user: User | None,
) -> None:
    """Post a single employer-side statutory contribution as its own balanced
    entry (Dr expense / Cr payable). Caller filters on ``amount > 0`` to avoid
    posting zero-valued journals that would clutter the GL.

    ``statute`` keeps each contribution's idempotency reference distinct.
    post_journal deduplicates on (organization, reference_type, reference_id),
    so sharing one reference across the whole run meant only the first of the
    five payroll entries ever reached the ledger.
    """
    if amount <= 0:
        return
    post_journal(
        organization=organization,
        description=f"Payroll employer contributions — {period_label}",
        lines=[
            {
                "account": expense_account,
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": "",
            },
            {
                "account": payable_account,
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": memo,
            },
        ],
        reference_type="payroll_employer",
        reference_id=f"{reference_id}:{statute}",
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
    vat_amount: Decimal = Decimal("0"),
    tax_class: str = "",
    reference_type: str = "",
    reference_id: str = "",
    notes: str = "",
    user: User | None = None,
) -> SupplierBill:
    """Record a supplier invoice (AP) and post it to the GL.

    If ``vat_amount`` is supplied, the entry splits:
      Dr Expense (net)   = total − vat
      Dr VAT Input       = vat           (recoverable from RRA on next return)
      Cr Accounts Payable = total

    If ``vat_amount`` is 0 (zero-rated supplier, VAT-exempt import, or legacy
    data), the entry is the legacy single-line:
      Dr Expense / Cr AP.
    """
    bill = SupplierBill.objects.create(
        organization=organization,
        supplier=supplier,
        bill_number=bill_number,
        bill_date=bill_date,
        due_date=due_date,
        total_amount=total_amount,
        vat_amount=vat_amount,
        tax_class=tax_class,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
        created_by=user,
    )
    accounts = ensure_default_accounts(organization)
    net_expense = (total_amount - vat_amount).quantize(Decimal("0.01"))
    if net_expense < 0:
        raise ValueError("vat_amount cannot exceed total_amount.")
    lines: list[JournalLineInput] = [
        {
            "account": accounts["5000"],
            "side": JournalLine.Side.DEBIT,
            "amount": net_expense,
            "memo": "Inventory / expense (net of VAT)",
        },
        {
            "account": accounts["2100"],
            "side": JournalLine.Side.CREDIT,
            "amount": total_amount,
            "memo": "",
        },
    ]
    if vat_amount > 0:
        lines.insert(
            1,
            {
                "account": accounts["1350"],
                "side": JournalLine.Side.DEBIT,
                "amount": vat_amount,
                "memo": f"VAT Input (class {tax_class or '?'})",
            },
        )
    post_journal(
        organization=organization,
        entry_date=bill_date,
        description=f"Supplier bill {bill.bill_number or bill.pk} — {supplier.name}",
        lines=lines,
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
    posts Dr Accounts Payable / Cr the account matching the tender."""
    if amount <= 0:
        raise ValueError("Payment amount must be positive.")
    payment = SupplierBillPayment.objects.create(
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
                "account": accounts["2100"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": reference,
            },
            {
                "account": accounts[_RECEIPT_ACCOUNT.get(method, "1100")],
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": method,
            },
        ],
        # Keyed on the payment, not the bill: post_journal deduplicates on the
        # reference pair, and the bill's own Dr expense / Cr AP entry already
        # owns ("supplier_bill", bill.pk) — sharing it silently swallowed every
        # payment entry, so AP was never relieved.
        reference_type="supplier_bill_payment",
        reference_id=str(payment.pk),
        user=user,
    )
    return bill


# Which cash control account a wallet's sub-ledger hangs under.
_BANK_ACCOUNT_PARENT = {
    "CASH": "1100",
    "BANK": "1200",
    "MOMO": "1300",
    "AIRTEL": "1300",
}


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
    the matching cash control account so its cash-book is tracked separately,
    and posts an opening-balance entry if one is given.

    The parent follows the tender: a MoMo wallet belongs under 1300, not under
    the bank control, so the cash-flow statement and the trial balance both see
    it in the right place.
    """
    control = ensure_default_accounts(organization)
    parent_code = _BANK_ACCOUNT_PARENT.get(kind, "1200")
    existing = Account.objects.filter(
        organization=organization, code__startswith=f"{parent_code}-"
    ).count()
    gl_account = Account.objects.create(
        organization=organization,
        code=f"{parent_code}-{existing + 1:02d}",
        name=name,
        account_type=Account.Type.ASSET,
        normal_balance=Account.Balance.DEBIT,
        parent=control[parent_code],
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


@transaction.atomic
def close_period(
    *,
    organization: Organization,
    kind: str,
    start_date: Any,
    end_date: Any,
    user: User | None,
    notes: str = "",
) -> AccountingPeriod:
    """Close an accounting period, snapshotting its headline figures.

    The snapshot matters: a closed period must report the same numbers forever, so
    the trial-balance/P&L totals are frozen onto the record rather than recomputed
    on every later read.
    """
    from apps.finance import reports

    period, _ = AccountingPeriod.objects.get_or_create(
        organization=organization,
        kind=kind,
        start_date=start_date,
        end_date=end_date,
    )
    if period.status == AccountingPeriod.Status.CLOSED:
        raise ValueError("That period is already closed.")

    tb = reports.trial_balance(organization, as_of=end_date)
    pl = reports.profit_and_loss(organization, start=start_date, end=end_date)
    bs = reports.balance_sheet(organization, as_of=end_date)
    if not tb["balanced"]:
        raise ValueError(
            "Refusing to close: the trial balance does not balance "
            f"(debits {tb['total_debit']} vs credits {tb['total_credit']})."
        )

    period.status = AccountingPeriod.Status.CLOSED
    period.closed_by = user
    period.closed_at = timezone.now()
    period.notes = notes
    period.closing_totals = {
        "total_debit": str(tb["total_debit"]),
        "total_credit": str(tb["total_credit"]),
        "revenue": str(pl["revenue"]),
        "cogs": str(pl["cogs"]),
        "gross_profit": str(pl["gross_profit"]),
        "net_profit": str(pl["net_profit"]),
        "total_assets": str(bs["total_assets"]),
        "total_liabilities": str(bs["total_liabilities"]),
        "total_equity": str(bs["total_equity"]),
    }
    period.save()
    record_audit(
        action="PERIOD_CLOSE",
        user=user,
        organization=organization,
        entity_type="accounting_period",
        entity_id=str(period.pk),
        changes=period.closing_totals,
    )

    # F2 — emit FISCAL_PERIOD_CLOSED (or EOM_CLOSE_FINALISED for MONTH-end
    # closes) on the bus. HQ consolidation in PR F8 consumes these to drive
    # intercompany eliminations; idempotent on (org, fiscal_period, period.pk).
    from apps.events.events import EventType
    from apps.events.publishers import publish_fiscal_period_event

    period_event = (
        EventType.EOM_CLOSE_FINALISED
        if kind == AccountingPeriod.Kind.MONTH
        else EventType.FISCAL_PERIOD_CLOSED
    )
    publish_fiscal_period_event(
        event=period_event,
        period_id=period.pk,
        organization=organization,
        user=user,
        kind=kind,
        start_date=str(start_date),
        end_date=str(end_date),
    )
    return period


@transaction.atomic
def reopen_period(*, period: AccountingPeriod, user: User | None, reason: str) -> AccountingPeriod:
    """Reopen a closed period — deliberate and audited, never silent."""
    if period.status != AccountingPeriod.Status.CLOSED:
        raise ValueError("That period is not closed.")
    if not reason.strip():
        raise ValueError("A reason is required to reopen a closed period.")
    period.status = AccountingPeriod.Status.OPEN
    period.reopened_by = user
    period.reopened_at = timezone.now()
    period.notes = f"{period.notes}\nReopened: {reason}".strip()
    period.save(update_fields=["status", "reopened_by", "reopened_at", "notes"])
    record_audit(
        action="PERIOD_REOPEN",
        user=user,
        organization=period.organization,
        entity_type="accounting_period",
        entity_id=str(period.pk),
        changes={"reason": reason},
    )

    # F2 — emit PERIOD_REOPENED on the bus so any cached period-closed
    # reports invalidate and HQ consolidation re-runs.
    from apps.events.events import EventType
    from apps.events.publishers import publish_fiscal_period_event

    publish_fiscal_period_event(
        event=EventType.PERIOD_REOPENED,
        period_id=period.pk,
        organization=period.organization,
        user=user,
        kind=period.kind,
        start_date=str(period.start_date),
        end_date=str(period.end_date),
    )
    return period


# ---------------------------------------------------------------------------
# Slice 2 — auto-posting the operational reality into the ledger.
#
# Up to here, the ledger only captured journal entries that were explicitly
# posted by a service (payroll, supplier bill, B2B settlement). The P&L stayed
# empty because nothing was posting sales. These three functions close that
# gap so the leader's cockpit — the Finance home — reflects the business as it
# happens:
#
#   * ``post_sale_journal`` — every completed POS sale → AR/cash, revenue,
#     VAT Output, and COGS+Inventory at the FEFO batch's wholesale_cost.
#   * ``post_inventory_adjustment`` — a stock-count variance →
#     Dr/COGS  Cr/Inventory so the GL moves with the physical count.
#   * ``post_writeoff`` — a StockDisposal (destruction, expiry) →
#     Dr Inventory Adjustment Expense / Cr Inventory at batch cost.
# ---------------------------------------------------------------------------


@transaction.atomic
def post_sale_journal(*, sale: Any, user: User | None) -> JournalEntry | None:
    """Auto-post a completed retail sale to the GL.

    Debits:
      * Cash on Hand (1100)  — full sale total (retail is cash-on-delivery).
    Credits:
      * Retail Revenue (4100) — sum of line_net (price excluding VAT portion).
      * VAT Payable — Output (2300) — sum of line_tax (only the B-class 18%
                                  portion; Rwanda exempts / zero-rates
                                  medicines A/C/D).
    COGS leg (separate entry so it has its own reference + audit trail):
      Debit  COGS (5000)
      Credit Inventory (1500)
      at the FEFO batch's ``wholesale_cost``. This is the moment inventory
      leaves the books: every retail sale also adjusts the on-hand value.

    Returns the sales-side JournalEntry (or None if the sale had no value).
    """
    accounts = ensure_default_accounts(sale.organization)

    # Sales side: cash/debit-revenue + VAT split. Prices are VAT-inclusive
    # (see apps/retail/models.py), so each line already knows its tax portion.
    revenue_net = sum((i.line_net for i in sale.items.all()), Decimal("0"))
    vat_output = sum((i.line_tax for i in sale.items.all()), Decimal("0"))
    total = sale.total

    if total <= 0:
        return None

    revenue_lines: list[JournalLineInput] = [
        {
            "account": accounts["1100"],
            "side": JournalLine.Side.DEBIT,
            "amount": total,
            "memo": "Cash & equivalents at POS",
        },
        {
            "account": accounts["4100"],
            "side": JournalLine.Side.CREDIT,
            "amount": revenue_net,
            "memo": "Sales revenue (net of VAT)",
        },
    ]
    if vat_output > 0:
        revenue_lines.append(
            {
                "account": accounts["2300"],
                "side": JournalLine.Side.CREDIT,
                "amount": vat_output,
                "memo": "VAT Output (18% on standard-rated lines)",
            }
        )

    sale_entry = post_journal(
        organization=sale.organization,
        description=f"Sale {sale.sale_number or sale.pk} — POS revenue",
        lines=revenue_lines,
        reference_type="sale",
        reference_id=str(sale.pk),
        user=user,
    )

    # COGS leg: draw the cost straight off the FEFO allocations so the GL
    # agrees with the on-hand value, batch by batch.
    cogs_total = Decimal("0")
    cogs_lines: list[JournalLineInput] = []
    for item in sale.items.prefetch_related("allocations__batch").all():
        for alloc in item.allocations.all():
            unit_cost = alloc.batch.wholesale_cost or Decimal("0")
            cost = (unit_cost * alloc.quantity).quantize(Decimal("0.01"))
            if cost <= 0:
                continue
            cogs_total += cost

    if cogs_total > 0:
        post_journal(
            organization=sale.organization,
            description=f"Sale {sale.sale_number or sale.pk} — COGS",
            lines=[
                {
                    "account": accounts["5000"],
                    "side": JournalLine.Side.DEBIT,
                    "amount": cogs_total,
                    "memo": "Cost of goods sold (FEFO batch cost)",
                },
                {
                    "account": accounts["1500"],
                    "side": JournalLine.Side.CREDIT,
                    "amount": cogs_total,
                    "memo": "Inventory on hand (FEFO allocations)",
                },
            ],
            # Its own reference: post_journal deduplicates on the reference
            # pair, and the revenue leg already owns ("sale", sale.pk) — sharing
            # it meant the COGS entry was silently dropped and every sale looked
            # like pure margin.
            reference_type="sale_cogs",
            reference_id=str(sale.pk),
            user=user,
        )

    record_audit(
        action="SALE_POSTED",
        user=user,
        organization=sale.organization,
        entity_type="sale",
        entity_id=str(sale.pk),
        changes={
            "entry_id": sale_entry.pk,
            "total": str(total),
            "revenue_net": str(revenue_net),
            "vat_output": str(vat_output),
            "cogs": str(cogs_total),
        },
    )
    return sale_entry


@transaction.atomic
def post_inventory_adjustment(
    *,
    batch: Any,
    delta: int,
    unit_cost: Decimal | None,
    reason: str,
    reference_type: str,
    reference_id: str,
    user: User | None,
) -> JournalEntry | None:
    """Auto-post a stock-count variance (approved StockCount) to the GL.

    A positive ``delta`` means we found more than the books showed (Dr Inventory
    / Cr COGS — a gain, reducing expense). A negative delta means we found
    less (Dr COGS / Cr Inventory — a shrinkage expense).
    """
    if delta == 0:
        return None

    cost_per_unit = unit_cost if unit_cost is not None else batch.wholesale_cost
    if not cost_per_unit:
        # No cost recorded yet — skip the GL leg, the movement ledger still
        # records the physical truth.
        return None
    amount = (Decimal(str(cost_per_unit)) * abs(int(delta))).quantize(Decimal("0.01"))
    accounts = ensure_default_accounts(batch.organization)

    if delta > 0:
        lines: list[JournalLineInput] = [
            {
                "account": accounts["1500"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": "Stock found (variance surplus)",
            },
            {
                "account": accounts["5000"],
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": "COGS reversal on found stock",
            },
        ]
    else:
        lines = [
            {
                "account": accounts["5000"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": "COGS — stock shrinkage",
            },
            {
                "account": accounts["1500"],
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": "Inventory written off (variance loss)",
            },
        ]

    entry = post_journal(
        organization=batch.organization,
        description=f"Inventory variance — batch {batch.batch_number} ({reason})",
        lines=lines,
        reference_type=reference_type,
        reference_id=reference_id,
        user=user,
    )
    record_audit(
        action="INVENTORY_ADJUSTMENT_POSTED",
        user=user,
        organization=batch.organization,
        entity_type="inventory_batch",
        entity_id=str(batch.pk),
        changes={"delta": delta, "amount": str(amount), "reason": reason},
    )

    # F2 — emit INVENTORY_ADJUSTED on the bus. Reporting / Insights rebuild
    # the variance event from the same source tuple so a transient dispatcher
    # failure doesn't block the GL post (which is already idempotent on
    # (org, reference_type, reference_id)).
    from apps.events.publishers import publish_inventory_adjusted

    publish_inventory_adjusted(
        organization=batch.organization,
        user=user,
        batch_id=batch.pk,
        product_id=batch.product_id,
        delta=delta,
        amount=amount,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    return entry


@transaction.atomic
def post_writeoff(
    *,
    batch: Any,
    quantity: int,
    reason: str,
    reference_type: str,
    reference_id: str,
    user: User | None,
) -> JournalEntry | None:
    """Auto-post a StockDisposal (destruction / writeoff) at the batch's cost.

    Dr Inventory Adjustments (5100)
    Cr Inventory on Hand (1500)
    """
    if quantity <= 0:
        return None
    cost_per_unit = batch.wholesale_cost
    if not cost_per_unit:
        return None
    amount = (Decimal(str(cost_per_unit)) * quantity).quantize(Decimal("0.01"))
    accounts = ensure_default_accounts(batch.organization)

    entry = post_journal(
        organization=batch.organization,
        description=f"Stock writeoff — batch {batch.batch_number} ({reason})",
        lines=[
            {
                "account": accounts["5100"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": f"{quantity} units disposed",
            },
            {
                # 1500 under the statutory chart. 1200 is Bank now, so this was
                # crediting the bank balance for every stock write-off.
                "account": accounts["1500"],
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": "Inventory on hand removed",
            },
        ],
        reference_type=reference_type,
        reference_id=reference_id,
        user=user,
    )
    record_audit(
        action="WRITE_OFF_POSTED",
        user=user,
        organization=batch.organization,
        entity_type="inventory_batch",
        entity_id=str(batch.pk),
        changes={"quantity": quantity, "amount": str(amount), "reason": reason},
    )

    # F2 — emit STOCK_DISPOSED on the bus. Reporting / Insights rebuild the
    # writeoff-driven shrink event from the same source tuple so a transient
    # dispatcher failure doesn't block the GL post.
    from apps.events.publishers import publish_stock_disposed

    publish_stock_disposed(
        organization=batch.organization,
        user=user,
        batch_id=batch.pk,
        product_id=batch.product_id,
        quantity=quantity,
        amount=amount,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    return entry


# ---------------------------------------------------------------------------
# Slice 3 — Tax, VAT, EBM fiscalization bridge.
#
# Two control accounts were added for tax:
#   1300 VAT Input (asset — recoverable from RRA)
#   2050 VAT Output (liability — owed to RRA)
#   2060 Withholding Tax Payable (liability)
#
# The ``record_tax_payment`` flow is approval-gated via the approvals engine
# (`finance.tax_payment` resource type) — money leaves the bank.
# ---------------------------------------------------------------------------


@transaction.atomic
def record_tax_payment(
    *,
    organization: Organization,
    paid_on: Any,
    period_start: Any,
    period_end: Any,
    amount: Decimal,
    method: str = "BANK_TRANSFER",
    rra_reference: str = "",
    notes: str = "",
    user: User | None = None,
) -> Any:
    """Record an RRA remittance and post Dr VAT Output / Cr Cash & Bank.

    The full amount pays down VAT Output by default; if the org has withholding
    tax owed the caller should split manually and call once per liability, or
    use the ``finance.tax_payment`` approval handler to apply the split.
    """
    from apps.finance.models import TaxPayment

    if amount <= 0:
        raise ValueError("Tax payment amount must be positive.")
    payment = TaxPayment.objects.create(
        organization=organization,
        paid_on=paid_on,
        period_start=period_start,
        period_end=period_end,
        amount=amount,
        method=method,
        rra_reference=rra_reference,
        notes=notes,
        created_by=user,
    )
    payment.payment_number = f"TAX-{organization.pk}-{payment.pk:06d}"
    payment.save(update_fields=["payment_number"])
    accounts = ensure_default_accounts(organization)
    post_journal(
        organization=organization,
        entry_date=paid_on,
        description=f"RRA remittance — {payment.payment_number}",
        lines=[
            {
                # 2300/1100 under the statutory chart of accounts — the old
                # 2050/1000 codes were renamed by the F3 migration.
                "account": accounts["2300"],
                "side": JournalLine.Side.DEBIT,
                "amount": amount,
                "memo": f"VAT Output paid ({period_start}–{period_end})",
            },
            {
                "account": accounts[_RECEIPT_ACCOUNT.get(method, "1100")],
                "side": JournalLine.Side.CREDIT,
                "amount": amount,
                "memo": method,
            },
        ],
        reference_type="tax_payment",
        reference_id=str(payment.pk),
        user=user,
    )
    record_audit(
        action="TAX_PAYMENT_RECORDED",
        user=user,
        organization=organization,
        entity_type="tax_payment",
        entity_id=str(payment.pk),
        changes={
            "amount": str(amount),
            "period_start": str(period_start),
            "period_end": str(period_end),
            "rra_reference": rra_reference,
        },
    )

    # F2 — emit STATUTORY_PAYMENT_CONFIRMED on the bus. The two-line GL post
    # above is the source of truth; this event lets Reporting / Insights /
    # HQ consolidation rebuild the stat-payable cleared report from the same
    # source tuple (idempotent on (org, tax_payment, payment.pk)).
    from apps.events.publishers import publish_statutory_payment_confirmed

    publish_statutory_payment_confirmed(
        organization=organization,
        user=user,
        payment_id=payment.pk,
        amount=amount,
        period_start=str(period_start),
        period_end=str(period_end),
        rra_reference=rra_reference,
    )
    return payment


@transaction.atomic
def mirror_ebm_to_ledger(*, tax_record: Any, user: User | None) -> JournalEntry:
    """EBM fiscalization bridge — when a TaxRecord lands from the SDC/OSDC,
    mirror its per-class breakdown into the GL so the EBM register and the
    VAT Output ledger agree to the cent.

    The TaxRecord stores `tax_class_a/b/c` amounts. We post:
      Dr Sales Revenue (split across classes proportionally)  Cr VAT Output (sum)
    Actually the *revenue* lines are already posted by ``post_sale_journal``,
    so the EBM mirror only writes a confirming VAT Output credit so the
    RRA-side audit register reconciles. No double-post of revenue.
    """
    accounts = ensure_default_accounts(tax_record.organization)
    vat_total = sum(
        (
            Decimal(str(tax_record.tax_class_a or 0)),
            Decimal(str(tax_record.tax_class_b or 0)),
            Decimal(str(tax_record.tax_class_c or 0)),
        ),
        Decimal("0"),
    )
    if vat_total <= 0:
        raise ValueError("TaxRecord carries no VAT to mirror.")
    entry = post_journal(
        organization=tax_record.organization,
        description=f"EBM mirror — receipt {tax_record.receipt_number}",
        lines=[
            {
                # 1400/2300 under the statutory chart of accounts — the old
                # 1100 (receivables) and 2050 (VAT output) codes were renamed
                # by the F3 migration.
                "account": accounts["1400"],
                "side": JournalLine.Side.DEBIT,
                "amount": vat_total,
                "memo": "EBM-fiscalized VAT receivable from RRA reconciliation",
            },
            {
                "account": accounts["2300"],
                "side": JournalLine.Side.CREDIT,
                "amount": vat_total,
                "memo": f"EBM {tax_record.receipt_number} (A:{tax_record.tax_class_a} B:{tax_record.tax_class_b} C:{tax_record.tax_class_c})",
            },
        ],
        reference_type="tax_record",
        reference_id=str(tax_record.pk),
        user=user,
    )
    record_audit(
        action="EBM_MIRRORED",
        user=user,
        organization=tax_record.organization,
        entity_type="tax_record",
        entity_id=str(tax_record.pk),
        changes={"vat_total": str(vat_total)},
    )
    return entry


# Approval-gated RRA remittance — money leaves the bank, so it routes through
# the central approvals engine rather than being applied directly. The approval
# handler below is invoked once a senior approves the request.


@registry.register("finance.tax_payment")
def _apply_tax_payment(approval: ApprovalRequest) -> None:
    """Apply an approved tax-payment request: call ``record_tax_payment`` with
    the payload values. No self-approval by design — the registry decorator
    enforces the segregation."""

    organization = approval.organization
    payload = approval.payload
    payment = record_tax_payment(
        organization=organization,
        paid_on=payload.get("paid_on") or timezone.now().date(),
        period_start=payload["period_start"],
        period_end=payload["period_end"],
        amount=Decimal(payload["amount"]),
        method=payload.get("method", "BANK_TRANSFER"),
        rra_reference=payload.get("rra_reference", ""),
        notes=payload.get("notes", ""),
        user=approval.decided_by,
    )
    record_audit(
        action="TAX_PAYMENT_APPLIED",
        user=approval.decided_by,
        organization=organization,
        entity_type="tax_payment",
        entity_id=str(payment.pk),
        changes=payload,
    )


def request_tax_payment(
    *,
    organization: Organization,
    requested_by: User,
    paid_on: Any,
    period_start: Any,
    period_end: Any,
    amount: Decimal,
    method: str = "BANK_TRANSFER",
    rra_reference: str = "",
    notes: str = "",
    reason: str = "",
) -> ApprovalRequest:
    """Propose an RRA remittance — routed through the approvals engine so a
    senior must sign off before the money leaves the bank."""
    payload = {
        "paid_on": str(paid_on),
        "period_start": str(period_start),
        "period_end": str(period_end),
        "amount": str(amount),
        "method": method,
        "rra_reference": rra_reference,
        "notes": notes,
    }
    return request_approval(
        resource_type="finance.tax_payment",
        resource_id=str(organization.pk),
        organization=organization,
        requested_by=requested_by,
        payload=payload,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# TenantSettings (ADR-014 — per-tenant configuration as data, not code)
# ---------------------------------------------------------------------------


def tenant_settings_for(organization: Organization) -> TenantSettings:
    """Return (and lazily create) the :class:`TenantSettings` for ``organization``.

    Every module reads tenant-scoped config through this helper so the
    configuration lives in the database, not in code: costing method,
    FX provider, pay period, statutory remittance day, PIT filing
    deadline.

    The lazy create keeps onboarding cheap — a new tenant gets a default
    TenantSettings row the first time any module asks for one.
    """
    settings, _created = TenantSettings.objects.get_or_create(
        organization=organization,
        defaults={
            "base_currency": "RWF",
            "fx_provider": "",
            "costing_method": TenantSettings.CostingMethod.FEFO_LOT,
            "pay_period": TenantSettings.PayPeriod.MONTHLY,
            "statutory_remittance_day": 15,
            "pit_filing_deadline_month": 3,
            "pit_filing_deadline_day": 31,
            "default_country": "RW",
            "timezone": "Africa/Kigali",
        },
    )
    return settings


# ---------------------------------------------------------------------------
# F4.4 — OpeningBalance import (onboarding + legacy migration)
# ---------------------------------------------------------------------------


class OpeningBalanceValidationError(ValueError):
    """Raised when an opening-balance import fails its tie-out checks."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _validate_gl_trial_balance(organization: Organization, rows: list[OpeningBalance]) -> None:
    """A trial balance must balance: Σdebits = Σcredits. Each account code must
    exist in the org's chart of accounts."""
    accounts = {a.code: a for a in Account.objects.filter(organization=organization)}
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    errors: list[str] = []
    for row in rows:
        code = row.payload.get("account_code", "")
        if code not in accounts:
            errors.append(f"GL row {row.reference_key}: unknown account code {code!r}")
            continue
        total_debit += Decimal(str(row.payload.get("debit", 0) or 0))
        total_credit += Decimal(str(row.payload.get("credit", 0) or 0))
    if total_debit != total_credit:
        errors.append(
            f"Trial balance does not balance: debits={total_debit} credits={total_credit}"
        )
    if errors:
        raise OpeningBalanceValidationError(errors)


def _validate_ar_ap_aging(
    organization: Organization, rows: list[OpeningBalance], kind: str
) -> None:
    """AR/AP aging rows must reference a known partner (catalog.Supplier or a
    downstream Customer model — fall back to raw reference_id if the model is
    absent). Each row must carry a positive amount and a valid aging bucket."""
    valid_buckets = {"d30", "d60", "d90", "over90"}
    errors: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.reference_key in seen:
            errors.append(f"{kind} duplicate reference_key {row.reference_key!r}")
        seen.add(row.reference_key)
        amount = Decimal(str(row.payload.get("amount", 0) or 0))
        if amount <= 0:
            errors.append(f"{kind} row {row.reference_key}: amount must be > 0")
        bucket = row.payload.get("aging_bucket", "")
        if bucket not in valid_buckets:
            errors.append(
                f"{kind} row {row.reference_key}: invalid aging_bucket {bucket!r} "
                f"(expected one of {sorted(valid_buckets)})"
            )
        if not row.payload.get("partner_ref"):
            errors.append(f"{kind} row {row.reference_key}: missing partner_ref")
    if errors:
        raise OpeningBalanceValidationError(errors)


def _validate_stock_batches(organization: Organization, rows: list[OpeningBalance]) -> None:
    """Stock batch rows must reference a known product (by id) and carry a
    positive quantity + non-negative cost."""
    # Lazy import to avoid pulling catalog at app load time.
    from apps.catalog.models import Product

    valid_ids = {p.pk for p in Product.objects.filter(is_active=True)}
    errors: list[str] = []
    for row in rows:
        pid = row.payload.get("product_id")
        if pid is None or int(pid) not in valid_ids:
            errors.append(f"STOCK_BATCH row {row.reference_key}: unknown product_id {pid!r}")
        qty = int(row.payload.get("quantity", 0) or 0)
        if qty <= 0:
            errors.append(f"STOCK_BATCH row {row.reference_key}: quantity must be > 0")
        cost = Decimal(str(row.payload.get("unit_cost", 0) or 0))
        if cost < 0:
            errors.append(f"STOCK_BATCH row {row.reference_key}: unit_cost must be >= 0")
    if errors:
        raise OpeningBalanceValidationError(errors)


def _validate_employee_leave(organization: Organization, rows: list[OpeningBalance]) -> None:
    """Employee leave rows must reference a known employee + valid leave type."""
    # Lazy import to avoid linking HR schema into every finance import call.
    from apps.hr.models import Employee

    employee_ids = {str(e.pk) for e in Employee.objects.filter(organization=organization)}
    valid_types = {"ANNUAL", "SICK", "MATERNITY", "PATERNITY", "UNPAID", "COMPASSIONATE"}
    errors: list[str] = []
    for row in rows:
        emp_id = str(row.payload.get("employee_id", ""))
        if emp_id not in employee_ids:
            errors.append(f"EMPLOYEE_LEAVE row {row.reference_key}: unknown employee_id {emp_id!r}")
        leave_type = row.payload.get("leave_type", "")
        if leave_type not in valid_types:
            errors.append(
                f"EMPLOYEE_LEAVE row {row.reference_key}: invalid leave_type {leave_type!r}"
            )
        days = Decimal(str(row.payload.get("days_accrued", 0) or 0))
        if days < 0:
            errors.append(f"EMPLOYEE_LEAVE row {row.reference_key}: days_accrued must be >= 0")
    if errors:
        raise OpeningBalanceValidationError(errors)


def validate_opening_balance_rows(
    *, organization: Organization, rows: list[dict[str, Any]]
) -> list[OpeningBalance]:
    """Validate a list of opening-balance line dicts and return them as
    in-memory ``OpeningBalance`` objects (not yet saved). Per-kind tie-out
    checks catch the things you can't catch at the row level: trial-balance
    imbalance, duplicate keys, missing partners.

    Each input dict must carry ``kind`` and ``reference_key``; ``payload``
    carries the kind-specific fields.
    """
    if not rows:
        raise OpeningBalanceValidationError(["No opening-balance rows supplied."])

    by_kind: dict[str, list[OpeningBalance]] = {}
    seen_keys: set[tuple[str, str]] = set()
    for r in rows:
        kind = r.get("kind", "")
        ref_key = r.get("reference_key", "")
        if kind not in OpeningBalance.Kind.values:
            raise OpeningBalanceValidationError([f"Unknown kind {kind!r}"])
        if not ref_key:
            raise OpeningBalanceValidationError(
                [f"Row with kind={kind!r} is missing reference_key"]
            )
        dedupe_key = (kind, ref_key)
        if dedupe_key in seen_keys:
            raise OpeningBalanceValidationError([f"Duplicate row within import: {kind}/{ref_key}"])
        seen_keys.add(dedupe_key)
        by_kind.setdefault(kind, []).append(
            OpeningBalance(
                organization=organization,
                kind=kind,
                reference_key=ref_key,
                payload=r.get("payload", {}),
            )
        )

    if OpeningBalance.Kind.GL_TRIAL_BALANCE in by_kind:
        _validate_gl_trial_balance(organization, by_kind[OpeningBalance.Kind.GL_TRIAL_BALANCE])
    if OpeningBalance.Kind.AR_AGING in by_kind:
        _validate_ar_ap_aging(organization, by_kind[OpeningBalance.Kind.AR_AGING], "AR_AGING")
    if OpeningBalance.Kind.AP_AGING in by_kind:
        _validate_ar_ap_aging(organization, by_kind[OpeningBalance.Kind.AP_AGING], "AP_AGING")
    if OpeningBalance.Kind.STOCK_BATCH in by_kind:
        _validate_stock_batches(organization, by_kind[OpeningBalance.Kind.STOCK_BATCH])
    if OpeningBalance.Kind.EMPLOYEE_LEAVE in by_kind:
        _validate_employee_leave(organization, by_kind[OpeningBalance.Kind.EMPLOYEE_LEAVE])

    flat: list[OpeningBalance] = []
    for items in by_kind.values():
        flat.extend(items)
    return flat


@transaction.atomic
def import_opening_balances(
    *,
    organization: Organization,
    rows: list[dict[str, Any]],
    apply: bool = False,
    user: User | None = None,
) -> list[OpeningBalance]:
    """Import a batch of opening-balance rows for ``organization``.

    Validation runs first; if any kind-level tie-out check fails, no row is
    written. On success, rows are persisted as drafts (``applied_at is None``).
    If ``apply=True``, downstream effects (GL opening journal, inventory
    batches, leave balances) are produced in the same transaction.
    """
    validated = validate_opening_balance_rows(organization=organization, rows=rows)
    # Upsert: re-importing the same file is a no-op for already-applied rows.
    for obj in validated:
        OpeningBalance.objects.update_or_create(
            organization=organization,
            kind=obj.kind,
            reference_key=obj.reference_key,
            defaults={"payload": obj.payload},
        )
    if apply:
        _apply_opening_balances(organization=organization, user=user)
    return list(
        OpeningBalance.objects.filter(organization=organization).order_by("kind", "reference_key")
    )


def _apply_opening_balances(*, organization: Organization, user: User | None) -> None:
    """Promote draft opening balances to applied: write the GL opening journal,
    create inventory batches for stock rows, leave balances for HR rows.

    AR/AP aging rows are recorded as OpeningBalances only at this stage — the
    downstream partner-ledger models (open invoices) are not yet a first-class
    concept separate from the AR/AP control accounts, so the GL opening journal
    captures the net position. Future migrations will hook them up.
    """
    gl_rows = list(
        OpeningBalance.objects.filter(
            organization=organization,
            kind=OpeningBalance.Kind.GL_TRIAL_BALANCE,
            applied_at__isnull=True,
        )
    )
    if gl_rows:
        accounts = {a.code: a for a in Account.objects.filter(organization=organization)}
        lines: list[JournalLineInput] = []
        for row in gl_rows:
            acct = accounts[row.payload["account_code"]]
            debit = Decimal(str(row.payload.get("debit", 0) or 0))
            credit = Decimal(str(row.payload.get("credit", 0) or 0))
            if debit > 0:
                lines.append(
                    {"account": acct, "side": JournalLine.Side.DEBIT, "amount": debit, "memo": ""}
                )
            if credit > 0:
                lines.append(
                    {"account": acct, "side": JournalLine.Side.CREDIT, "amount": credit, "memo": ""}
                )
        if lines:
            post_journal(
                organization=organization,
                description="Opening trial balance",
                lines=lines,
                reference_type="opening_balance",
                reference_id=f"gl-{organization.pk}",
                user=user,
            )

    stock_rows = list(
        OpeningBalance.objects.filter(
            organization=organization,
            kind=OpeningBalance.Kind.STOCK_BATCH,
            applied_at__isnull=True,
        )
    )
    if stock_rows:
        from apps.catalog.models import Product
        from apps.inventory.models import InventoryBatch, StockMovement

        products = {p.pk: p for p in Product.objects.filter(is_active=True)}
        for row in stock_rows:
            product = products[int(row.payload["product_id"])]
            batch = InventoryBatch.objects.create(
                organization=organization,
                product=product,
                batch_number=row.payload["batch_number"],
                expiry_date=row.payload["expiry_date"],
                quantity_available=int(row.payload["quantity"]),
                wholesale_cost=Decimal(str(row.payload.get("unit_cost", 0) or 0)),
                source_supplier_id=row.payload.get("source_supplier_id"),
            )
            StockMovement.objects.create(
                organization=organization,
                product=product,
                batch=batch,
                batch_number=batch.batch_number,
                movement_type=StockMovement.Type.INTAKE,
                quantity_delta=int(row.payload["quantity"]),
                reference_type="opening_balance",
                reference_id=row.reference_key,
                reason="Opening balance",
            )

    OpeningBalance.objects.filter(organization=organization, applied_at__isnull=True).update(
        applied_at=timezone.now()
    )


# ---------------------------------------------------------------------------
# Accounts receivable (ROADMAP 9): invoices, receipts, on-account credit, dunning
# ---------------------------------------------------------------------------


class CreditHoldError(ValueError):
    """Raised when a customer's credit profile forbids further invoicing."""


def _customer_outstanding(organization: Organization, customer: Organization) -> Decimal:
    """Total still owed to ``organization`` by ``customer`` across open invoices."""
    total = Decimal("0.00")
    open_invoices = CustomerInvoice.objects.filter(
        organization=organization, customer=customer
    ).exclude(status__in=[CustomerInvoice.Status.PAID, CustomerInvoice.Status.CANCELLED])
    for inv in open_invoices:
        total += inv.total_amount - inv.amount_paid
    return total.quantize(Decimal("0.01"))


def _assert_credit_allows(
    *, organization: Organization, customer: Organization, new_amount: Decimal
) -> None:
    """Guard an invoice against the customer's credit profile.

    No profile means no credit terms were agreed, so nothing is blocked: plenty
    of customers trade cash-on-delivery.
    """
    profile = CreditProfile.objects.filter(creditor=organization, debtor=customer).first()
    if profile is None:
        return
    if profile.status == CreditProfile.Status.HOLD:
        reason = profile.hold_reason or "no reason recorded"
        raise CreditHoldError(f"{customer.name} is on credit hold ({reason}).")
    if profile.credit_limit > 0:
        projected = _customer_outstanding(organization, customer) + new_amount
        if projected > profile.credit_limit:
            raise CreditHoldError(
                f"{customer.name} credit limit breached: outstanding would be "
                f"{projected} against a limit of {profile.credit_limit}."
            )


@transaction.atomic
def record_customer_invoice(
    *,
    organization: Organization,
    customer: Organization,
    invoice_date: Any,
    due_date: Any,
    total_amount: Decimal,
    vat_amount: Decimal = Decimal("0"),
    tax_class: str = "B",
    reference_type: str = "",
    reference_id: str = "",
    notes: str = "",
    user: User | None = None,
) -> CustomerInvoice:
    """Raise a B2B invoice and post it to the GL.

        Dr 1400 Accounts Receivable      total
        Cr 4100 Revenue                  total - vat
        Cr 2300 VAT Output               vat        (omitted when zero-rated)

    Refuses if the customer is on credit hold or the invoice would breach their
    credit limit.
    """
    total_amount = Decimal(total_amount)
    vat_amount = Decimal(vat_amount or 0)
    if total_amount <= 0:
        raise ValueError("Invoice total must be positive.")
    if vat_amount < 0 or vat_amount > total_amount:
        raise ValueError("vat_amount must be between 0 and total_amount.")

    _assert_credit_allows(organization=organization, customer=customer, new_amount=total_amount)

    seq = next_number(organization=organization, domain="FINANCE", kind="CINV")
    invoice = CustomerInvoice.objects.create(
        organization=organization,
        customer=customer,
        invoice_number=f"INV-{organization.pk}-{seq:05d}",
        invoice_date=invoice_date,
        due_date=due_date,
        total_amount=total_amount,
        vat_amount=vat_amount,
        tax_class=tax_class,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
        created_by=user,
    )

    accounts = ensure_default_accounts(organization)
    net = (total_amount - vat_amount).quantize(Decimal("0.01"))
    lines: list[JournalLineInput] = [
        {
            "account": accounts["1400"],
            "side": "DEBIT",
            "amount": total_amount,
            "memo": f"Invoice {invoice.invoice_number} for {customer.name}",
        },
        {
            "account": accounts["4100"],
            "side": "CREDIT",
            "amount": net,
            "memo": f"Revenue on {invoice.invoice_number}",
        },
    ]
    if vat_amount > 0:
        lines.append(
            {
                "account": accounts["2300"],
                "side": "CREDIT",
                "amount": vat_amount,
                "memo": f"VAT output ({tax_class}) on {invoice.invoice_number}",
            }
        )

    post_journal(
        organization=organization,
        entry_date=invoice_date,
        description=f"Customer invoice {invoice.invoice_number}",
        lines=lines,
        reference_type="customer_invoice",
        reference_id=str(invoice.pk),
        user=user,
    )
    record_audit(
        action="CREATE",
        user=user,
        organization=organization,
        entity_type="customer_invoice",
        entity_id=str(invoice.pk),
        changes={"total": str(total_amount), "customer": customer.name},
    )
    return invoice


# Which cash-side control account a tender lands in.
_RECEIPT_ACCOUNT = {
    "CASH": "1100",
    "CHEQUE": "1100",
    "BANK_TRANSFER": "1200",
    "MOBILE_MONEY": "1300",
}


@transaction.atomic
def record_customer_receipt(
    *,
    invoice: CustomerInvoice,
    amount: Decimal,
    method: str = "CASH",
    reference: str = "",
    received_on: Any = None,
    user: User | None = None,
) -> CustomerReceipt:
    """Receive money against an invoice and post it.

        Dr 1100/1200/1300 (by tender)    amount
        Cr 1400 Accounts Receivable      amount applied

    Anything paid beyond the balance becomes an on-account ``CustomerCredit``
    (a liability) rather than over-crediting AR.
    """
    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError("Receipt amount must be positive.")
    invoice.refresh_from_db()
    if invoice.is_settled:
        raise ValueError(f"Invoice {invoice.invoice_number} is already paid in full.")

    received_on = received_on or timezone.now().date()
    organization = invoice.organization
    seq = next_number(organization=organization, domain="FINANCE", kind="RCT")
    receipt = CustomerReceipt.objects.create(
        invoice=invoice,
        receipt_number=f"RCT-{organization.pk}-{seq:05d}",
        amount=amount,
        method=method,
        reference=reference,
        received_on=received_on,
        created_by=user,
    )

    applied = min(amount, invoice.amount_due)
    overpaid = (amount - applied).quantize(Decimal("0.01"))

    invoice.amount_paid = (invoice.amount_paid + applied).quantize(Decimal("0.01"))
    invoice.status = (
        CustomerInvoice.Status.PAID
        if invoice.amount_paid >= invoice.total_amount
        else CustomerInvoice.Status.PARTIAL
    )
    invoice.save(update_fields=["amount_paid", "status", "updated_at"])

    accounts = ensure_default_accounts(organization)
    cash_code = _RECEIPT_ACCOUNT.get(method, "1100")
    lines: list[JournalLineInput] = [
        {
            "account": accounts[cash_code],
            "side": "DEBIT",
            "amount": amount,
            "memo": f"Receipt {receipt.receipt_number} ({method})",
        },
        {
            "account": accounts["1400"],
            "side": "CREDIT",
            "amount": applied,
            "memo": f"Settles {invoice.invoice_number}",
        },
    ]
    if overpaid > 0:
        # Money held but not earned - a liability until applied or refunded.
        lines.append(
            {
                "account": accounts["2160"],
                "side": "CREDIT",
                "amount": overpaid,
                "memo": f"On-account credit for {invoice.customer.name}",
            }
        )
        CustomerCredit.objects.create(
            organization=organization,
            customer=invoice.customer,
            amount=overpaid,
            balance=overpaid,
            source=CustomerCredit.Source.OVERPAYMENT,
            source_receipt=receipt,
            notes=f"Overpayment on {invoice.invoice_number}",
        )

    post_journal(
        organization=organization,
        entry_date=received_on,
        description=f"Customer receipt {receipt.receipt_number}",
        lines=lines,
        reference_type="customer_receipt",
        reference_id=str(receipt.pk),
        user=user,
    )
    return receipt


# Days past due -> ladder step. Checked high-to-low so the worst step wins.
_DUNNING_LADDER = [
    (60, DunningNotice.Level.LEGAL),
    (30, DunningNotice.Level.FINAL),
    (14, DunningNotice.Level.SECOND),
    (7, DunningNotice.Level.REMINDER),
]


@transaction.atomic
def apply_dunning(*, organization: Organization, today: Any = None) -> list[DunningNotice]:
    """Walk open invoices and issue the next collections step for each.

    Idempotent: one notice per level per invoice, so re-running the same day
    issues nothing new. Reaching the legal step puts the customer's credit
    profile on hold, which blocks further B2B orders.
    """
    today = today or timezone.now().date()
    issued: list[DunningNotice] = []

    open_invoices = CustomerInvoice.objects.filter(organization=organization).exclude(
        status__in=[CustomerInvoice.Status.PAID, CustomerInvoice.Status.CANCELLED]
    )
    for invoice in open_invoices:
        days_past = (today - invoice.due_date).days
        if days_past < 7:
            continue

        level = next(lvl for threshold, lvl in _DUNNING_LADDER if days_past >= threshold)
        if DunningNotice.objects.filter(invoice=invoice, level=level).exists():
            continue

        issued.append(
            DunningNotice.objects.create(
                invoice=invoice,
                level=level,
                days_past_due=days_past,
                amount_due=invoice.amount_due,
                sent_on=today,
            )
        )

        if invoice.status != CustomerInvoice.Status.OVERDUE:
            invoice.status = CustomerInvoice.Status.OVERDUE
            invoice.save(update_fields=["status", "updated_at"])

        if level == DunningNotice.Level.LEGAL:
            profile = CreditProfile.objects.filter(
                creditor=organization, debtor=invoice.customer
            ).first()
            if profile and profile.status != CreditProfile.Status.HOLD:
                profile.status = CreditProfile.Status.HOLD
                profile.hold_reason = f"Auto-hold: {invoice.invoice_number} is 60+ days overdue."
                profile.save(update_fields=["status", "hold_reason", "updated_at"])
    return issued


# A customer who has let an invoice run this far past its due date stops being
# able to place new orders on credit, whatever their limit says. The dunning
# ladder issues the FINAL demand at the same age.
ORDER_BLOCK_DAYS_OVERDUE = 30


def days_overdue(organization: Organization, customer: Organization, *, today: Any = None) -> int:
    """Age of the customer's oldest unsettled invoice, in days past its due date.

    Zero when nothing is overdue.
    """
    today = today or timezone.now().date()
    oldest = (
        CustomerInvoice.objects.filter(organization=organization, customer=customer)
        .exclude(status__in=[CustomerInvoice.Status.PAID, CustomerInvoice.Status.CANCELLED])
        .order_by("due_date")
        .first()
    )
    if oldest is None:
        return 0
    return max(0, (today - oldest.due_date).days)


def assert_may_order_on_credit(
    *,
    seller: Organization,
    buyer: Organization,
    order_amount: Decimal = Decimal("0"),
    today: Any = None,
) -> None:
    """Gate a B2B order against the buyer's credit standing with this seller.

    Raises :class:`CreditHoldError` when the buyer is on hold, has an invoice
    too far past due, or the order would push them over their limit. Callers in
    the API layer turn that into an HTTP 409 — the request is well-formed, it is
    the buyer's account that refuses it.

    No credit profile means the pair trades cash-on-delivery, which nothing here
    needs to block.
    """
    profile = CreditProfile.objects.filter(creditor=seller, debtor=buyer).first()
    if profile is None:
        return

    if profile.status == CreditProfile.Status.HOLD:
        reason = profile.hold_reason or "no reason recorded"
        raise CreditHoldError(f"{buyer.name} is on credit hold ({reason}).")

    overdue = days_overdue(seller, buyer, today=today)
    if overdue > ORDER_BLOCK_DAYS_OVERDUE:
        raise CreditHoldError(
            f"{buyer.name} has an invoice {overdue} days past due "
            f"(limit is {ORDER_BLOCK_DAYS_OVERDUE}). Settle it before ordering again."
        )

    if profile.credit_limit > 0 and order_amount > 0:
        projected = _customer_outstanding(seller, buyer) + Decimal(order_amount)
        if projected > profile.credit_limit:
            raise CreditHoldError(
                f"{buyer.name} credit limit breached: exposure would be {projected} "
                f"against a limit of {profile.credit_limit}."
            )


# ---------------------------------------------------------------------------
# Payment runs (ROADMAP 9): batch supplier settlement with a disbursement file
# ---------------------------------------------------------------------------


# Above this total a run needs two sign-offs rather than one. Set in RWF; the
# figure is deliberately conservative — a second pair of eyes costs a minute,
# a mis-keyed batch costs a month.
DUAL_APPROVAL_THRESHOLD = Decimal("5000000")


class PaymentRunError(ValueError):
    """Raised when a payment run is asked to do something its state forbids."""


def _payee_details(bill: SupplierBill, method: str) -> tuple[str, str]:
    """Where the money for this bill should go: (payee name, account/MSISDN).

    Settlement details live on the procurement supplier profile when that app
    is installed; a bare catalog supplier still has a phone number, which is
    what a MoMo payout needs anyway.
    """
    supplier = bill.supplier
    account = ""
    try:
        from apps.procurement.models import SupplierProfile

        profile = SupplierProfile.objects.filter(supplier=supplier).first()
    except Exception:  # pragma: no cover - procurement not installed
        profile = None
    if profile is not None:
        account = (
            profile.mobile_money_number
            if method == PaymentRun.Method.MOBILE_MONEY
            else profile.bank_account_number
        )
    if not account and method == PaymentRun.Method.MOBILE_MONEY:
        account = getattr(supplier, "phone", "") or ""
    return supplier.name, account


@transaction.atomic
def create_payment_run(
    *,
    organization: Organization,
    bills: Sequence[SupplierBill],
    method: str = PaymentRun.Method.BANK_TRANSFER,
    scheduled_for: Any = None,
    notes: str = "",
    user: User | None = None,
) -> PaymentRun:
    """Open a draft run over the given bills, one line each for what is still due."""
    if not bills:
        raise PaymentRunError("A payment run needs at least one bill.")

    seq = next_number(organization=organization, domain="FINANCE", kind="PRUN")
    run = PaymentRun.objects.create(
        organization=organization,
        run_number=f"PRUN-{organization.pk}-{seq:05d}",
        method=method,
        scheduled_for=scheduled_for,
        notes=notes,
        created_by=user,
    )

    total = Decimal("0.00")
    for bill in bills:
        if bill.organization_id != organization.pk:
            raise PaymentRunError(f"{bill} belongs to another organization.")
        if bill.status == SupplierBill.Status.PAID:
            raise PaymentRunError(f"{bill} is already paid in full.")
        # A bill sitting in another live run is already spoken for.
        if PaymentRunLine.objects.filter(
            bill=bill,
            payment_run__status__in=[
                PaymentRun.Status.DRAFT,
                PaymentRun.Status.AWAITING_APPROVAL,
                PaymentRun.Status.APPROVED,
            ],
        ).exists():
            raise PaymentRunError(f"{bill} is already in an open payment run.")

        amount = Decimal(bill.amount_due).quantize(Decimal("0.01"))
        payee_name, payee_account = _payee_details(bill, method)
        PaymentRunLine.objects.create(
            payment_run=run,
            bill=bill,
            amount=amount,
            payee_name=payee_name,
            payee_account=payee_account,
        )
        total += amount

    run.total_amount = total
    run.approvals_required = 2 if total > DUAL_APPROVAL_THRESHOLD else 1
    run.save(update_fields=["total_amount", "approvals_required", "updated_at"])
    record_audit(
        action="CREATE",
        user=user,
        organization=organization,
        entity_type="payment_run",
        entity_id=str(run.pk),
        changes={"total": str(total), "lines": str(len(bills))},
    )
    return run


def build_disbursement_file(run: PaymentRun) -> tuple[str, str]:
    """Render the run as the CSV its channel expects: (filename, body).

    Every row carries an idempotency key of ``run_id:bill_id`` so a file that
    gets uploaded twice — which happens — settles once.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    if run.method == PaymentRun.Method.MOBILE_MONEY:
        writer.writerow(["msisdn", "amount", "reference", "idempotency_key"])
        for line in run.lines.select_related("bill__supplier"):
            writer.writerow(
                [
                    line.payee_account,
                    f"{line.amount:.2f}",
                    line.bill.bill_number or f"BILL-{line.bill_id}",
                    line.idempotency_key,
                ]
            )
        name = f"{run.run_number}-momo.csv"
    else:
        writer.writerow(
            ["account_number", "account_name", "amount", "reference", "idempotency_key"]
        )
        for line in run.lines.select_related("bill__supplier"):
            writer.writerow(
                [
                    line.payee_account,
                    line.payee_name,
                    f"{line.amount:.2f}",
                    line.bill.bill_number or f"BILL-{line.bill_id}",
                    line.idempotency_key,
                ]
            )
        name = f"{run.run_number}-bank.csv"
    return name, buffer.getvalue()


@transaction.atomic
def submit_payment_run(*, run: PaymentRun, user: User) -> ApprovalRequest:
    """Send a draft run for sign-off. Nothing moves until it comes back approved."""
    if run.status != PaymentRun.Status.DRAFT:
        raise PaymentRunError("Only a draft run can be submitted for approval.")
    if not run.lines.exists():
        raise PaymentRunError("A payment run needs at least one line.")

    run.status = PaymentRun.Status.AWAITING_APPROVAL
    run.save(update_fields=["status", "updated_at"])
    return request_approval(
        resource_type="finance.payment_run",
        resource_id=str(run.pk),
        organization=run.organization,
        requested_by=user,
        payload={"total_amount": str(run.total_amount), "method": run.method},
        reason=f"Payment run {run.run_number} · {run.line_count} bills · {run.total_amount}",
    )


@registry.register("finance.payment_run")
def _apply_payment_run_approval(approval: ApprovalRequest) -> None:
    """One sign-off landed. Below the threshold that is the whole story; above
    it, raise a second request in this approver's name so the engine's
    no-self-approval rule guarantees a different second signature."""
    run = PaymentRun.objects.get(pk=int(approval.resource_id))
    run.approvals_received += 1

    if run.approvals_received < run.approvals_required:
        run.save(update_fields=["approvals_received", "updated_at"])
        request_approval(
            resource_type="finance.payment_run",
            resource_id=str(run.pk),
            organization=run.organization,
            requested_by=approval.decided_by or approval.requested_by,
            payload=approval.payload,
            reason=(
                f"Second approval for {run.run_number} "
                f"({run.total_amount} exceeds the dual-approval threshold)"
            ),
        )
        return

    run.status = PaymentRun.Status.APPROVED
    run.approved_at = timezone.now()
    filename, body = build_disbursement_file(run)
    run.disbursement_filename = filename
    run.disbursement_file = body
    run.save(
        update_fields=[
            "status",
            "approvals_received",
            "approved_at",
            "disbursement_filename",
            "disbursement_file",
            "updated_at",
        ]
    )


@transaction.atomic
def disburse_payment_run(*, run: PaymentRun, user: User | None = None) -> PaymentRun:
    """Money has left the building — post a payment against every line.

    Idempotent per line, so re-running after a partial failure settles only what
    is still outstanding.
    """
    if run.status not in {PaymentRun.Status.APPROVED, PaymentRun.Status.DISBURSED}:
        raise PaymentRunError("Only an approved run can be disbursed.")

    for line in run.lines.select_related("bill").select_for_update():
        if line.paid:
            continue
        record_supplier_bill_payment(
            bill=line.bill,
            amount=line.amount,
            method=run.method,
            reference=f"{run.run_number}#{line.idempotency_key}",
            user=user,
        )
        line.paid = True
        line.save(update_fields=["paid"])

    if run.status != PaymentRun.Status.DISBURSED:
        run.status = PaymentRun.Status.DISBURSED
        run.disbursed_at = timezone.now()
        run.save(update_fields=["status", "disbursed_at", "updated_at"])
    record_audit(
        action="PAYMENT",
        user=user,
        organization=run.organization,
        entity_type="payment_run",
        entity_id=str(run.pk),
        changes={"total": str(run.total_amount)},
    )
    return run


@transaction.atomic
def lock_payment_run(*, run: PaymentRun, user: User | None = None) -> PaymentRun:
    """Close the run once the bank statement agrees with it. Nothing further
    can be added, re-disbursed, or cancelled."""
    if run.status != PaymentRun.Status.DISBURSED:
        raise PaymentRunError("Only a disbursed run can be locked.")
    run.status = PaymentRun.Status.LOCKED
    run.locked_at = timezone.now()
    run.save(update_fields=["status", "locked_at", "updated_at"])
    return run


@transaction.atomic
def cancel_payment_run(
    *, run: PaymentRun, user: User | None = None, reason: str = ""
) -> PaymentRun:
    """Abandon a run that has not paid anything yet."""
    if run.status in {PaymentRun.Status.DISBURSED, PaymentRun.Status.LOCKED}:
        raise PaymentRunError("Money has already moved — this run cannot be cancelled.")
    run.status = PaymentRun.Status.CANCELLED
    run.notes = (f"{run.notes} · Cancelled: {reason}" if run.notes else f"Cancelled: {reason}")[
        :255
    ]
    run.save(update_fields=["status", "notes", "updated_at"])
    return run
