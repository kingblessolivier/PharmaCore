"""Module homes as work queues (D14), and only work you may actually do.

The audit measured one ordinary job crossing seven screens in five nav groups
with no link from any step to the next. The dashboard answers "what needs doing"
for the business; this answers it per app.

The first test is the important one: it runs **every** module's query. A queue
built on a guessed field name or a status that does not exist fails here rather
than on someone's screen.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch
from apps.workspace import modulework
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="Remera Pharmacy", type="RETAIL")


def person(org, *codes):
    user = User.objects.create_user(
        username=f"u{User.objects.count()}", password="pw", organization=org
    )
    for code in codes:
        user.roles.add(Role.objects.get(code=code))
    return user


def test_every_module_query_actually_runs(org) -> None:
    """The point of this test: a wrong field name fails here, not on a screen.

    A superuser holds every permission, so every builder executes.
    """
    root = User.objects.create_superuser(username="root", password="pw", email="r@x.rw")
    root.organization = org
    root.save()

    queues = modulework.queues_for(root)
    assert set(queues) == set(modulework._MODULES), "a module was silently skipped"
    for name, rows in queues.items():
        for row in rows:
            assert row["count"] > 0, f"{name}: an empty queue line was returned"
            assert row["to"].startswith("/"), f"{name}: {row['label']} has no link"


def test_a_queue_only_names_work_you_may_do(org) -> None:
    """A cashier is not told about quarantine releases."""
    cashier = person(org, "CASHIER")
    assert set(modulework.queues_for(cashier)) == {"retail"}

    clerk = person(org, "WAREHOUSE_CLERK")
    assert "inventory" in modulework.queues_for(clerk)
    assert "finance" not in modulework.queues_for(clerk)
    assert "people" not in modulework.queues_for(clerk)


def test_a_real_count_appears_with_a_link(org) -> None:
    product = Product.objects.create(generic_name="Amoxicillin", strength="500mg")
    for n in range(3):
        InventoryBatch.objects.create(
            organization=org,
            product=product,
            batch_number=f"E{n}",
            expiry_date=timezone.localdate() - timedelta(days=2),
            quantity_available=10,
            wholesale_cost=Decimal("100"),
        )
    rows = modulework.queues_for(person(org, "WAREHOUSE_CLERK"), "inventory")["inventory"]
    expired = next(r for r in rows if "expired" in r["label"])
    assert expired["count"] == 3
    assert expired["to"] == "/inventory/disposal"
    assert expired["tone"] == "danger"


def test_nothing_to_do_returns_an_empty_queue_not_a_zero(org) -> None:
    """A line reading "0 things to do" is noise; the absence is the message."""
    rows = modulework.queues_for(person(org, "WAREHOUSE_CLERK"), "inventory")["inventory"]
    assert rows == []


def test_the_endpoint_answers_and_can_be_narrowed(org) -> None:
    client = APIClient()
    client.force_authenticate(user=person(org, "WAREHOUSE_CLERK", "PHARMACIST"))

    all_modules = client.get("/api/workspace/module-work/")
    assert all_modules.status_code == 200
    assert "inventory" in all_modules.json()["queues"]

    one = client.get("/api/workspace/module-work/?module=inventory")
    assert one.status_code == 200
    assert list(one.json()["queues"]) == ["inventory"]


def test_an_unknown_module_is_ignored_rather_than_erroring(org) -> None:
    client = APIClient()
    client.force_authenticate(user=person(org, "PHARMACIST"))
    resp = client.get("/api/workspace/module-work/?module=nonsense")
    assert resp.status_code == 200
    assert resp.json()["queues"] == {}
