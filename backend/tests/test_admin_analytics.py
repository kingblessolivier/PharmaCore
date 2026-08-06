"""Admin oversight remainder: audit CSV export, per-user & per-branch performance."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from apps.catalog.models import Product
from apps.iam.models import AuditLog, Organization, Role, User
from apps.inventory.models import InventoryBatch, PharmacyProduct
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="City Pharmacy", type=Organization.OrgType.RETAIL)


@pytest.fixture
def sys_admin(db: None) -> User:
    u = User.objects.create_user(username="root", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.fixture
def cashier(retail: Organization) -> User:
    u = User.objects.create_user(username="till", password="x", organization=retail)
    u.roles.add(Role.objects.get(code="CASHIER"))
    return u


# --- audit CSV export ------------------------------------------------------


@pytest.mark.django_db
def test_audit_export_csv(sys_admin: User, cashier: User) -> None:
    AuditLog.objects.create(user=cashier, action="LOGIN", entity_type="auth")
    resp = _auth(sys_admin).get("/api/audit-logs/export/")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert "attachment" in resp["Content-Disposition"]
    body = resp.content.decode()
    assert "when,user,action" in body.replace(" ", "")
    assert "LOGIN" in body and "till" in body


@pytest.mark.django_db
def test_audit_export_respects_filters(sys_admin: User, cashier: User) -> None:
    AuditLog.objects.create(user=cashier, action="LOGIN", entity_type="auth")
    AuditLog.objects.create(user=sys_admin, action="CREATE", entity_type="user")
    body = _auth(sys_admin).get(f"/api/audit-logs/export/?user={cashier.pk}").content.decode()
    assert "LOGIN" in body and "CREATE" not in body


@pytest.mark.django_db
def test_non_admin_cannot_export(cashier: User) -> None:
    assert _auth(cashier).get("/api/audit-logs/export/").status_code == 403


# --- per-user performance --------------------------------------------------


@pytest.mark.django_db
def test_user_performance(sys_admin: User, cashier: User, retail: Organization) -> None:
    product = Product.objects.create(generic_name="Paracetamol", strength="500mg", tax_class="B")
    PharmacyProduct.objects.create(organization=retail, product=product, retail_price="1000.00")
    InventoryBatch.objects.create(
        organization=retail,
        product=product,
        batch_number="B1",
        expiry_date=date.today() + timedelta(days=200),
        quantity_available=50,
    )
    # ring up a sale as the cashier
    _auth(cashier).post(
        "/api/retail/sales/",
        {
            "organization": retail.pk,
            "items": [{"product": product.pk, "quantity": 2}],
            "payments": [{"method": "CASH", "amount": "2000"}],
        },
        format="json",
    )
    AuditLog.objects.create(user=cashier, action="LOGIN", entity_type="auth")

    resp = _auth(sys_admin).get(f"/api/users/{cashier.pk}/performance/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["sales_count"] == 1
    assert body["logins"] == 1
    assert body["voids"] == 0


@pytest.mark.django_db
def test_org_performance(sys_admin: User, cashier: User, retail: Organization) -> None:
    resp = _auth(sys_admin).get(f"/api/organizations/{retail.pk}/performance/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["users"] >= 1  # the cashier
    assert body["sales_count"] == 0
