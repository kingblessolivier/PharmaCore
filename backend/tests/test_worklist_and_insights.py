"""The home screen: what needs doing, and how the business is going.

Pins audit D10 (a dashboard with no trend, no branch split and no margin) and the
interactivity gap — the reporting line was recorded and never shown to anyone.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.approvals import services
from apps.catalog.models import Product
from apps.core import insights
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch
from apps.retail.models import Sale, SaleBatchAllocation, SaleItem
from apps.workspace import worklist
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def group():
    hq = Organization.objects.create(name="Umoja HQ", type="HQ")
    a = Organization.objects.create(name="Remera Pharmacy", type="RETAIL", parent=hq)
    b = Organization.objects.create(name="Nyamirambo Pharmacy", type="RETAIL", parent=hq)
    return hq, a, b


def person(org, code, reports_to=None):
    u = User.objects.create_user(
        username=f"u{User.objects.count()}", password="pw", organization=org
    )
    u.roles.add(Role.objects.get(code=code))
    if reports_to:
        u.reports_to = reports_to
        u.save()
    return u


def sell(org, *, revenue, cost, n=1):
    product = Product.objects.create(generic_name=f"D{Product.objects.count()}", strength="1")
    batch = InventoryBatch.objects.create(
        organization=org,
        product=product,
        batch_number=f"B{InventoryBatch.objects.count()}",
        expiry_date=timezone.localdate() + timedelta(days=300),
        quantity_available=100,
        wholesale_cost=Decimal(cost),
    )
    for _ in range(n):
        sale = Sale.objects.create(
            organization=org,
            status=Sale.Status.COMPLETED,
            completed_at=timezone.now(),
            sale_number=f"S{Sale.objects.count()}",
        )
        item = SaleItem.objects.create(
            sale=sale, product=product, quantity=1, unit_price=Decimal(revenue)
        )
        SaleBatchAllocation.objects.create(sale_item=item, batch=batch, quantity=1)


def test_the_dashboard_splits_revenue_by_branch(group):
    """A group owner with four pharmacies was given one summed number."""
    _, a, b = group
    sell(a, revenue="1000", cost="600", n=2)
    sell(b, revenue="500", cost="400")

    result = insights.performance(org_ids=[a.pk, b.pk])
    assert [row["name"] for row in result["by_branch"]] == [
        "Remera Pharmacy",
        "Nyamirambo Pharmacy",
    ]
    assert result["by_branch"][0]["revenue"] == 2000.0
    assert result["today"]["revenue"] == 2500.0


def test_margin_is_taken_from_the_batches_actually_sold(group):
    _, a, _ = group
    sell(a, revenue="1000", cost="600")
    result = insights.performance(org_ids=[a.pk])
    assert result["today"]["margin"] == 400.0
    assert result["today"]["margin_pct"] == 40.0


def test_there_is_something_to_compare_today_against(group):
    _, a, _ = group
    result = insights.performance(org_ids=[a.pk])
    assert len(result["trend"]) == insights.TREND_DAYS
    assert "yesterday" in result["compared"]


def test_expiry_exposure_is_banded_because_the_action_differs(group):
    _, a, _ = group
    product = Product.objects.create(generic_name="Old", strength="1")
    for days, qty in ((-5, 10), (15, 20), (200, 99)):
        InventoryBatch.objects.create(
            organization=a,
            product=product,
            batch_number=f"E{days}",
            expiry_date=timezone.localdate() + timedelta(days=days),
            quantity_available=qty,
            wholesale_cost=Decimal("100"),
        )
    bands = {b["band"]: b for b in insights.expiry_exposure(org_ids=[a.pk])["bands"]}
    assert bands["expired"]["units"] == 10
    assert bands["within_30"]["units"] == 20
    assert bands["within_90"]["units"] == 0, "a batch 200 days out is not 'at risk'"


# --------------------------------------------------------------------------- #
# The work queue — the reporting line made visible
# --------------------------------------------------------------------------- #


def test_a_manager_sees_what_their_team_raised(group):
    _, a, _ = group
    manager = person(a, "BRANCH_MANAGER")
    clerk = person(a, "WAREHOUSE_CLERK", reports_to=manager)

    services.request_approval(
        resource_type="inventory.disposal",
        resource_id="1",
        organization=a,
        requested_by=clerk,
        payload={"value": "40000"},
        reason="Water damage",
    )
    work = worklist.for_user(manager)
    assert work["my_team"]["size"] == 1
    assert len(work["my_team"]["open_requests"]) == 1
    assert work["my_team"]["open_requests"][0]["requested_by"] == clerk.username


def test_what_you_cannot_decide_is_separated_and_explains_itself(group):
    """These are the ones that rot in a shared queue."""
    _, a, _ = group
    ceo = person(a, "ORG_ADMIN")
    hr = person(a, "HR_MANAGER", reports_to=ceo)
    other_hr = person(a, "HR_MANAGER", reports_to=ceo)

    services.request_approval(
        resource_type="hr.payroll_run",
        resource_id="1",
        organization=a,
        requested_by=hr,
        payload={"net_pay": "48000000"},
        reason="August payroll",
    )
    work = worklist.for_user(other_hr)
    assert work["waiting_on_me"] == []
    assert len(work["needs_escalation"]) == 1
    row = work["needs_escalation"][0]
    assert "above your approval limit" in row["why"]
    assert row["escalate_to"] == [ceo.username]


def test_your_own_request_says_who_it_is_with(group):
    _, a, _ = group
    ceo = person(a, "ORG_ADMIN")
    hr = person(a, "HR_MANAGER", reports_to=ceo)
    services.request_approval(
        resource_type="hr.payroll_run",
        resource_id="1",
        organization=a,
        requested_by=hr,
        payload={"net_pay": "48000000"},
    )
    work = worklist.for_user(hr)
    assert len(work["raised_by_me"]) == 1
    assert work["raised_by_me"][0]["with"] == [ceo.username]
    assert work["waiting_on_me"] == [], "you can never decide your own request"


def test_next_steps_only_names_work_you_may_actually_do(group):
    _, a, _ = group
    product = Product.objects.create(generic_name="Expired", strength="1")
    InventoryBatch.objects.create(
        organization=a,
        product=product,
        batch_number="X1",
        expiry_date=timezone.localdate() - timedelta(days=2),
        quantity_available=5,
        wholesale_cost=Decimal("100"),
    )
    clerk = person(a, "WAREHOUSE_CLERK")
    cashier = person(a, "CASHIER")
    assert any("expired" in s["label"] for s in worklist.next_steps(clerk))
    assert worklist.next_steps(cashier) == [], "a cashier has no inventory.view"


def test_the_endpoints_answer_over_http(group):
    _, a, _ = group
    manager = person(a, "BRANCH_MANAGER")
    client = APIClient()
    client.force_authenticate(user=manager)
    for url in ("/api/dashboard/", "/api/workspace/my-work/"):
        assert client.get(url).status_code == 200, url
