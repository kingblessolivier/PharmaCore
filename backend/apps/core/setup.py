"""Four questions, asked once, that decide what the pharmacy sees.

A pharmacy signing up is currently handed the whole system and left to work out
which forty screens it needs. The answers below take about a minute and settle
it: how the place is staffed, whether it is registered for VAT, and what it
wants the system to do at all.

None of it removes capability. `feature_flags` decides what is *offered* on the
navigation; every route, permission and API stays exactly where it was, so a
pharmacy that later starts doing insurance turns it on rather than being
migrated. That distinction is the whole design — see `Organization.Size`.

**VAT is asked, not assumed.** The RRA makes registration compulsory above
RWF 20,000,000 of turnover in twelve months. Below it a pharmacy must not charge
VAT, and the system charged it anyway on every line because nothing had ever
asked. It is the one answer here with a consequence on the money.
"""

from __future__ import annotations

from typing import Any, Final

from apps.iam.models import Organization

#: What the system can be asked to manage, and what each turns on.
#:
#: Selling and stock are not in the list: a pharmacy that does neither is not a
#: pharmacy, and offering to switch them off is a question with one sensible
#: answer, which is not a question.
OPTIONAL_AREAS: Final[dict[str, str]] = {
    "purchasing": "Ordering from suppliers and receiving deliveries",
    "finance": "Money in, money out, and the books",
    "insurance": "Claiming from RSSB, CBHI and private schemes",
    "customers": "Customer accounts and credit",
    "hr": "Staff records, payroll and statutory filings",
    "distribution": "Selling on to other pharmacies",
    "quality": "Complaints, deviations and CAPA",
}

#: How many people maps to how the place works. Asked as a range because an
#: owner knows "two of us" and does not know what MICRO means.
SIZE_BY_HEADCOUNT: Final[dict[str, str]] = {
    "1": Organization.Size.MICRO,
    "2-5": Organization.Size.SMALL,
    "6-20": Organization.Size.MEDIUM,
    "20+": Organization.Size.ENTERPRISE,
}


class SetupError(ValueError):
    """The answers do not describe a pharmacy that can be configured."""


def apply_setup(
    *,
    organization: Organization,
    headcount: str,
    branches: int = 1,
    manages: list[str] | None = None,
    vat_registered: bool = False,
    vat_registration_no: str = "",
) -> Organization:
    """Write the answers onto the organisation.

    Deliberately forgiving about *which* areas are named and strict about the
    two that change behaviour — size and VAT — because those are the ones that
    are wrong in a way somebody has to notice later.
    """
    if headcount not in SIZE_BY_HEADCOUNT:
        raise SetupError(
            f"'{headcount}' is not one of {', '.join(SIZE_BY_HEADCOUNT)} — "
            "how many people work here?"
        )
    if branches < 1:
        raise SetupError("A pharmacy has at least one location.")
    if vat_registered and not vat_registration_no.strip():
        raise SetupError(
            "A VAT-registered pharmacy has a VAT registration number. "
            "It goes on every invoice you issue, so it is needed before the till "
            "starts charging VAT."
        )

    size = SIZE_BY_HEADCOUNT[headcount]
    # Several branches is not a two-person shop however few people are at each.
    if branches > 1 and size in (Organization.Size.MICRO, Organization.Size.SMALL):
        size = Organization.Size.MEDIUM

    chosen = [area for area in (manages or []) if area in OPTIONAL_AREAS]
    flags = dict(organization.feature_flags or {})
    for area in OPTIONAL_AREAS:
        flags[area] = area in chosen

    organization.size = size
    organization.feature_flags = flags
    organization.is_vat_registered = bool(vat_registered)
    organization.vat_registration_no = vat_registration_no.strip()
    organization.save(
        update_fields=["size", "feature_flags", "is_vat_registered", "vat_registration_no"]
    )
    return organization


def setup_state(organization: Organization) -> dict[str, Any]:
    """What the wizard needs to show, and whether it has been answered before."""
    flags = organization.feature_flags or {}
    return {
        "organization": organization.pk,
        "name": organization.name,
        "size": organization.size,
        "is_vat_registered": organization.is_vat_registered,
        "vat_registration_no": organization.vat_registration_no,
        "manages": sorted(area for area in OPTIONAL_AREAS if flags.get(area)),
        "areas": [{"key": key, "label": label} for key, label in OPTIONAL_AREAS.items()],
        "headcount_options": sorted(SIZE_BY_HEADCOUNT),
        # A pharmacy that has never answered has no flags at all. Distinguished
        # from one that answered and chose nothing, which is a real answer.
        "answered": any(area in flags for area in OPTIONAL_AREAS),
    }
