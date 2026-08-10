"""Where the pharmacy's money actually is.

An owner asking "how did we do?" is asking several different questions that a
profit figure does not answer:

* how much came in today, and in what form — a day that took RWF 400,000 of
  which RWF 250,000 was an insurance claim has not put RWF 400,000 in the till;
* what is owed *to* the pharmacy, and by whom — customers on account, and
  insurers who have accepted a claim and not yet paid;
* what the pharmacy owes — suppliers, and the statutory deductions sitting in
  payroll payables waiting for a filing date;
* what is left, in cash, right now.

The existing finance screens answer each of these somewhere, in the vocabulary
of a ledger: receivables aging, payables aging, trial balance. That vocabulary
is correct and useless to somebody who runs a two-person shop. This composes the
same figures into the four sentences they would use themselves.

**Money in is not profit and money owed is not money.** Both are stated as what
they are. An insurance receivable is a claim somebody still has to pay, and
saying so is the difference between a pharmacy that plans and one that is
surprised.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

ZERO = Decimal("0.00")


def _money(value: Any, currency: str = "RWF") -> dict[str, str]:
    return {"amount": f"{Decimal(str(value or 0)):.2f}", "currency": currency}


def _taken_today(org_ids: list[int], today: date) -> dict[str, Decimal]:
    """What came in, split by how it arrived.

    Insurance is deliberately in this list and deliberately not counted as cash:
    the scheme's share of an insured sale is a debt the insurer owes, and a
    pharmacy that reads it as takings will plan to spend money it has not got.
    """
    from apps.retail.models import Payment, Sale

    payments = Payment.objects.filter(
        sale__organization_id__in=org_ids,
        sale__status=Sale.Status.COMPLETED,
        sale__completed_at__date=today,
    ).values("method")

    totals: dict[str, Decimal] = {}
    for row in payments.annotate(total=Sum("amount")):
        totals[row["method"]] = Decimal(str(row["total"] or 0))
    return totals


def _owed_to_us(org_ids: list[int], today: date) -> dict[str, Any]:
    """Customers on account, and insurers who have not yet settled."""
    from apps.distribution.models import StockOrder
    from apps.insurance.models import Claim

    # B2B: a depot's unpaid orders are its receivables.
    customers = ZERO
    overdue = ZERO
    for order in (
        StockOrder.objects.filter(depot_id__in=org_ids)
        .exclude(payment_status=StockOrder.PaymentStatus.PAID)
        .prefetch_related("items")
    ):
        due = Decimal(str(order.amount_due))
        customers += due
        if order.payment_due_date and order.payment_due_date < today:
            overdue += due

    # What is claimed and not yet settled. A part-paid claim still has a
    # balance, so it is the difference that is outstanding, not the whole
    # claim — and a rejected or reversed one is owed by nobody.
    insurers = ZERO
    claims_waiting = 0
    for claim in Claim.objects.filter(
        organization_id__in=org_ids,
        status__in=(Claim.Status.SUBMITTED, Claim.Status.ACCEPTED, Claim.Status.PART_PAID),
    ).only("claimed_amount", "paid_amount"):
        outstanding = Decimal(str(claim.claimed_amount)) - Decimal(str(claim.paid_amount))
        if outstanding > 0:
            insurers += outstanding
            claims_waiting += 1

    return {
        "customers": customers,
        "customers_overdue": overdue,
        "insurers": insurers,
        "claims_waiting": claims_waiting,
        "total": customers + insurers,
    }


def _we_owe(org_ids: list[int], today: date) -> dict[str, Any]:
    """Suppliers, and the statutory money that is not the pharmacy's to keep.

    PAYE, RSSB and CBHI deducted from a payslip sit in payables until they are
    filed. They are in the bank account and they are not the pharmacy's — which
    is exactly the money a small business spends by accident.
    """
    from apps.distribution.models import StockOrder
    from apps.finance.models import JournalLine

    suppliers = ZERO
    overdue = ZERO
    for order in (
        StockOrder.objects.filter(retail_id__in=org_ids)
        .exclude(payment_status=StockOrder.PaymentStatus.PAID)
        .prefetch_related("items")
    ):
        due = Decimal(str(order.amount_due))
        suppliers += due
        if order.payment_due_date and order.payment_due_date < today:
            overdue += due

    statutory = ZERO
    for code in ("2200", "2210", "2220", "2230", "2240", "2250"):
        # Credits raise a liability, debits settle it — net the two.
        credits = (
            JournalLine.objects.filter(
                entry__organization_id__in=org_ids,
                account__code=code,
                side=JournalLine.Side.CREDIT,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        debits = (
            JournalLine.objects.filter(
                entry__organization_id__in=org_ids,
                account__code=code,
                side=JournalLine.Side.DEBIT,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        statutory += Decimal(str(credits)) - Decimal(str(debits))

    return {
        "suppliers": suppliers,
        "suppliers_overdue": overdue,
        "statutory": max(statutory, ZERO),
        "total": suppliers + max(statutory, ZERO),
    }


def _cash_now(org_ids: list[int]) -> Decimal:
    """What is in the drawer and the bank, per the ledger."""
    from apps.finance.models import JournalLine

    total = ZERO
    for code in ("1100", "1110", "1120"):
        credits = (
            JournalLine.objects.filter(
                entry__organization_id__in=org_ids,
                account__code=code,
                side=JournalLine.Side.CREDIT,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        debits = (
            JournalLine.objects.filter(
                entry__organization_id__in=org_ids,
                account__code=code,
                side=JournalLine.Side.DEBIT,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        total += Decimal(str(debits)) - Decimal(str(credits))
    return total


def money_centre(user: Any, *, on: date | None = None) -> dict[str, Any]:
    """The four questions an owner asks about money, answered together."""
    from apps.iam.scoping import organizations_visible_to

    orgs = organizations_visible_to(user)
    org_ids = list(orgs.values_list("id", flat=True))
    today = on or timezone.localdate()
    home = user.organization
    currency = (home.currency if home else "RWF") or "RWF"

    taken = _taken_today(org_ids, today)
    cash_like = sum((taken.get(method, ZERO) for method in ("CASH", "MOBILE_MONEY", "CARD")), ZERO)
    insured = taken.get("INSURANCE", ZERO)

    owed_to_us = _owed_to_us(org_ids, today)
    we_owe = _we_owe(org_ids, today)

    return {
        "as_of": today.isoformat(),
        "currency": currency,
        "took_today": {
            "cash": _money(taken.get("CASH", ZERO), currency),
            "mobile_money": _money(taken.get("MOBILE_MONEY", ZERO), currency),
            "card": _money(taken.get("CARD", ZERO), currency),
            # Named separately because it is not money the pharmacy has.
            "on_insurance": _money(insured, currency),
            "actually_received": _money(cash_like, currency),
            "total_rung_up": _money(cash_like + insured, currency),
        },
        "owed_to_you": {
            "customers": _money(owed_to_us["customers"], currency),
            "customers_overdue": _money(owed_to_us["customers_overdue"], currency),
            "insurers": _money(owed_to_us["insurers"], currency),
            "claims_waiting": owed_to_us["claims_waiting"],
            "total": _money(owed_to_us["total"], currency),
        },
        "you_owe": {
            "suppliers": _money(we_owe["suppliers"], currency),
            "suppliers_overdue": _money(we_owe["suppliers_overdue"], currency),
            # PAYE, RSSB, CBHI — in the account and not the pharmacy's.
            "statutory": _money(we_owe["statutory"], currency),
            "total": _money(we_owe["total"], currency),
        },
        "cash_position": _money(_cash_now(org_ids), currency),
        "as_at_note": (
            "Money owed to you is not money you have. An insurance claim is paid when the "
            "scheme pays it."
        ),
    }


def turnover_12m(org_ids: list[int], *, on: date | None = None) -> Decimal:
    """Rolling twelve-month sales, for the VAT registration threshold."""
    from apps.retail.models import Sale

    today = on or timezone.localdate()
    start = today - timedelta(days=365)
    total = ZERO
    for sale in Sale.objects.filter(
        organization_id__in=org_ids,
        status=Sale.Status.COMPLETED,
        completed_at__date__gte=start,
        completed_at__date__lte=today,
    ).prefetch_related("items"):
        total += Decimal(str(sale.total))
    return total
