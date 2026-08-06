"""Credit standing gates B2B ordering (roadmap F6).

The credit limit used to be advisory — a buyer on hold could still place an
order and only get stopped at invoicing time, after the depot had already
committed stock. These tests pin the refusal to order creation, with HTTP 409
so the caller can tell "your account is blocked" from "your request is wrong".
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.finance.models import CreditProfile
from apps.finance.services import record_customer_invoice
from apps.iam.models import Organization, Role, User
from apps.inventory.models import PharmacyProduct
from rest_framework.test import APIClient


@pytest.fixture
def depot(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Depot", type="DEPOT")


@pytest.fixture
def retail(db: None) -> Organization:
    return Organization.objects.create(name="Nyabugogo Pharmacy", type="RETAIL")


@pytest.fixture
def product(db: None) -> Product:
    return Product.objects.create(generic_name="Metformin", strength="850mg")


@pytest.fixture
def offering(depot: Organization, product: Product) -> PharmacyProduct:
    return PharmacyProduct.objects.create(
        organization=depot, product=product, wholesale_price=Decimal("1000"), is_active=True
    )


@pytest.fixture
def buyer_admin(retail: Organization) -> User:
    user = User.objects.create_user(username="buyer", password="x", organization=retail)
    user.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return user


def _client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _order_payload(depot: Organization, retail: Organization, product: Product, qty: int) -> dict:
    return {
        "depot": depot.pk,
        "retail": retail.pk,
        "items": [{"product": product.pk, "quantity_ordered": qty}],
    }


@pytest.mark.django_db
def test_order_succeeds_without_a_credit_profile(
    buyer_admin, depot, retail, product, offering
) -> None:
    """No profile means cash-on-delivery, which nothing should block."""
    resp = _client(buyer_admin).post(
        "/api/distribution/orders/", _order_payload(depot, retail, product, 5), format="json"
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_order_rejected_with_409_when_buyer_is_on_hold(
    buyer_admin, depot, retail, product, offering
) -> None:
    CreditProfile.objects.create(
        creditor=depot,
        debtor=retail,
        credit_limit=Decimal("500000"),
        terms_days=30,
        status=CreditProfile.Status.HOLD,
        hold_reason="Cheque bounced",
    )
    resp = _client(buyer_admin).post(
        "/api/distribution/orders/", _order_payload(depot, retail, product, 5), format="json"
    )
    assert resp.status_code == 409
    assert "credit hold" in resp.json()["detail"]
    assert "Cheque bounced" in resp.json()["detail"]


@pytest.mark.django_db
def test_rejected_order_leaves_nothing_behind(
    buyer_admin, depot, retail, product, offering
) -> None:
    from apps.distribution.models import StockOrder

    CreditProfile.objects.create(
        creditor=depot, debtor=retail, status=CreditProfile.Status.HOLD, hold_reason="Overdue"
    )
    _client(buyer_admin).post(
        "/api/distribution/orders/", _order_payload(depot, retail, product, 5), format="json"
    )
    assert StockOrder.objects.count() == 0


@pytest.mark.django_db
def test_order_rejected_when_it_would_breach_the_credit_limit(
    buyer_admin, depot, retail, product, offering
) -> None:
    CreditProfile.objects.create(
        creditor=depot,
        debtor=retail,
        credit_limit=Decimal("10000"),
        terms_days=30,
        status=CreditProfile.Status.ACTIVE,
    )
    # 20 units at 1,000 = 20,000 against a 10,000 limit.
    resp = _client(buyer_admin).post(
        "/api/distribution/orders/", _order_payload(depot, retail, product, 20), format="json"
    )
    assert resp.status_code == 409
    assert "credit limit breached" in resp.json()["detail"]


@pytest.mark.django_db
def test_existing_debt_counts_towards_the_limit(
    buyer_admin, depot, retail, product, offering
) -> None:
    CreditProfile.objects.create(
        creditor=depot,
        debtor=retail,
        credit_limit=Decimal("10000"),
        terms_days=30,
        status=CreditProfile.Status.ACTIVE,
    )
    record_customer_invoice(
        organization=depot,
        customer=retail,
        invoice_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("9000"),
    )
    # 5,000 of new stock on top of 9,000 already owed clears the 10,000 limit.
    resp = _client(buyer_admin).post(
        "/api/distribution/orders/", _order_payload(depot, retail, product, 5), format="json"
    )
    assert resp.status_code == 409


@pytest.mark.django_db
def test_order_rejected_when_an_invoice_is_far_past_due(
    buyer_admin, depot, retail, product, offering
) -> None:
    CreditProfile.objects.create(
        creditor=depot,
        debtor=retail,
        credit_limit=Decimal("1000000"),
        terms_days=30,
        status=CreditProfile.Status.ACTIVE,
    )
    record_customer_invoice(
        organization=depot,
        customer=retail,
        invoice_date=date.today() - timedelta(days=90),
        due_date=date.today() - timedelta(days=60),
        total_amount=Decimal("5000"),
    )
    resp = _client(buyer_admin).post(
        "/api/distribution/orders/", _order_payload(depot, retail, product, 2), format="json"
    )
    assert resp.status_code == 409
    assert "past due" in resp.json()["detail"]


@pytest.mark.django_db
def test_a_slightly_late_invoice_does_not_block(
    buyer_admin, depot, retail, product, offering
) -> None:
    """Ten days late is a reminder, not a stop — trade keeps moving."""
    CreditProfile.objects.create(
        creditor=depot,
        debtor=retail,
        credit_limit=Decimal("1000000"),
        terms_days=30,
        status=CreditProfile.Status.ACTIVE,
    )
    record_customer_invoice(
        organization=depot,
        customer=retail,
        invoice_date=date.today() - timedelta(days=40),
        due_date=date.today() - timedelta(days=10),
        total_amount=Decimal("5000"),
    )
    resp = _client(buyer_admin).post(
        "/api/distribution/orders/", _order_payload(depot, retail, product, 2), format="json"
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_hold_engaged_after_draft_blocks_submission(
    buyer_admin, depot, retail, product, offering
) -> None:
    """A draft raised while the account was clean must not slip through once the
    account goes on hold."""
    created = _client(buyer_admin).post(
        "/api/distribution/orders/", _order_payload(depot, retail, product, 3), format="json"
    )
    assert created.status_code == 201
    order_id = created.json()["id"]

    CreditProfile.objects.create(
        creditor=depot,
        debtor=retail,
        status=CreditProfile.Status.HOLD,
        hold_reason="Auto-hold: 60+ days overdue",
    )
    resp = _client(buyer_admin).post(f"/api/distribution/orders/{order_id}/submit/")
    assert resp.status_code == 409


@pytest.mark.django_db
def test_admin_cannot_bypass_an_engaged_hold(depot, retail, product, offering) -> None:
    """The hold is a business rule, not a permission — being an admin does not
    make the customer's debt go away."""
    admin = User.objects.create_superuser(username="root", password="x")
    CreditProfile.objects.create(
        creditor=depot, debtor=retail, status=CreditProfile.Status.HOLD, hold_reason="Legal"
    )
    resp = _client(admin).post(
        "/api/distribution/orders/", _order_payload(depot, retail, product, 1), format="json"
    )
    assert resp.status_code == 409
