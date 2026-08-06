"""Gapless transactional numbering for every document kind.

A single primitive (:func:`next_number`) that the documents engine, the
journal engine, the AR/AP engines, the HR payslip engine, and the
statutory filing engine all call under :class:`apps.procurement.models.NumberSequence`.

The contract:

* **Gapless** within ``(organization, domain, kind, year)`` — two callers
  cannot take the same number.
* **Transactional** — the SELECT … FOR UPDATE row lock is held for the
  duration of the surrounding ``transaction.atomic()``; the bumped
  ``next_number`` and the consuming insert happen together or not at
  all.
* **Monotonic** — the value never goes backwards.
* **Domain-namespaced** — see ADR-014. A finance JOURNAL_ENTRY-2026-00001
  and a procurement REQUISITION-2026-00001 are different rows in the
  same table.

Callers should raise an outer ``transaction.atomic()`` so the bump is
rolled back if the consuming insert fails.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone


class NumberingError(Exception):
    """Raised when a numbering operation fails (year missing, etc.)."""


def next_number(
    *,
    organization,
    domain: str,
    kind: str,
    year: int | None = None,
) -> int:
    """Allocate and return the next gapless number for the (org, domain, kind, year).

    Returns the allocated number, never the *next* number after it. So the
    first call returns 1, the second returns 2, etc.

    Must be called inside ``transaction.atomic()`` so the row lock is held
    until the consuming insert commits. The caller pattern:

        with transaction.atomic():
            n = next_number(organization=org, domain=..., kind=..., year=...)
            MyDocument.objects.create(number=f"{kind}-{year}-{n:05d}", ...)
    """
    # Imported lazily so this helper doesn't drag the procurement app at
    # import time (helps with cycle-free tests).
    from apps.procurement.models import NumberSequence

    year = year or timezone.now().year

    with transaction.atomic():
        seq, _created = NumberSequence.objects.select_for_update().get_or_create(
            organization=organization,
            domain=domain,
            kind=kind,
            year=year,
        )
        number = seq.next_number
        seq.next_number = number + 1
        seq.save(update_fields=["next_number"])
        return number


def next_document_number(
    *,
    organization,
    domain: str,
    kind: str,
    year: int | None = None,
    width: int = 5,
    prefix: str | None = None,
) -> str:
    """Convenience: return the formatted document string e.g. ``PO-2026-00042``.

    ``prefix`` defaults to the upper-case ``kind``; pass an explicit value
    to override (e.g. ``AR-INV-2026-00042`` for customer invoices).
    """
    n = next_number(
        organization=organization,
        domain=domain,
        kind=kind,
        year=year,
    )
    y = year or timezone.now().year
    p = (prefix or kind).upper()
    return f"{p}-{y}-{n:0{width}d}"