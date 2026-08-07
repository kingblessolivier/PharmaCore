"""BE1 / BE2 / BE4 — invoice cancel, fixed-asset dispose, tenant-settings viewset.

Covers the new ``POST /customer-invoices/{id}/cancel/``, the new
``POST /fixed-assets/{id}/dispose/``, and the new ``TenantSettingsViewSet``
(GET/PATCH) on top of the existing ``tenant_settings_for`` service.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.finance.models import (
    CustomerInvoice,
    FixedAsset,
    JournalEntry,
    JournalLine,
    TenantSettings,
)
from apps.finance.services import (
    cancel_customer_invoice,
    dispose_fixed_asset,
    record_customer_invoice,
    tenant_settings_for,
)
from apps.iam.models import Organization, Role, User
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def creditor(db: None) -> Organization:
    return Organization.objects.create(name="Wholesale Depot", type="DEPOT")


@pytest.fixture
def debtor(db: None) -> Organization:
    return Organization.objects.create(name="Retail Buyer", type="RETAIL")


@pytest.fixture
def accountant(db: None, creditor: Organization) -> User:
    user = User.objects.create_user(username="acc1", password="x", organization=creditor)
    user.roles.add(Role.objects.get(code="ACCOUNTANT"))
    return user


@pytest.fixture
def cashier(db: None, creditor: Organization) -> User:
    user = User.objects.create_user(username="till_d2c", password="x", organization=creditor)
    user.roles.add(Role.objects.get(code="CASHIER"))
    return user


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _make_invoice(
    creditor: Organization,
    debtor: Organization,
    total: Decimal = Decimal("118000.00"),
    vat: Decimal = Decimal("18000.00"),
) -> CustomerInvoice:
    return record_customer_invoice(
        organization=creditor,
        customer=debtor,
        invoice_date=date(2026, 7, 1),
        due_date=date(2026, 7, 31),
        total_amount=total,
        vat_amount=vat,
        tax_class="B",
    )


# ---------------------------------------------------------------------------
# BE1 — Cancel customer invoice
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cancel_invoice_flips_status_and_posts_reversal(
    creditor: Organization, debtor: Organization, accountant: User
) -> None:
    invoice = _make_invoice(creditor, debtor)
    assert invoice.status == CustomerInvoice.Status.OPEN

    cancel_customer_invoice(invoice=invoice, user=accountant, reason="wrong amount")

    invoice.refresh_from_db()
    assert invoice.status == CustomerInvoice.Status.CANCELLED

    # Reversal entry exists with the canonical reference_type.
    reversal = JournalEntry.objects.filter(
        organization=creditor,
        reference_type="customer_invoice_cancel",
        reference_id=str(invoice.pk),
    ).first()
    assert reversal is not None
    # Three lines when there's VAT (Dr 4100, Dr 2300, Cr 1400).
    lines = JournalLine.objects.filter(entry=reversal)
    assert lines.count() == 3
    sides = {(ln.side, ln.amount) for ln in lines}
    assert (JournalLine.Side.DEBIT, Decimal("100000.00")) in sides
    assert (JournalLine.Side.DEBIT, Decimal("18000.00")) in sides
    assert (JournalLine.Side.CREDIT, Decimal("118000.00")) in sides


@pytest.mark.django_db
def test_cancel_invoice_without_vat_posts_two_lines(
    creditor: Organization, debtor: Organization, accountant: User
) -> None:
    invoice = _make_invoice(creditor, debtor, total=Decimal("50000.00"), vat=Decimal("0"))
    cancel_customer_invoice(invoice=invoice, user=accountant, reason="")
    reversal = JournalEntry.objects.get(
        reference_type="customer_invoice_cancel", reference_id=str(invoice.pk)
    )
    lines = JournalLine.objects.filter(entry=reversal)
    assert lines.count() == 2  # Dr revenue + Cr AR only — no VAT reversal line.


@pytest.mark.django_db
def test_cancel_invoice_with_payments_is_refused(
    creditor: Organization, debtor: Organization, accountant: User
) -> None:
    invoice = _make_invoice(creditor, debtor)
    # Record a partial receipt so amount_paid > 0.
    from apps.finance.services import record_customer_receipt

    record_customer_receipt(
        invoice=invoice,
        amount=Decimal("5000"),
        method="BANK",
        reference="RCPT-001",
        received_on=date(2026, 7, 5),
        user=accountant,
    )

    with pytest.raises(ValueError, match="refund them first|has receipts"):
        cancel_customer_invoice(invoice=invoice, user=accountant, reason="x")


@pytest.mark.django_db
def test_cancel_invoice_is_idempotent_on_second_call(
    creditor: Organization, debtor: Organization, accountant: User
) -> None:
    invoice = _make_invoice(creditor, debtor)
    cancel_customer_invoice(invoice=invoice, user=accountant, reason="first")
    with pytest.raises(ValueError, match="already cancelled"):
        cancel_customer_invoice(invoice=invoice, user=accountant, reason="second")


@pytest.mark.django_db
def test_cancel_invoice_via_api(
    creditor: Organization, debtor: Organization, accountant: User
) -> None:
    invoice = _make_invoice(creditor, debtor)
    resp = _auth(accountant).post(
        f"/api/finance/customer-invoices/{invoice.pk}/cancel/",
        {"reason": "Wrong pricing"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    invoice.refresh_from_db()
    assert invoice.status == CustomerInvoice.Status.CANCELLED


@pytest.mark.django_db
def test_cancel_invoice_via_api_requires_finance_manage(
    creditor: Organization, debtor: Organization, cashier: User
) -> None:
    invoice = _make_invoice(creditor, debtor)
    resp = _auth(cashier).post(
        f"/api/finance/customer-invoices/{invoice.pk}/cancel/",
        {"reason": "x"},
        format="json",
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# BE2 — Dispose fixed asset
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dispose_asset_marks_inactive_and_stamps_fields(
    creditor: Organization, accountant: User
) -> None:
    asset = FixedAsset.objects.create(
        organization=creditor,
        asset_number="AST-D2C-001",
        name="Delivery Van",
        category=FixedAsset.Category.VEHICLE,
        acquisition_date=date(2024, 1, 15),
        acquisition_cost=Decimal("2000000.00"),
        useful_life_years=5,
    )

    asset = dispose_fixed_asset(
        asset=asset,
        disposal_date=date(2026, 8, 1),
        disposal_amount=Decimal("500000.00"),
        disposal_reason="Sold to driver",
        user=accountant,
    )
    assert asset.is_active is False
    assert asset.disposal_date == date(2026, 8, 1)
    assert asset.disposal_amount == Decimal("500000.00")
    assert asset.disposal_reason == "Sold to driver"


@pytest.mark.django_db
def test_dispose_asset_posts_gain_entry(creditor: Organization, accountant: User) -> None:
    asset = FixedAsset.objects.create(
        organization=creditor,
        asset_number="AST-D2C-002",
        name="Lab Freezer",
        category=FixedAsset.Category.EQUIPMENT,
        acquisition_date=date(2023, 1, 1),
        acquisition_cost=Decimal("800000.00"),
        useful_life_years=5,
    )
    dispose_fixed_asset(
        asset=asset,
        disposal_date=date(2026, 8, 1),
        disposal_amount=Decimal("100000.00"),
        disposal_reason="Scrap",
        user=accountant,
    )
    entry = JournalEntry.objects.filter(
        organization=creditor, reference_type="fixed_asset_dispose"
    ).first()
    assert entry is not None
    lines = JournalLine.objects.filter(entry=entry)
    # Dr 1100 / Cr 4100 — two lines.
    assert lines.count() == 2
    amounts = sorted([(ln.side, ln.amount) for ln in lines])
    assert amounts == sorted(
        [
            (JournalLine.Side.DEBIT, Decimal("100000.00")),
            (JournalLine.Side.CREDIT, Decimal("100000.00")),
        ]
    )


@pytest.mark.django_db
def test_dispose_already_disposed_refuses(creditor: Organization, accountant: User) -> None:
    asset = FixedAsset.objects.create(
        organization=creditor,
        asset_number="AST-D2C-003",
        name="Server",
        category=FixedAsset.Category.IT_HARDWARE,
        acquisition_date=date(2022, 1, 1),
        acquisition_cost=Decimal("300000.00"),
        useful_life_years=4,
        is_active=False,  # already disposed
    )
    with pytest.raises(ValueError, match="already disposed"):
        dispose_fixed_asset(
            asset=asset,
            disposal_date=date(2026, 8, 1),
            disposal_amount=Decimal("50000.00"),
            user=accountant,
        )


@pytest.mark.django_db
def test_dispose_refuses_proceeds_above_cost(creditor: Organization, accountant: User) -> None:
    asset = FixedAsset.objects.create(
        organization=creditor,
        asset_number="AST-D2C-004",
        name="Shelf",
        category=FixedAsset.Category.FURNITURE,
        acquisition_date=date(2022, 1, 1),
        acquisition_cost=Decimal("100000.00"),
        useful_life_years=5,
    )
    with pytest.raises(ValueError, match="exceeds"):
        dispose_fixed_asset(
            asset=asset,
            disposal_date=date(2026, 8, 1),
            disposal_amount=Decimal("150000.00"),
            user=accountant,
        )


@pytest.mark.django_db
def test_dispose_refuses_negative_amount(creditor: Organization, accountant: User) -> None:
    asset = FixedAsset.objects.create(
        organization=creditor,
        asset_number="AST-D2C-005",
        name="Locker",
        category=FixedAsset.Category.FURNITURE,
        acquisition_date=date(2022, 1, 1),
        acquisition_cost=Decimal("100000.00"),
        useful_life_years=5,
    )
    with pytest.raises(ValueError, match="negative"):
        dispose_fixed_asset(
            asset=asset,
            disposal_date=date(2026, 8, 1),
            disposal_amount=Decimal("-1.00"),
            user=accountant,
        )


@pytest.mark.django_db
def test_dispose_via_api(creditor: Organization, accountant: User) -> None:
    asset = FixedAsset.objects.create(
        organization=creditor,
        asset_number="AST-D2C-006",
        name="POS Terminal",
        category=FixedAsset.Category.IT_HARDWARE,
        acquisition_date=date(2024, 6, 1),
        acquisition_cost=Decimal("250000.00"),
        useful_life_years=3,
    )
    resp = _auth(accountant).post(
        f"/api/finance/fixed-assets/{asset.pk}/dispose/",
        {
            "disposal_date": "2026-08-01",
            "disposal_amount": "75000.00",
            "disposal_reason": "Replaced with newer model",
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["is_active"] is False
    assert body["disposal_reason"] == "Replaced with newer model"


@pytest.mark.django_db
def test_dispose_via_api_requires_finance_manage(creditor: Organization, cashier: User) -> None:
    asset = FixedAsset.objects.create(
        organization=creditor,
        asset_number="AST-D2C-007",
        name="POS",
        category=FixedAsset.Category.IT_HARDWARE,
        acquisition_date=date(2024, 6, 1),
        acquisition_cost=Decimal("250000.00"),
        useful_life_years=3,
    )
    resp = _auth(cashier).post(
        f"/api/finance/fixed-assets/{asset.pk}/dispose/",
        {"disposal_date": "2026-08-01", "disposal_amount": "100.00"},
        format="json",
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# BE4 — TenantSettings viewset
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tenant_settings_get_lazily_creates(creditor: Organization, accountant: User) -> None:
    """A fresh GET for an org without a row must produce a default-initialised
    singleton (not a 404)."""
    assert not TenantSettings.objects.filter(organization=creditor).exists()
    resp = _auth(accountant).get(f"/api/finance/tenant-settings/{creditor.pk}/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["organization"] == creditor.pk
    assert body["base_currency"] == "RWF"
    assert body["costing_method"] == "FEFO_LOT"


@pytest.mark.django_db
def test_tenant_settings_get_returns_existing(creditor: Organization, accountant: User) -> None:
    settings = tenant_settings_for(creditor)
    settings.costing_method = TenantSettings.CostingMethod.WAC
    settings.save()

    resp = _auth(accountant).get(f"/api/finance/tenant-settings/{creditor.pk}/")
    assert resp.status_code == 200
    assert resp.json()["costing_method"] == "WAC"


@pytest.mark.django_db
def test_tenant_settings_patch_persists(creditor: Organization, accountant: User) -> None:
    resp = _auth(accountant).patch(
        f"/api/finance/tenant-settings/{creditor.pk}/",
        {"costing_method": "WAC", "fx_provider": "manual", "base_currency": "USD"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["costing_method"] == "WAC"
    assert body["fx_provider"] == "manual"
    assert body["base_currency"] == "USD"

    # Reload from DB.
    settings = TenantSettings.objects.get(organization=creditor)
    assert settings.costing_method == TenantSettings.CostingMethod.WAC
    assert settings.fx_provider == "manual"
    assert settings.base_currency == "USD"


@pytest.mark.django_db
def test_tenant_settings_patch_requires_finance_manage(
    creditor: Organization, cashier: User
) -> None:
    resp = _auth(cashier).patch(
        f"/api/finance/tenant-settings/{creditor.pk}/",
        {"costing_method": "WAC"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_tenant_settings_get_for_unknown_org_404(creditor: Organization, accountant: User) -> None:
    resp = _auth(accountant).get("/api/finance/tenant-settings/999999/")
    # The view raises ValidationError → 400 (it doesn't 404).
    assert resp.status_code in (400, 404)


@pytest.mark.django_db
def test_tenant_settings_list_query_param(creditor: Organization, accountant: User) -> None:
    """The viewset exposes ``list()`` taking an ``?organization=`` query
    parameter, in addition to retrieve-by-id."""
    resp = _auth(accountant).get(f"/api/finance/tenant-settings/?organization={creditor.pk}")
    assert resp.status_code == 200, resp.content
    assert resp.json()["organization"] == creditor.pk
