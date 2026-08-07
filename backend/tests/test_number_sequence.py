"""Tests for NumberSequence + the next_number helper (F4.1 + F4.2).

The numbering primitive must be:
- Gapless within (organization, domain, kind, year)
- Safe under concurrent callers (SELECT … FOR UPDATE)
- Domain-namespaced so finance and HR don't collide
- Idempotent — calling next_number() twice returns the next two numbers
"""

from __future__ import annotations

import pytest
from apps.procurement.models import NumberSequence

pytestmark = pytest.mark.django_db


def test_unique_per_organization_domain_kind_year(organization):
    """(org, domain, kind, year) is unique."""
    NumberSequence.objects.create(
        organization=organization,
        domain=NumberSequence.Domain.FINANCE,
        kind=NumberSequence.Kind.JOURNAL_ENTRY,
        year=2026,
        next_number=1,
    )
    # Same (org, domain=PROC, kind=PR, year) is allowed; different domain is too.
    NumberSequence.objects.create(
        organization=organization,
        domain=NumberSequence.Domain.PROCUREMENT,
        kind=NumberSequence.Kind.JOURNAL_ENTRY,  # noqa: same kind, different domain
        year=2026,
        next_number=1,
    )


def test_unique_constraint_rejects_duplicate_combo(organization):
    NumberSequence.objects.create(
        organization=organization,
        domain=NumberSequence.Domain.FINANCE,
        kind=NumberSequence.Kind.JOURNAL_ENTRY,
        year=2026,
    )
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        NumberSequence.objects.create(
            organization=organization,
            domain=NumberSequence.Domain.FINANCE,
            kind=NumberSequence.Kind.JOURNAL_ENTRY,
            year=2026,
        )


def test_domain_field_defaults_to_procurement(organization):
    """Existing rows (added via the model default) keep working."""
    seq = NumberSequence.objects.create(
        organization=organization,
        kind=NumberSequence.Kind.PURCHASE_ORDER,
        year=2026,
    )
    assert seq.domain == NumberSequence.Domain.PROCUREMENT
