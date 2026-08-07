"""Posting accruals and prepayments month by month.

The interesting decisions here are about *not* posting:

* A schedule never charges a month twice — the run table's unique constraint is
  the guard, not a flag someone remembers to check.
* The final period absorbs the rounding remainder, so twelve months of
  1,000,000 / 12 add up to 1,000,000 and not 999,999.96. A schedule that does not
  fully release its balance leaves a permanent stub on the balance sheet that
  nobody can ever explain.
* Accruals reverse by default, so the real invoice can be posted normally when it
  arrives without the cost being counted twice.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction

from apps.iam.models import Organization, User

from .models import Account, CostCentre, JournalEntry, JournalLine, RecurringSchedule, ScheduleRun
from .services import JournalLineInput, ensure_default_accounts, post_journal

ZERO = Decimal("0.00")
D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT


class ScheduleError(Exception):
    """Raised when a schedule would post something incoherent."""


def _q(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _month_end(day: date) -> date:
    nxt = date(day.year + (day.month // 12), (day.month % 12) + 1, 1)
    return nxt - timedelta(days=1)


def _add_months(day: date, months: int) -> date:
    total = day.month - 1 + months
    return date(day.year + total // 12, total % 12 + 1, 1)


def schedule_months(schedule: RecurringSchedule) -> list[date]:
    """Every month this schedule covers, as first-of-month dates."""
    start = _month_start(schedule.start_month)
    return [_add_months(start, i) for i in range(schedule.periods)]


def amount_for_period(schedule: RecurringSchedule, period_month: date) -> Decimal:
    """The charge for one month, with the last month taking the remainder.

    Spreading 1,000,000 over 12 gives 83,333.33 a month, which leaves 0.04
    unreleased after a year. Left alone that becomes a balance nobody can clear.
    """
    months = schedule_months(schedule)
    if period_month not in months:
        return ZERO
    per = schedule.amount_per_period
    if period_month == months[-1]:
        return _q(schedule.total_amount - per * (len(months) - 1))
    return per


@transaction.atomic
def create_schedule(
    *,
    organization: Organization,
    name: str,
    kind: str,
    expense_account: Account,
    total_amount: Decimal,
    periods: int,
    start_month: date,
    cost_centre: CostCentre | None = None,
    auto_reverse: bool | None = None,
    source_reference: str = "",
    notes: str = "",
    user: User | None = None,
) -> RecurringSchedule:
    """Set up a spread. Posting happens month by month, not here."""
    if periods < 1:
        raise ScheduleError("A schedule must cover at least one month.")
    if _q(total_amount) <= 0:
        raise ScheduleError("A schedule needs a positive total.")
    if kind not in RecurringSchedule.Kind.values:
        raise ScheduleError(f"{kind!r} is not a valid schedule kind.")

    return RecurringSchedule.objects.create(
        organization=organization,
        name=name,
        kind=kind,
        expense_account=expense_account,
        cost_centre=cost_centre,
        total_amount=_q(total_amount),
        periods=periods,
        start_month=_month_start(start_month),
        # Prepayments never reverse: the asset really is being consumed.
        auto_reverse=(
            False
            if kind == RecurringSchedule.Kind.PREPAYMENT
            else (True if auto_reverse is None else auto_reverse)
        ),
        source_reference=source_reference,
        notes=notes,
        created_by=user,
    )


@transaction.atomic
def post_period(
    *, schedule: RecurringSchedule, period_month: date, user: User | None = None
) -> ScheduleRun | None:
    """Charge one month of a schedule to the P&L.

        Prepayment:  Dr expense   Cr 1600 Prepayments
        Accrual:     Dr expense   Cr 2170 Accruals

    Returns the existing run untouched if the month has already been charged, so
    a re-run is safe. Returns None if the month is outside the schedule.
    """
    if schedule.status != RecurringSchedule.Status.ACTIVE:
        return None

    month = _month_start(period_month)
    amount = amount_for_period(schedule, month)
    if amount <= 0:
        return None

    existing = schedule.runs.filter(period_month=month).first()
    if existing is not None:
        return existing

    accounts = ensure_default_accounts(schedule.organization)
    balance_account = accounts[schedule.balance_account_code]
    charge_date = _month_end(month)

    lines: list[JournalLineInput] = [
        {
            "account": schedule.expense_account,
            "side": D,
            "amount": amount,
            "memo": schedule.name[:200],
        },
        {
            "account": balance_account,
            "side": C,
            "amount": amount,
            "memo": schedule.name[:200],
        },
    ]
    entry = post_journal(
        organization=schedule.organization,
        entry_date=charge_date,
        description=f"{schedule.get_kind_display()} — {schedule.name}",
        lines=lines,
        reference_type="recurring_schedule",
        reference_id=f"{schedule.pk}:{month:%Y-%m}",
        source_module=JournalEntry.Source.CLOSE,
        cost_centre=schedule.cost_centre,
        user=user,
    )

    reversal = None
    if schedule.auto_reverse:
        # Straight back out on the first of the next month, so the supplier's
        # invoice can be posted normally without counting the cost twice.
        reversal = post_journal(
            organization=schedule.organization,
            entry_date=charge_date + timedelta(days=1),
            description=f"Reversal of {schedule.name}",
            lines=[
                {
                    "account": balance_account,
                    "side": D,
                    "amount": amount,
                    "memo": schedule.name[:200],
                },
                {
                    "account": schedule.expense_account,
                    "side": C,
                    "amount": amount,
                    "memo": schedule.name[:200],
                },
            ],
            reference_type="recurring_schedule_reversal",
            reference_id=f"{schedule.pk}:{month:%Y-%m}",
            source_module=JournalEntry.Source.CLOSE,
            cost_centre=schedule.cost_centre,
            user=user,
        )

    run = ScheduleRun.objects.create(
        schedule=schedule,
        period_month=month,
        amount=amount,
        journal_entry=entry,
        reversal_entry=reversal,
    )

    if schedule.runs.count() >= schedule.periods:
        schedule.status = RecurringSchedule.Status.COMPLETED
        schedule.save(update_fields=["status"])
    return run


@transaction.atomic
def run_schedules(
    *, organization: Organization, as_of: date, user: User | None = None
) -> dict[str, Any]:
    """Post every active schedule that is due for the month containing `as_of`.

    Catches up quietly: a schedule started three months ago and never run posts
    all three months, each dated to the month it belongs to, rather than dumping
    the whole backlog into the current period.
    """
    month = _month_start(as_of)
    posted: list[ScheduleRun] = []
    for schedule in RecurringSchedule.objects.filter(
        organization=organization, status=RecurringSchedule.Status.ACTIVE
    ).select_related("expense_account", "cost_centre"):
        already = set(schedule.runs.values_list("period_month", flat=True))
        for candidate in schedule_months(schedule):
            if candidate > month:
                break
            if candidate in already:
                continue
            run = post_period(schedule=schedule, period_month=candidate, user=user)
            if run is not None:
                posted.append(run)
    return {
        "as_of": as_of.isoformat(),
        "schedules_posted": len({r.schedule_id for r in posted}),
        "runs": len(posted),
        "total": str(_q(sum((r.amount for r in posted), ZERO))),
    }


@transaction.atomic
def cancel_schedule(*, schedule: RecurringSchedule, reason: str) -> RecurringSchedule:
    """Stop future charges. Whatever has already been posted stays posted."""
    if not reason.strip():
        raise ScheduleError("Cancelling a schedule requires a reason.")
    schedule.status = RecurringSchedule.Status.CANCELLED
    schedule.notes = f"{schedule.notes}\nCancelled: {reason.strip()}".strip()
    schedule.save(update_fields=["status", "notes"])
    return schedule


def schedule_summary(organization: Organization, *, as_of: date) -> dict[str, Any]:
    """What is still sitting in prepayments and accruals, and what is overdue to post."""
    month = _month_start(as_of)
    rows: list[dict[str, Any]] = []
    prepaid = accrued = ZERO

    for schedule in RecurringSchedule.objects.filter(
        organization=organization, status=RecurringSchedule.Status.ACTIVE
    ).prefetch_related("runs"):
        due = [m for m in schedule_months(schedule) if m <= month]
        posted_months = {r.period_month for r in schedule.runs.all()}
        outstanding = [m for m in due if m not in posted_months]
        remaining = schedule.remaining
        if schedule.kind == RecurringSchedule.Kind.PREPAYMENT:
            prepaid += remaining
        else:
            accrued += remaining
        rows.append(
            {
                "id": schedule.pk,
                "name": schedule.name,
                "kind": schedule.kind,
                "account": schedule.expense_account.code,
                "total": str(schedule.total_amount),
                "posted": str(_q(schedule.posted_total)),
                "remaining": str(_q(remaining)),
                "months_outstanding": len(outstanding),
            }
        )

    return {
        "as_of": as_of.isoformat(),
        "prepayments_remaining": str(_q(prepaid)),
        "accruals_remaining": str(_q(accrued)),
        "schedules": rows,
        "overdue": [r for r in rows if r["months_outstanding"] > 0],
    }
