"""Postings that keep the ledger faithful to what the business actually did.

Each function here closes a hole where money moved in the real world and the
books never heard about it:

* **Card settlement** — a card sale is not cash on the day. The acquirer pays
  T+1/T+2, net of a fee. Until this posts, `1150 Card Settlement in Transit`
  sits open and the fee is never expensed.
* **Till over/short** — `DrawerSession` computed a variance and stored it. A
  cash shortage is a real cost; storing it next to the count and never posting
  it means it never reaches the P&L.
* **Depreciation** — the asset register knew useful lives and salvage values and
  nothing ever charged the periodic expense, so assets sat at cost until the day
  they were sold and EBITDA's depreciation add-back was permanently zero.
* **Expiry provision** — IAS 2 carries stock at the lower of cost and net
  realisable value. The provision was computed for a dashboard and never posted,
  so the balance sheet still valued expiring stock at full cost.

See docs/development/finance-redesign-plan.md §1a.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.iam.models import Organization, User

from .models import Account, FixedAsset, JournalEntry, JournalLine
from .services import JournalLineInput, ensure_default_accounts, post_journal

ZERO = Decimal("0.00")
D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT


def _q(value: Decimal | int | float | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _month_end(day: date) -> date:
    nxt = date(day.year + (day.month // 12), (day.month % 12) + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


# --------------------------------------------------------------------------- #
# Card settlement
# --------------------------------------------------------------------------- #


@transaction.atomic
def settle_card_batch(
    *,
    organization: Organization,
    gross: Decimal,
    fee: Decimal = ZERO,
    settled_on: date | None = None,
    reference: str = "",
    bank_account_code: str = "1200",
    user: User | None = None,
) -> JournalEntry:
    """Clear card takings out of transit when the acquirer pays.

        Dr 1200 Bank            net received
        Dr 6150 Card charges    the acquirer's fee
        Cr 1150 In transit      gross taken at the till

    The fee is a real operating cost of taking cards and belongs in the P&L, not
    netted silently against revenue where nobody can see what it costs to accept
    a card.
    """
    gross, fee = _q(gross), _q(fee)
    if gross <= 0:
        raise ValueError("A card settlement must have a positive gross amount.")
    if fee < 0 or fee > gross:
        raise ValueError("The acquirer fee must be between zero and the gross amount.")

    accounts = ensure_default_accounts(organization)
    when = settled_on or timezone.localdate()
    net = _q(gross - fee)

    lines: list[JournalLineInput] = [
        {
            "account": accounts[bank_account_code],
            "side": D,
            "amount": net,
            "memo": "Card settlement received",
        },
    ]
    if fee > 0:
        lines.append(
            {"account": accounts["6150"], "side": D, "amount": fee, "memo": "Acquirer fee"}
        )
    lines.append(
        {"account": accounts["1150"], "side": C, "amount": gross, "memo": "Card takings cleared"}
    )

    return post_journal(
        organization=organization,
        entry_date=when,
        description=f"Card settlement {reference}".strip(),
        lines=lines,
        reference_type="card_settlement",
        reference_id=reference or f"{organization.pk}:{when.isoformat()}",
        source_module=JournalEntry.Source.TREASURY,
        user=user,
    )


# --------------------------------------------------------------------------- #
# Till variance
# --------------------------------------------------------------------------- #


@transaction.atomic
def post_drawer_variance(*, drawer: Any, user: User | None = None) -> JournalEntry | None:
    """Post a closed drawer's over/short to the P&L.

    A shortage debits `6160 Cash Over / Short` and credits cash — the drawer holds
    less than the books say, and the difference is an expense. An overage is the
    mirror image. Returns None when the drawer balanced exactly, which is the
    outcome that needs no entry.
    """
    variance = _q(drawer.over_short)
    if variance == 0:
        return None
    if drawer.status != "CLOSED":
        raise ValueError("Only a closed drawer session has a variance to post.")

    organization = drawer.organization
    accounts = ensure_default_accounts(organization)
    amount = abs(variance)
    short = variance < 0

    lines: list[JournalLineInput] = (
        [
            {"account": accounts["6160"], "side": D, "amount": amount, "memo": "Till shortage"},
            {
                "account": accounts["1100"],
                "side": C,
                "amount": amount,
                "memo": "Cash counted short",
            },
        ]
        if short
        else [
            {"account": accounts["1100"], "side": D, "amount": amount, "memo": "Cash counted over"},
            {"account": accounts["6160"], "side": C, "amount": amount, "memo": "Till overage"},
        ]
    )

    closed_on = drawer.closed_at.date() if drawer.closed_at else timezone.localdate()
    return post_journal(
        organization=organization,
        entry_date=closed_on,
        description=f"Drawer #{drawer.pk} {'shortage' if short else 'overage'}",
        lines=lines,
        reference_type="drawer_variance",
        reference_id=str(drawer.pk),
        source_module=JournalEntry.Source.TREASURY,
        user=user,
    )


# --------------------------------------------------------------------------- #
# Depreciation
# --------------------------------------------------------------------------- #


def monthly_charge(asset: FixedAsset) -> Decimal:
    """Straight-line monthly depreciation for one asset."""
    life_months = (asset.useful_life_years or 0) * 12
    if life_months <= 0:
        return ZERO
    depreciable = _q(asset.acquisition_cost) - _q(asset.salvage_value)
    if depreciable <= 0:
        return ZERO
    return _q(depreciable / Decimal(life_months))


def depreciation_schedule(
    organization: Organization, *, as_of: date
) -> list[tuple[FixedAsset, Decimal]]:
    """What each active asset should be charged this month, capped at cost.

    An asset never depreciates below its salvage value — once it is fully written
    down the charge stops, rather than running the carrying amount negative.
    """
    assets = FixedAsset.objects.filter(organization=organization, is_active=True).filter(
        Q(disposal_date__isnull=True) | Q(disposal_date__gt=as_of)
    )
    rows: list[tuple[FixedAsset, Decimal]] = []
    for asset in assets:
        if asset.acquisition_date > as_of:
            continue
        charge = monthly_charge(asset)
        if charge <= 0:
            continue
        depreciable = _q(asset.acquisition_cost) - _q(asset.salvage_value)
        remaining = depreciable - _q(asset.accumulated_depreciation)
        charge = min(charge, remaining)
        if charge > 0:
            rows.append((asset, _q(charge)))
    return rows


@transaction.atomic
def run_depreciation(
    *, organization: Organization, as_of: date, user: User | None = None
) -> JournalEntry | None:
    """Charge one month of depreciation across the whole asset register.

        Dr 6500 Depreciation Expense
        Cr 1701 Accumulated Depreciation

    One entry per organization per month, with a line per asset, keyed on the
    month so a re-run cannot double-charge. Returns None when there is nothing
    left to depreciate.
    """
    period_end = _month_end(as_of)
    rows = depreciation_schedule(organization, as_of=period_end)
    if not rows:
        return None

    accounts = ensure_default_accounts(organization)
    total = _q(sum((charge for _, charge in rows), ZERO))
    if total <= 0:
        return None

    reference_id = f"{period_end.year}-{period_end.month:02d}"
    existing = JournalEntry.objects.filter(
        organization=organization,
        reference_type="depreciation",
        reference_id=reference_id,
    ).first()
    if existing is not None:
        return existing

    lines: list[JournalLineInput] = [
        {
            "account": accounts["6500"],
            "side": D,
            "amount": charge,
            "memo": f"{asset.asset_number} {asset.name}"[:200],
        }
        for asset, charge in rows
    ]
    lines.append(
        {
            "account": accounts["1701"],
            "side": C,
            "amount": total,
            "memo": f"Depreciation for {reference_id}",
        }
    )

    entry = post_journal(
        organization=organization,
        entry_date=period_end,
        description=f"Depreciation — {reference_id}",
        lines=lines,
        reference_type="depreciation",
        reference_id=reference_id,
        source_module=JournalEntry.Source.CLOSE,
        user=user,
    )

    for asset, charge in rows:
        asset.accumulated_depreciation = _q(asset.accumulated_depreciation) + charge
        asset.save(update_fields=["accumulated_depreciation"])
    return entry


# --------------------------------------------------------------------------- #
# Expiry provision (IAS 2)
# --------------------------------------------------------------------------- #


def current_provision_balance(organization: Organization) -> Decimal:
    """What is already carried in 1590, as a positive number."""
    from django.db.models import Sum

    account = Account.objects.filter(organization=organization, code="1590").first()
    if account is None:
        return ZERO
    lines = JournalLine.objects.filter(account=account).exclude(
        entry__status=JournalEntry.Status.REVERSED
    )
    credit = lines.filter(side=C).aggregate(t=Sum("amount"))["t"] or ZERO
    debit = lines.filter(side=D).aggregate(t=Sum("amount"))["t"] or ZERO
    return _q(credit - debit)


@transaction.atomic
def post_expiry_provision(
    *, organization: Organization, as_of: date | None = None, user: User | None = None
) -> JournalEntry | None:
    """Move the stock provision to the level this month's expiry profile implies.

        Increase:  Dr 5900 Shrinkage    Cr 1590 Provision
        Release:   Dr 1590 Provision    Cr 5900 Shrinkage

    Only the *movement* is posted, not the whole provision, because the balance
    already carried is still valid — reversing and re-recognising the full amount
    every month would churn the P&L with two large offsetting entries and make
    the shrinkage line unreadable.

    Returns None when the required provision already matches what is carried.
    """
    from .pharmacy import inventory_expiry_exposure

    when = _month_end(as_of or timezone.localdate())
    exposure = inventory_expiry_exposure(organization, as_of=when)
    required = _q(exposure["suggested_provision"])
    carried = current_provision_balance(organization)
    movement = _q(required - carried)
    if movement == 0:
        return None

    accounts = ensure_default_accounts(organization)
    amount = abs(movement)
    increasing = movement > 0

    lines: list[JournalLineInput] = (
        [
            {
                "account": accounts["5900"],
                "side": D,
                "amount": amount,
                "memo": "Increase in expiry & slow-moving provision",
            },
            {"account": accounts["1590"], "side": C, "amount": amount, "memo": "Provision carried"},
        ]
        if increasing
        else [
            {
                "account": accounts["1590"],
                "side": D,
                "amount": amount,
                "memo": "Provision released",
            },
            {
                "account": accounts["5900"],
                "side": C,
                "amount": amount,
                "memo": "Release of expiry provision no longer required",
            },
        ]
    )

    return post_journal(
        organization=organization,
        entry_date=when,
        description=(
            f"Expiry provision {'increase' if increasing else 'release'} "
            f"to {required} (IAS 2 lower of cost and NRV)"
        ),
        lines=lines,
        reference_type="expiry_provision",
        reference_id=f"{when.year}-{when.month:02d}",
        source_module=JournalEntry.Source.CLOSE,
        user=user,
    )
