"""Restating foreign-currency balances at the closing rate.

The exposure is invisible without this. A supplier invoice booked at 1,300 RWF/USD
and settled at 1,350 costs half a million francs more than the books say, and no
transaction ever created that cost — the currency moved while the balance sat
there.

Two halves, and they are different:

* **Realised** difference — the rate on the day you paid against the rate on the
  day you booked. That is already handled at settlement.
* **Unrealised** difference — the rate at period end against the rate you booked,
  on balances still open. That is what this module posts, and what nothing was
  doing before.

Only monetary balances are restated (`Account.is_monetary`). Inventory bought in
dollars is *not* revalued: it is carried at what it cost on the day it arrived,
however the currency moves afterwards. Revaluing it would restate the cost of
goods that are simply sitting on a shelf.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction

from apps.iam.models import Organization, User

from .models import ExchangeRate, FxRevaluation, JournalEntry, JournalLine
from .services import JournalLineInput, ensure_default_accounts, post_journal

BASE_CURRENCY = "RWF"
ZERO = Decimal("0.00")
D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT


class FxError(Exception):
    """Raised when a revaluation cannot be done honestly."""


def _q(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rate_for(currency: str, *, on: date) -> Decimal:
    """The rate in force on a date — the latest published on or before it.

    Falling forward to a later rate would let a revaluation use information that
    did not exist yet, which is how a period gets restated with next month's news.
    """
    if not currency or currency == BASE_CURRENCY:
        return Decimal("1")
    rate = (
        ExchangeRate.objects.filter(currency=currency, rate_date__lte=on)
        .order_by("-rate_date")
        .first()
    )
    if rate is None:
        raise FxError(
            f"No exchange rate published for {currency} on or before {on}. "
            "A revaluation without a rate would be a guess."
        )
    return rate.rate_to_base


def convert(amount: Decimal, *, currency: str, on: date) -> Decimal:
    """Foreign amount to base currency at the rate in force."""
    return _q(Decimal(str(amount)) * rate_for(currency, on=on))


def _signed(line: JournalLine, field: str) -> Decimal:
    value = Decimal(str(getattr(line, field) or 0))
    return value if line.side == D else -value


def open_exposures(organization: Organization, *, as_of: date) -> list[dict[str, Any]]:
    """Every monetary balance held in a foreign currency, and what it is worth now.

    Grouped by (account, currency): one account can hold more than one currency,
    and each is restated at its own rate.
    """
    lines = (
        JournalLine.objects.filter(
            entry__organization=organization,
            entry__entry_date__lte=as_of,
            account__is_monetary=True,
        )
        .exclude(currency=BASE_CURRENCY)
        .exclude(entry__status=JournalEntry.Status.REVERSED)
        .select_related("account", "entry")
    )

    buckets: dict[tuple[int, str], dict[str, Any]] = {}
    for line in lines:
        key = (line.account_id, line.currency)
        bucket = buckets.setdefault(
            key,
            {
                "account": line.account,
                "currency": line.currency,
                "foreign_balance": ZERO,
                "carrying_amount": ZERO,
            },
        )
        # `amount_fc` is the figure the transaction was struck in; without it the
        # line cannot be restated, so it falls back to the base amount rather than
        # silently contributing zero.
        bucket["foreign_balance"] += _signed(line, "amount_fc") or _signed(line, "amount")
        bucket["carrying_amount"] += _signed(line, "amount")

    exposures: list[dict[str, Any]] = []
    for bucket in buckets.values():
        foreign = _q(bucket["foreign_balance"])
        carrying = _q(bucket["carrying_amount"])
        if foreign == 0 and carrying == 0:
            continue  # settled — nothing left to restate
        closing = rate_for(bucket["currency"], on=as_of)
        restated = _q(foreign * closing)
        exposures.append(
            {
                "account": bucket["account"],
                "account_code": bucket["account"].code,
                "account_name": bucket["account"].name,
                "currency": bucket["currency"],
                "foreign_balance": str(foreign),
                "closing_rate": str(closing),
                "carrying_amount": str(carrying),
                "restated_amount": str(restated),
                "difference": str(_q(restated - carrying)),
            }
        )
    return exposures


@transaction.atomic
def revalue(
    *, organization: Organization, as_of: date, user: User | None = None
) -> FxRevaluation | None:
    """Restate every open foreign monetary balance and take the difference to P&L.

        Gain:  Dr the monetary account   Cr 7100 FX gain / loss
        Loss:  Dr 7100 FX gain / loss    Cr the monetary account

    One entry for the whole organization per date, so a re-run returns the
    existing revaluation instead of posting the movement twice. Returns None when
    nothing needs restating — either no foreign balances, or the rate has not moved.
    """
    existing = FxRevaluation.objects.filter(organization=organization, as_of=as_of).first()
    if existing is not None:
        return existing

    exposures = open_exposures(organization, as_of=as_of)
    movements = [e for e in exposures if Decimal(e["difference"]) != 0]
    if not movements:
        return None

    accounts = ensure_default_accounts(organization)
    fx_account = accounts["7100"]
    lines: list[JournalLineInput] = []
    net = ZERO

    for exposure in movements:
        difference = Decimal(exposure["difference"])
        net += difference
        amount = abs(difference)
        memo = (
            f"{exposure['currency']} {exposure['foreign_balance']} " f"@ {exposure['closing_rate']}"
        )[:200]
        lines.append(
            {
                "account": exposure["account"],
                "side": D if difference > 0 else C,
                "amount": amount,
                "memo": memo,
            }
        )

    net = _q(net)
    lines.append(
        {
            "account": fx_account,
            "side": C if net > 0 else D,
            "amount": abs(net),
            "memo": "Unrealised FX on retranslation of monetary balances",
        }
    )

    entry = post_journal(
        organization=organization,
        entry_date=as_of,
        description=f"FX revaluation at {as_of}",
        lines=lines,
        reference_type="fx_revaluation",
        reference_id=as_of.isoformat(),
        source_module=JournalEntry.Source.CLOSE,
        user=user,
    )

    return FxRevaluation.objects.create(
        organization=organization,
        as_of=as_of,
        net_gain=net,
        # The account object is carried through `open_exposures` so the posting can
        # use it; the stored record keeps only what serialises.
        detail=[{k: v for k, v in m.items() if k != "account"} for m in movements],
        journal_entry=entry,
        run_by=user,
    )


def exposure_report(organization: Organization, *, as_of: date) -> dict[str, Any]:
    """What the currency is doing to the business, before anything is posted."""
    try:
        exposures = open_exposures(organization, as_of=as_of)
    except FxError as exc:
        return {
            "as_of": as_of.isoformat(),
            "exposures": [],
            "net_unrealised": "0.00",
            "computable": False,
            "interpretation": str(exc),
        }

    exposures = [{k: v for k, v in e.items() if k != "account"} for e in exposures]
    net = _q(sum((Decimal(e["difference"]) for e in exposures), ZERO))
    by_currency: dict[str, Decimal] = {}
    for exposure in exposures:
        by_currency[exposure["currency"]] = by_currency.get(exposure["currency"], ZERO) + Decimal(
            exposure["difference"]
        )

    return {
        "as_of": as_of.isoformat(),
        "exposures": exposures,
        "by_currency": {k: str(_q(v)) for k, v in by_currency.items()},
        "net_unrealised": str(net),
        "computable": True,
        "interpretation": (
            "No foreign-currency monetary balances are open."
            if not exposures
            else (
                f"Retranslating at today's rates would {'add' if net > 0 else 'cost'} "
                f"{abs(net)} — money nobody spent, created by the currency moving "
                "while these balances sat open."
            )
        ),
    }


def seed_rate(
    *, currency: str, rate_date: date, rate_to_base: Decimal, source: str = "BNR"
) -> ExchangeRate:
    """Record a published rate. Effective-dated, never overwritten in place."""
    rate, _ = ExchangeRate.objects.update_or_create(
        currency=currency.upper(),
        rate_date=rate_date,
        defaults={"rate_to_base": rate_to_base, "source": source},
    )
    return rate


def latest_rates(*, on: date | None = None) -> dict[str, str]:
    """The rate table as it stood on a date — what a screen shows in its header."""
    when = on or date.today()
    out: dict[str, str] = {}
    for currency in (
        ExchangeRate.objects.filter(rate_date__lte=when)
        .values_list("currency", flat=True)
        .distinct()
    ):
        try:
            out[currency] = str(rate_for(currency, on=when))
        except FxError:
            continue
    return out


def month_end(day: date) -> date:
    nxt = date(day.year + (day.month // 12), (day.month % 12) + 1, 1)
    return nxt - timedelta(days=1)
