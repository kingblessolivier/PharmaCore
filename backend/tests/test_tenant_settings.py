"""Tests for TenantSettings + tenant_settings_for() (F4.3)."""

from __future__ import annotations

import pytest

from apps.finance.models import TenantSettings
from apps.finance.services import tenant_settings_for

pytestmark = pytest.mark.django_db


def test_first_call_creates_row_with_defaults(organization):
    s = tenant_settings_for(organization)
    assert s.pk is not None
    assert s.base_currency == "RWF"
    assert s.costing_method == TenantSettings.CostingMethod.FEFO_LOT
    assert s.pay_period == TenantSettings.PayPeriod.MONTHLY
    assert s.statutory_remittance_day == 15
    assert s.pit_filing_deadline_month == 3
    assert s.pit_filing_deadline_day == 31
    assert s.default_country == "RW"
    assert s.timezone == "Africa/Kigali"


def test_second_call_returns_the_same_row(organization):
    a = tenant_settings_for(organization)
    b = tenant_settings_for(organization)
    assert a.pk == b.pk


def test_one_tenant_one_settings_row(organization):
    s = tenant_settings_for(organization)
    # A second create should fail at the DB layer (OneToOne + UNIQUE).
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        TenantSettings.objects.create(organization=organization)


def test_settings_are_editable_independently_by_tenant(organization):
    """Tenant A and Tenant B have separate settings rows. Editing one
    tenant's settings must not bleed into the other."""
    from apps.iam.models import Organization

    other = Organization.objects.create(
        name="Other",
        type=Organization.OrgType.RETAIL,
    )
    a = tenant_settings_for(organization)
    b = tenant_settings_for(other)
    assert a.pk != b.pk

    # Tenant A picks USD; Tenant B stays on the default.
    a.base_currency = "USD"
    a.save(update_fields=["base_currency", "updated_at"])
    b.refresh_from_db()
    assert b.base_currency == "RWF"


def test_costing_method_choices_include_fefo_lot(organization):
    s = tenant_settings_for(organization)
    s.costing_method = TenantSettings.CostingMethod.WAC
    s.save()
    s.refresh_from_db()
    assert s.costing_method == TenantSettings.CostingMethod.WAC
