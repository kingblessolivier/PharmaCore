"""A depot is not a shop, and a shop is not a depot.

The counter was gated on the `sale.create` permission alone and never on what
kind of organization was trading, so a depot with one permissive role got a till
and could ring up a walk-in customer.

That is not a cosmetic slip. A depot sells cases to pharmacies on account and
books wholesale revenue and trade receivables; a shop sells singles to the
public for cash and books retail revenue, VAT at the till, and a drawer somebody
has to reconcile at close. Letting one post the other's transactions puts both
sets of books wrong at once — which is why this is refused at the door rather
than hidden in the menu.
"""

from __future__ import annotations

import pytest
from apps.iam.models import Organization, User
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def org(kind: str, name: str) -> Organization:
    return Organization.objects.create(name=name, type=kind)


def till_for(organization: Organization) -> APIClient:
    user = User.objects.create_superuser(
        username=f"till-{organization.pk}", password="pw", organization=organization
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def search(client: APIClient, organization: Organization):
    return client.get(f"/api/retail/counter/search/?organization={organization.pk}&q=para")


def test_a_retail_pharmacy_may_trade_over_the_counter():
    shop = org("RETAIL", "Remera Pharmacy")
    assert search(till_for(shop), shop).status_code == 200


def test_a_depot_may_not():
    """Bulk stock leaves a depot on a B2B order, not over a counter."""
    depot = org("DEPOT", "Kigali Central Depot")
    resp = search(till_for(depot), depot)
    assert resp.status_code == 403
    assert "not a retail pharmacy" in str(resp.content)


def test_a_head_office_may_not_either():
    """It holds no stock to sell."""
    hq = org("HQ", "Group HQ")
    assert search(till_for(hq), hq).status_code == 403


def test_the_refusal_says_what_to_do_instead():
    """A refusal that only says 'no' sends somebody looking for a workaround."""
    depot = org("DEPOT", "Kigali Central Depot")
    body = str(search(till_for(depot), depot).content)
    assert "B2B order" in body


def test_a_retail_user_cannot_trade_through_a_depot_by_naming_it():
    """The guard is on the organization being traded for, not on the caller."""
    depot = org("DEPOT", "Kigali Central Depot")
    shop = org("RETAIL", "Remera Pharmacy")
    resp = search(till_for(shop), depot)
    assert resp.status_code == 403
