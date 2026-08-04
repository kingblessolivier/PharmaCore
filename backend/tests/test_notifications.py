"""Operational notifications — order lifecycle events + the alerts command."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from apps.catalog.models import Product
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch, PharmacyProduct
from apps.workspace.models import Notification
from django.core.management import call_command
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_submit_notifies_supplying_branch_admins() -> None:
    depot = Organization.objects.create(name="Depot", type=Organization.OrgType.DEPOT)
    retail = Organization.objects.create(name="Shop", type=Organization.OrgType.RETAIL)
    product = Product.objects.create(generic_name="Amoxicillin", strength="500mg")
    PharmacyProduct.objects.create(organization=depot, product=product, wholesale_price="10")

    depot_admin = User.objects.create_user(username="da", password="x", organization=depot)
    depot_admin.roles.add(Role.objects.get(code="ORG_ADMIN"))
    buyer = User.objects.create_user(username="b", password="x", organization=retail)
    buyer.roles.add(Role.objects.get(code="ORG_ADMIN"))

    client = _auth(buyer)
    oid = client.post(
        "/api/distribution/orders/",
        {
            "depot": depot.pk,
            "retail": retail.pk,
            "items": [{"product": product.pk, "quantity_ordered": 3}],
        },
        format="json",
    ).json()["id"]
    client.post(f"/api/distribution/orders/{oid}/submit/")

    n = Notification.objects.filter(recipient=depot_admin, link_entity_id=str(oid))
    assert n.exists()
    assert "New order" in n.first().title


@pytest.mark.django_db
def test_alerts_command_flags_low_stock_and_expiry() -> None:
    org = Organization.objects.create(name="Shop", type=Organization.OrgType.RETAIL)
    product = Product.objects.create(generic_name="Amoxicillin", strength="500mg")
    admin = User.objects.create_user(username="a", password="x", organization=org)
    admin.roles.add(Role.objects.get(code="ORG_ADMIN"))

    # Below-minimum listing (min 10, only 2 on hand) + an expired batch.
    PharmacyProduct.objects.create(
        organization=org, product=product, retail_price="100", min_stock_level=10
    )
    InventoryBatch.objects.create(
        organization=org, product=product, batch_number="OK",
        expiry_date=date.today() + timedelta(days=200), quantity_available=2,
    )
    InventoryBatch.objects.create(
        organization=org, product=product, batch_number="OLD",
        expiry_date=date.today() - timedelta(days=1), quantity_available=5,
    )

    call_command("notify_alerts")
    titles = list(Notification.objects.filter(recipient=admin).values_list("title", flat=True))
    assert any("below minimum" in t for t in titles)
    assert any("expired" in t for t in titles)

    # Idempotent: running again doesn't duplicate the unread alerts.
    before = Notification.objects.filter(recipient=admin).count()
    call_command("notify_alerts")
    assert Notification.objects.filter(recipient=admin).count() == before


@pytest.mark.django_db
def test_run_scheduler_dry_run_registers_job(capsys) -> None:
    # --dry-run builds the schedule and exits without blocking.
    call_command("run_scheduler", "--dry-run", "--hour", "2", "--minute", "30")
    out = capsys.readouterr().out
    assert "notify_alerts" in out and "02:30" in out
