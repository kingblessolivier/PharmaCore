"""What a tax invoice has to say, worked out once.

A tax invoice is a statutory document. The parts below are the ones the
templates were missing and that every caller would otherwise have to assemble
for itself — which is how two invoices from the same system come to disagree
about what the VAT was.

The rule throughout: **arithmetic happens here, never in a template.** A
template that adds numbers is a second, invisible implementation of the ledger,
and the two drift.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

#: Rwanda's tax classes, and what each one actually charges. Kept here rather
#: than in a template so a rate change is one edit, not a search.
TAX_CLASS_RATES: Final[dict[str, Decimal]] = {
    "A": Decimal("0"),  # exempt
    "B": Decimal("18"),  # standard-rated
    "C": Decimal("0"),  # zero-rated
    "D": Decimal("0"),  # special
}

TAX_CLASS_LABELS: Final[dict[str, str]] = {
    "A": "Exempt",
    "B": "18%",
    "C": "0%",
    "D": "Special",
}

_ONES: Final = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS: Final = "  twenty thirty forty fifty sixty seventy eighty ninety".split(" ")
_SCALES: Final = ((10**9, "billion"), (10**6, "million"), (1000, "thousand"))


def money(value: Any) -> str:
    """Two decimal places, thousands separated — the way money is read."""
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:,.2f}"


def _under_thousand(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, rest = divmod(n, 10)
        word = _TENS[tens]
        return f"{word}-{_ONES[rest]}" if rest else word
    hundreds, rest = divmod(n, 100)
    head = f"{_ONES[hundreds]} hundred"
    return f"{head} and {_under_thousand(rest)}" if rest else head


def in_words(value: Any, *, currency: str = "RWF") -> str:
    """Spell an amount out, the way a cheque or an invoice footer does.

    It exists to make tampering obvious: altering a digit is easy, altering a
    digit *and* the words is not, which is why the convention survives.
    """
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    negative = amount < 0
    amount = abs(amount)
    whole = int(amount)
    cents = int((amount - whole) * 100)

    if whole == 0:
        words = "zero"
    else:
        parts: list[str] = []
        remainder = whole
        for size, name in _SCALES:
            count, remainder = divmod(remainder, size)
            if count:
                parts.append(f"{_under_thousand(count)} {name}")
        if remainder:
            parts.append(_under_thousand(remainder))
        words = " ".join(parts)

    out = f"{words} {'francs' if currency == 'RWF' else currency}"
    if cents:
        out += f" and {_under_thousand(cents)} cents"
    out = f"{out} only"
    if negative:
        out = f"minus {out}"
    return out[0].upper() + out[1:]


def vat_bands(lines: list[dict[str, Any]]) -> list[dict[str, str]]:
    """VAT grouped by the rate that produced it.

    Legally required, and not a formatting nicety: a line at 18% and an exempt
    line cannot be summed into one VAT figure, because the buyer reclaims
    against the standard-rated portion only. An invoice showing a single total
    tells them nothing they can act on.

    Each line may state ``tax_rate`` directly, or a ``tax_class`` this maps.
    """
    grouped: dict[str, dict[str, Decimal]] = {}
    for line in lines:
        rate = line.get("tax_rate")
        if rate is None:
            rate = TAX_CLASS_RATES.get(str(line.get("tax_class", "")).upper(), Decimal("0"))
        rate = Decimal(str(rate))
        net = Decimal(str(line.get("net", line.get("total", 0)) or 0))
        vat = Decimal(str(line.get("tax_amount", net * rate / 100)))

        key = f"{rate.normalize():f}"
        band = grouped.setdefault(key, {"taxable": Decimal("0"), "amount": Decimal("0")})
        band["taxable"] += net
        band["amount"] += vat

    return [
        {
            "rate": f"{Decimal(rate):g}%",
            "taxable": money(band["taxable"]),
            "amount": money(band["amount"]),
        }
        for rate, band in sorted(grouped.items(), key=lambda kv: Decimal(kv[0]), reverse=True)
    ]


def party(source: Any, *, fallback_name: str = "") -> dict[str, str]:
    """The identifying block for one side of a document.

    A customer's TIN is not decoration: without it a VAT-registered buyer
    cannot reclaim the input VAT, so an invoice that omits it is worthless to
    them. Pulled from whatever the caller has — an Organization, a Customer, a
    Supplier — because all three appear on one document or another.
    """
    if source is None:
        return {"name": fallback_name}

    def get(*names: str) -> str:
        for name in names:
            value = getattr(source, name, "")
            if value:
                return str(value)
        return ""

    address = get("address_line", "address")
    district = get("district")
    if district and district not in address:
        address = f"{address}, {district}".strip(", ")

    return {
        "name": get("name", "legal_name") or fallback_name,
        "address": address,
        "tin": get("tin"),
        "phone": get("phone", "contact_phone"),
        "email": get("email"),
    }


def invoice_context(
    *,
    seller: Any,
    buyer: Any,
    lines: list[dict[str, Any]],
    subtotal: Any,
    tax_total: Any,
    total: Any,
    currency: str = "RWF",
    **extra: Any,
) -> dict[str, Any]:
    """Everything the tax-invoice template needs, assembled the same way twice.

    Two places raise tax invoices — a depot billing a pharmacy, and finance
    billing a customer — and they were building different context dictionaries
    for the same template, so the two documents differed in what they showed.
    """
    seller_party = party(seller)
    buyer_party = party(buyer)
    context: dict[str, Any] = {
        "seller_name": seller_party["name"],
        "seller_address": seller_party.get("address", ""),
        "seller_tin": seller_party.get("tin", ""),
        "seller_phone": seller_party.get("phone", ""),
        "buyer_name": buyer_party["name"],
        "buyer_address": buyer_party.get("address", ""),
        "buyer_tin": buyer_party.get("tin", ""),
        "buyer_phone": buyer_party.get("phone", ""),
        "lines": lines,
        "subtotal": money(subtotal),
        "tax_total": money(tax_total),
        "total": money(total),
        "vat_bands": vat_bands(lines),
        "amount_in_words": in_words(total, currency=currency),
        "currency": currency,
    }
    context.update(extra)
    return context
