"""Purchase orders: create (scoped) → submit → cancel, audited."""

from __future__ import annotations

import pytest
from apps.catalog.models import Product
from apps.distribution.models import StockOrder
from apps.iam.models import AuditLog, Organization, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def depot(db: None) -> Organization:
    return Organization.objects.create(name="Depot", type=Organization.OrgType.DEPOT)


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="Retail", type=Organization.OrgType.RETAIL)


@pytest.fixture
def product(db: None) -> Product:
    return Product.objects.create(generic_name="Paracetamol", strength="500mg")


@pytest.fixture
def retail_user(retail: Organization) -> User:
    u = User.objects.create_user(username="buyer", password="x", organization=retail)
    u.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return u


def _payload(depot: Organization, retail: Organization, product: Product) -> dict:
    return {
        "depot": depot.pk,
        "retail": retail.pk,
        "items": [{"product": product.pk, "quantity_ordered": 100, "price_per_unit": "12.00"}],
    }


@pytest.mark.django_db
def test_create_order_generates_number_and_audits(
    retail_user: User, depot, retail, product
) -> None:
    resp = _auth(retail_user).post(
        "/api/distribution/orders/", _payload(depot, retail, product), format="json"
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["order_number"].startswith("PO-")
    assert body["status"] == "DRAFT"
    assert body["total_amount"] == 1200.0
    assert AuditLog.objects.filter(action="CREATE", entity_type="stock_order").exists()


@pytest.mark.django_db
def test_cannot_order_for_other_org(depot, retail, product) -> None:
    outsider_org = Organization.objects.create(name="Other", type=Organization.OrgType.RETAIL)
    outsider = User.objects.create_user(username="o", password="x", organization=outsider_org)
    resp = _auth(outsider).post(
        "/api/distribution/orders/", _payload(depot, retail, product), format="json"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_submit_and_cancel_flow(retail_user: User, depot, retail, product) -> None:
    client = _auth(retail_user)
    order_id = client.post(
        "/api/distribution/orders/", _payload(depot, retail, product), format="json"
    ).json()["id"]
    sub = client.post(f"/api/distribution/orders/{order_id}/submit/")
    assert sub.status_code == 200 and sub.json()["status"] == "PENDING"
    can = client.post(f"/api/distribution/orders/{order_id}/cancel/")
    assert can.status_code == 200 and can.json()["status"] == "CANCELLED"
    StockOrder.objects.get(pk=order_id)  # still exists (not deleted)


@pytest.mark.django_db
def test_depot_sees_incoming_order(depot, retail, product, retail_user) -> None:
    _auth(retail_user).post(
        "/api/distribution/orders/", _payload(depot, retail, product), format="json"
    )
    depot_user = User.objects.create_user(username="depotmgr", password="x", organization=depot)
    depot_user.roles.add(Role.objects.get(code="ORG_ADMIN"))
    resp = _auth(depot_user).get("/api/distribution/orders/")
    assert resp.json()["count"] == 1  # depot sees the incoming order
