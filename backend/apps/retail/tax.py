"""What VAT a pharmacy actually charges.

Every sale line took its rate from the product's tax class and nothing else, so
every pharmacy in the system charged 18% on standard-rated medicines whether or
not it was registered for VAT.

That is the wrong way round for Rwanda. The RRA makes registration compulsory
above **RWF 20,000,000** of turnover in any twelve months, or RWF 5,000,000 in
the preceding quarter. Below that a pharmacy is not registered and must not
charge VAT: the 18% belongs to nobody, it overcharges the customer, and it
records a liability the pharmacy never owed and will be asked to explain.

Most Rwandan community pharmacies are under the threshold. So for most of them
the till was wrong on every line it rang.

Two questions, kept apart because they have different answers:

* **is this pharmacy registered?** — a fact about the business, set by somebody
  who has the certificate.
* **is this product standard-rated?** — a fact about the medicine, which stays
  true either way and still matters the day the pharmacy does register.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.retail.models import TAX_RATES

ZERO = Decimal("0")

#: Turnover above which VAT registration is compulsory (RRA). Held here so the
#: figure that drives the warning is written down once, next to what it means.
VAT_THRESHOLD_ANNUAL = Decimal("20000000")
VAT_THRESHOLD_QUARTERLY = Decimal("5000000")


def rate_for(*, product: Any, organization: Any) -> Decimal:
    """The VAT rate this line is actually charged at.

    Zero for an unregistered pharmacy, whatever the product's class says. The
    class is not overwritten anywhere — it is simply not applied, so the day the
    pharmacy registers, every medicine already carries the right rate.
    """
    if not getattr(organization, "is_vat_registered", False):
        return ZERO
    return TAX_RATES.get(str(getattr(product, "tax_class", "") or ""), ZERO)


def registration_check(organization: Any, *, turnover_12m: Decimal) -> dict[str, Any] | None:
    """Whether this pharmacy has crossed the threshold without registering.

    Returned rather than enforced. Registering is something the owner does at
    the RRA; the system's job is to tell them the day it becomes compulsory,
    not to start charging a tax they have no number for.
    """
    if getattr(organization, "is_vat_registered", False):
        return None
    if turnover_12m < VAT_THRESHOLD_ANNUAL:
        return None
    return {
        "severity": "warning",
        "headline": "You have passed the VAT registration threshold.",
        "body": (
            f"Sales over the last twelve months come to {turnover_12m:,.0f} RWF, above the "
            f"RRA's {VAT_THRESHOLD_ANNUAL:,.0f} RWF threshold. Registration for VAT is "
            "compulsory above it. Until you register here, the till charges no VAT — which "
            "is correct today and will be wrong once you are registered."
        ),
        "turnover": f"{turnover_12m:.2f}",
        "threshold": f"{VAT_THRESHOLD_ANNUAL:.2f}",
    }
