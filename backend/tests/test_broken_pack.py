"""A broken pack runs on its own, shorter clock.

Regulatory guidance holds a split tablet to a 90-day stability window at
25C/60% RH — so a loose remainder can sit inside the batch's printed expiry and
outside its own. FEFO sorting on the printed date would hand exactly that one
over, which is the failure these pin.

See docs/development/medicine-chain-import-to-patient.md 7.3.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product, ProductUnit
from apps.iam.models import Organization
from apps.inventory.models import InventoryBatch, PharmacyProduct
from apps.retail.lines import build_line
from apps.retail.models import Sale
from apps.retail.services import complete_sale
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="Remera Pharmacy", type="RETAIL")


@pytest.fixture
def splittable():
    """A tablet a pharmacist has approved for halving."""
    product = Product.objects.create(
        generic_name="Warfarin", strength="5mg", dosage_form="TABLET", divisibility=2
    )
    ProductUnit.objects.create(
        product=product,
        code="TABLET",
        factor_to_base=1,
        is_base=True,
        is_sale_default=True,
    )
    return product


def batch(org, product, *, days, number="B1", qty=100, opened=None):
    return InventoryBatch.objects.create(
        organization=org,
        product=product,
        batch_number=number,
        expiry_date=timezone.localdate() + timedelta(days=days),
        quantity_available=Decimal(qty),
        wholesale_cost=Decimal("10"),
        status=InventoryBatch.Status.ACTIVE,
        opened_at=opened,
    )


def sell(org, product, quantity):
    PharmacyProduct.objects.update_or_create(
        organization=org,
        product=product,
        defaults={"retail_price": Decimal("100"), "is_active": True},
    )
    sale = Sale.objects.create(
        organization=org, status=Sale.Status.OPEN, sale_number=f"S-{Sale.objects.count() + 1}"
    )
    build_line(
        sale=sale,
        product=product,
        quantity=quantity,
        base_price=Decimal("100"),
        tax_rate=Decimal("0"),
    )
    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": "10000"}], user=None)
    return sale


# ---------------------------------------------------------------------------
# The clock
# ---------------------------------------------------------------------------


def test_a_sealed_pack_expires_on_its_printed_date(org, splittable):
    b = batch(org, splittable, days=400)
    assert b.is_broken_pack is False
    assert b.effective_expiry == b.expiry_date


def test_an_opened_pack_expires_ninety_days_after_it_was_broken(org, splittable):
    """Even though the printed date is more than a year away."""
    opened = timezone.localdate() - timedelta(days=10)
    b = batch(org, splittable, days=400, opened=opened)

    assert b.is_broken_pack is True
    assert b.effective_expiry == opened + timedelta(days=90)
    assert b.effective_expiry < b.expiry_date


def test_the_printed_date_still_wins_when_it_comes_first(org, splittable):
    """Opening a pack cannot extend its life."""
    opened = timezone.localdate()
    b = batch(org, splittable, days=30, opened=opened)
    assert b.effective_expiry == b.expiry_date


# ---------------------------------------------------------------------------
# What the counter does with it
# ---------------------------------------------------------------------------


def test_selling_a_half_breaks_the_pack(org, splittable):
    b = batch(org, splittable, days=400)
    sell(org, splittable, "0.5")

    b.refresh_from_db()
    assert b.opened_at == timezone.localdate()
    assert b.quantity_available == Decimal("99.500")


def test_selling_whole_tablets_leaves_the_pack_sealed(org, splittable):
    """Taking whole units from a box does not put it on the split clock."""
    b = batch(org, splittable, days=400)
    sell(org, splittable, 5)

    b.refresh_from_db()
    assert b.opened_at is None
    assert b.is_broken_pack is False


def test_stock_past_its_own_clock_is_never_dispensed(org, splittable):
    """The failure this exists to prevent: inside the printed expiry, outside
    its own, and handed over anyway."""
    from apps.retail.services import InsufficientStock

    batch(org, splittable, days=400, opened=timezone.localdate() - timedelta(days=120))

    with pytest.raises(InsufficientStock):
        sell(org, splittable, 1)


def test_an_already_open_pack_is_finished_before_another_is_broken(org, splittable):
    """What a real counter does, and the opposite of FEFO on the printed date.

    The sealed pack expires sooner, so pure FEFO would open it and leave two
    broken packs on the shelf.
    """
    sealed = batch(org, splittable, days=100, number="SEALED")
    opened = batch(
        org, splittable, days=400, number="OPEN", opened=timezone.localdate(), qty=Decimal("10")
    )

    sell(org, splittable, 4)

    opened.refresh_from_db()
    sealed.refresh_from_db()
    assert opened.quantity_available == Decimal("6.000"), "the open pack is drawn down first"
    assert sealed.quantity_available == Decimal("100.000"), "the sealed pack is left alone"
