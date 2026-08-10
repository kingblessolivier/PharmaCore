"""What a small pharmacy needs to see when it opens in the morning.

Most Rwandan community pharmacies are not departmental. One or two people do
the selling, the ordering, the receiving, the cash and the books. Offering that
person a Finance module, a Procurement module and an HR module is not merely
over-featured — it describes an organisation that does not exist, and every
screen then asks them to pretend.

So this composes one answer to one question: *how is my pharmacy doing today,
and what needs me?*

Two rules it is built on.

**Takings are not profit.** A till that rang RWF 428,500 has not made
RWF 428,500. The medicines cost something, and until that is subtracted the
number is meaningless as a measure of a business. So revenue, cost of goods and
gross profit are all returned, and the cost comes from the FEFO allocations the
sale actually drew on — the same figures the ledger posts — not from an average
or a guess.

**Gross profit is not net profit either.** Rent, salaries and the electricity
bill come out of it. Where those are recorded as expenses in the ledger they
are subtracted too and the result is named an operating result; where they are
not, the figure says so rather than quietly presenting gross profit as what the
owner gets to keep.

Nothing here computes anything the ledger does not already know. It reads.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, TypedDict

from django.db.models import Sum
from django.utils import timezone

from apps.iam.models import Organization, User
from apps.iam.scoping import organizations_visible_to

ZERO = Decimal("0.00")

#: Expiry inside this window is a commercial problem, not yet a compliance one:
#: there is still time to sell it, move it or send it back.
EXPIRY_HORIZON_DAYS = 90


class Money(TypedDict):
    amount: str
    currency: str


def _money(value: Any, currency: str = "RWF") -> Money:
    return {"amount": f"{Decimal(str(value or 0)):.2f}", "currency": currency}


# --------------------------------------------------------------------------- #
# The trading picture
# --------------------------------------------------------------------------- #


def _sales_between(org_ids: list[int], start: date, end: date) -> dict[str, Any]:
    """Revenue, cost and gross profit over a date range, from the sales themselves.

    `Sale.total` is computed rather than stored, so the sum happens in Python.
    That is fine for a day and acceptable for a month at this size; it would
    not be for a chain, which is why this module is only asked for by the
    screens a small pharmacy uses.
    """
    from apps.retail.models import Sale

    sales = (
        Sale.objects.filter(
            organization_id__in=org_ids,
            status=Sale.Status.COMPLETED,
            completed_at__date__gte=start,
            completed_at__date__lte=end,
        )
        .prefetch_related("items__allocations__batch")
        .select_related("organization")
    )

    revenue = ZERO
    cost = ZERO
    transactions = 0
    units = Decimal("0")
    costed_lines = 0
    uncosted_lines = 0

    for sale in sales:
        transactions += 1
        revenue += Decimal(str(sale.total))
        for item in sale.items.all():
            units += Decimal(str(item.quantity_base or 0))
            allocations = list(item.allocations.all())
            if not allocations:
                # Sold before batch allocation existed, or from stock that
                # arrived without a cost. Counted so the margin can say how
                # much of itself it is sure about.
                uncosted_lines += 1
                continue
            line_cost = ZERO
            for allocation in allocations:
                unit_cost = allocation.batch.wholesale_cost or ZERO
                if unit_cost <= 0:
                    uncosted_lines += 1
                    continue
                line_cost += Decimal(str(unit_cost)) * Decimal(str(allocation.quantity))
            if line_cost > 0:
                costed_lines += 1
                cost += line_cost

    gross = revenue - cost
    return {
        "revenue": revenue,
        "cost_of_goods": cost,
        "gross_profit": gross,
        "gross_margin_pct": (
            float((gross / revenue * 100).quantize(Decimal("0.1"))) if revenue > 0 else None
        ),
        "transactions": transactions,
        "units": units,
        "average_basket": (revenue / transactions) if transactions else ZERO,
        # Honesty about the margin's own reliability. A pharmacy that has not
        # entered costs will otherwise read a 100% margin as good news.
        "lines_costed": costed_lines,
        "lines_without_cost": uncosted_lines,
    }


def _expenses_between(org_ids: list[int], start: date, end: date) -> Decimal:
    """Operating expenses posted to the ledger in the period.

    Read from the GL rather than guessed: an expense the pharmacy has not
    recorded is not an expense this can know about, and inventing one would be
    worse than the gap.
    """
    from apps.finance.models import Account, JournalLine

    total = JournalLine.objects.filter(
        entry__organization_id__in=org_ids,
        entry__entry_date__gte=start,
        entry__entry_date__lte=end,
        entry__status="POSTED",
        account__account_type=Account.Type.EXPENSE,
        side=JournalLine.Side.DEBIT,
    ).aggregate(total=Sum("amount"))["total"]
    # Cost of goods is an expense account too, and it is already subtracted to
    # reach gross profit. Counting it again would show a loss on every
    # profitable day.
    cogs = JournalLine.objects.filter(
        entry__organization_id__in=org_ids,
        entry__entry_date__gte=start,
        entry__entry_date__lte=end,
        entry__status="POSTED",
        entry__reference_type="sale_cogs",
        side=JournalLine.Side.DEBIT,
    ).aggregate(total=Sum("amount"))["total"]
    return Decimal(str(total or 0)) - Decimal(str(cogs or 0))


def _stock_value(org_ids: list[int]) -> Decimal:
    """What is on the shelf, at what it cost — not at what it will sell for."""
    from apps.inventory.models import InventoryBatch

    value = ZERO
    for batch in InventoryBatch.objects.filter(
        organization_id__in=org_ids,
        status=InventoryBatch.Status.ACTIVE,
        quantity_available__gt=0,
    ).only("quantity_available", "wholesale_cost"):
        value += Decimal(str(batch.wholesale_cost or 0)) * Decimal(str(batch.quantity_available))
    return value


# --------------------------------------------------------------------------- #
# What needs somebody
# --------------------------------------------------------------------------- #


def _needs_attention(org_ids: list[int], today: date) -> list[dict[str, Any]]:
    """The short list. Everything here is a real count with somewhere to go.

    Ordered by how much it costs to ignore: medicine that cannot be sold,
    then money, then paperwork. A list nobody can act on in one visit trains
    people to stop reading it, so it stays short.
    """
    from apps.inventory.models import InventoryBatch, PharmacyProduct
    from apps.retail.models import Prescription

    horizon = today + timedelta(days=EXPIRY_HORIZON_DAYS)
    items: list[dict[str, Any]] = []

    expired = InventoryBatch.objects.filter(
        organization_id__in=org_ids, expiry_date__lt=today, quantity_available__gt=0
    )
    expired_count = expired.count()
    if expired_count:
        items.append(
            {
                "kind": "expired",
                "count": expired_count,
                "label": f"{expired_count} batch(es) have expired and are still on the shelf",
                "detail": "They cannot be sold. Quarantine them and record the write-off.",
                "to": "/inventory/qc",
                "tone": "danger",
            }
        )

    expiring = InventoryBatch.objects.filter(
        organization_id__in=org_ids,
        status=InventoryBatch.Status.ACTIVE,
        expiry_date__gte=today,
        expiry_date__lte=horizon,
        quantity_available__gt=0,
    )
    expiring_value = ZERO
    for batch in expiring.only("quantity_available", "wholesale_cost"):
        expiring_value += Decimal(str(batch.wholesale_cost or 0)) * Decimal(
            str(batch.quantity_available)
        )
    expiring_count = expiring.count()
    if expiring_count:
        items.append(
            {
                "kind": "expiring",
                "count": expiring_count,
                "label": (f"{expiring_count} batch(es) expire within {EXPIRY_HORIZON_DAYS} days"),
                "detail": (
                    f"About {expiring_value:,.0f} RWF of stock. There is still time to "
                    "sell it, move it or send it back."
                ),
                "to": "/inventory/expiry",
                "tone": "warning",
            }
        )

    # Low stock, computed the same way the dashboard does: sellable on-hand
    # against the listing's own minimum.
    on_hand: dict[tuple[int, int], Any] = {}
    for row in (
        InventoryBatch.objects.filter(
            organization_id__in=org_ids,
            status=InventoryBatch.Status.ACTIVE,
            expiry_date__gte=today,
        )
        .values("organization_id", "product_id")
        .annotate(qty=Sum("quantity_available"))
    ):
        on_hand[(row["organization_id"], row["product_id"])] = row["qty"] or 0
    low = 0
    out = 0
    for listing in PharmacyProduct.objects.filter(
        organization_id__in=org_ids, is_active=True, min_stock_level__gt=0
    ).only("organization_id", "product_id", "min_stock_level"):
        have = on_hand.get((listing.organization_id, listing.product_id), 0)
        if have <= 0:
            out += 1
        elif have < listing.min_stock_level:
            low += 1
    if out:
        items.append(
            {
                "kind": "out_of_stock",
                "count": out,
                "label": f"{out} medicine(s) you stock are finished",
                "detail": "A customer asking for these today leaves without them.",
                "to": "/inventory/replenishment",
                "tone": "danger",
            }
        )
    if low:
        items.append(
            {
                "kind": "low_stock",
                "count": low,
                "label": f"{low} medicine(s) are below your minimum",
                "detail": "Order before they run out, not after.",
                "to": "/inventory/replenishment",
                "tone": "warning",
            }
        )

    waiting = Prescription.objects.filter(
        organization_id__in=org_ids, status=Prescription.Status.ACTIVE
    ).count()
    if waiting:
        items.append(
            {
                "kind": "prescriptions",
                "count": waiting,
                "label": f"{waiting} prescription(s) still to collect",
                "detail": "Dispensed and waiting for the patient.",
                "to": "/retail/prescriptions",
                "tone": "info",
            }
        )

    return items


# --------------------------------------------------------------------------- #
# Segregation of duties
# --------------------------------------------------------------------------- #


def control_notice(organization: Organization) -> dict[str, Any] | None:
    """Say plainly when one person can do the whole cycle unchecked.

    A pharmacy where the same account creates the order, receives the goods,
    enters the supplier's invoice and approves the payment has no separation of
    duties. That is an ordinary and unavoidable fact of a two-person business —
    but pretending it is not true is how a system ends up implying a control it
    does not have.

    So it is stated, not enforced. Nobody is blocked; the owner is told what
    the arrangement means and what would reduce the exposure. Refusing to let
    a one-person pharmacy buy stock would not be a control, it would be an
    outage.
    """
    from apps.iam.models import User as UserModel

    people = UserModel.objects.filter(organization=organization, is_active=True)
    total = people.count()
    if total > 2:
        return None

    full_cycle = [
        user.get_full_name() or user.username
        for user in people
        if user.is_superuser
        or all(
            user.has_permission(code)
            for code in ("order.create", "order.receive", "finance.manage")
        )
    ]
    if not full_cycle:
        return None

    return {
        "severity": "info" if total > 1 else "warning",
        "headline": (
            "One person can complete the whole purchase cycle here."
            if total == 1
            else "Purchasing and payment are not separated here."
        ),
        "body": (
            f"{', '.join(full_cycle)} can create a purchase order, receive the goods "
            "against it, and approve the payment. In a pharmacy this size that is "
            "normal and often unavoidable — it is recorded rather than prevented, "
            "because refusing it would stop you buying stock."
        ),
        "what_helps": [
            "Every action is in the audit log against a named person, including deletions.",
            "Approving your own request is allowed here but must carry a written reason, "
            "and is flagged as self-approved wherever it appears.",
            "Count the till at the end of each day — the variance is the check that "
            "does not need a second person.",
            "An outside accountant reviewing the month is the cheapest real separation "
            "available at this size.",
        ],
        "people": total,
    }


# --------------------------------------------------------------------------- #


def pharmacy_day(user: User, *, on: date | None = None) -> dict[str, Any]:
    """The whole morning briefing, in one call."""
    orgs = organizations_visible_to(user)
    org_ids = list(orgs.values_list("id", flat=True))
    today = on or timezone.localdate()
    home = user.organization
    currency = (home.currency if home else "RWF") or "RWF"

    month_start = today.replace(day=1)
    yesterday = today - timedelta(days=1)

    day = _sales_between(org_ids, today, today)
    prior = _sales_between(org_ids, yesterday, yesterday)
    month = _sales_between(org_ids, month_start, today)
    month_expenses = _expenses_between(org_ids, month_start, today)

    def change(now: Decimal, before: Decimal) -> float | None:
        """Percentage change, or nothing when there is no base to compare to.

        Returning 0% for "yesterday we sold nothing" would read as "flat",
        which is the opposite of what happened.
        """
        if before <= 0:
            return None
        return float(((now - before) / before * 100).quantize(Decimal("0.1")))

    return {
        "as_of": today.isoformat(),
        "organization": {
            "id": home.pk if home else None,
            "name": home.name if home else "",
            "size": home.size if home else Organization.Size.MICRO,
            "currency": currency,
        },
        "today": {
            "revenue": _money(day["revenue"], currency),
            "cost_of_goods": _money(day["cost_of_goods"], currency),
            "gross_profit": _money(day["gross_profit"], currency),
            "gross_margin_pct": day["gross_margin_pct"],
            "transactions": day["transactions"],
            "average_basket": _money(day["average_basket"], currency),
            "revenue_change_pct": change(day["revenue"], prior["revenue"]),
            "lines_without_cost": day["lines_without_cost"],
        },
        "month": {
            "from": month_start.isoformat(),
            "revenue": _money(month["revenue"], currency),
            "cost_of_goods": _money(month["cost_of_goods"], currency),
            "gross_profit": _money(month["gross_profit"], currency),
            "gross_margin_pct": month["gross_margin_pct"],
            "operating_expenses": _money(month_expenses, currency),
            "operating_result": _money(month["gross_profit"] - month_expenses, currency),
            "transactions": month["transactions"],
            # Whether the operating result means anything yet. With no expenses
            # recorded it is just gross profit wearing a different name.
            "expenses_recorded": month_expenses > 0,
        },
        "stock_value": _money(_stock_value(org_ids), currency),
        "needs_attention": _needs_attention(org_ids, today),
        "control_notice": control_notice(home) if home else None,
    }
