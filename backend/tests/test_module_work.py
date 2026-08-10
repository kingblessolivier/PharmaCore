"""A work-queue tile must open the thing it counted.

"1 orders waiting for your approval" opened the central approval inbox, which
lists ``ApprovalRequest`` records and had eight of them — a different queue, of
a different length, containing none of the orders the tile was counting. "1
deliveries on the road to you" opened the in-transit table, which lists the
batches physically on the lorry, and showed nothing at all.

Both tiles were counting ``StockOrder`` rows and linking somewhere that counts
something else. Nothing was broken in either the count or the screen; they were
simply about different things, and only a reader who clicked would find out.

So: for every tile, ask the destination's own API as the same user and require
the two numbers to agree. A tile is a promise about what is behind it.
"""

from __future__ import annotations

from typing import Any

import pytest
from apps.iam.models import Organization, Role, User
from apps.workspace import modulework
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

#: Where each queue destination gets its rows. A tile links to a *screen*; the
#: screen calls an API. This is the join between them, and the reason the test
#: can compare a tile to a table without running a browser.
#:
#: A destination missing from here fails `test_every_destination_is_mapped`
#: rather than being skipped, so a new queue entry cannot quietly opt out.
DESTINATION_API: dict[str, str] = {
    "/retail": "/api/retail/drawer-sessions/?status=OPEN",
    "/retail/prescriptions": "/api/retail/prescriptions/?status=ACTIVE",
    "/inventory/qc": "/api/inventory/batches/?status=QUARANTINE",
    "/inventory/counts": "/api/inventory/stock-counts/?status=SUBMITTED",
    "/inventory/picking": "/api/inventory/pick-waves/",
    "/distribution/orders?status=PENDING": "/api/distribution/orders/?status=PENDING",
    "/distribution/orders?status=IN_TRANSIT": "/api/distribution/orders/?status=IN_TRANSIT",
    # Mapped although nothing links here any more: the point is that if a tile
    # is ever pointed back at it, the count comparison — not merely the
    # "unmapped destination" check — is what fails.
    "/distribution/in-transit": "/api/distribution/in-transit/",
    "/distribution/demand": "/api/distribution/backorders/?status=OPEN",
    "/distribution/returns": "/api/distribution/returns/",
    "/procurement/requisitions": "/api/procurement/requisitions/?status=SUBMITTED",
    "/procurement/receipts": "/api/procurement/goods-receipts/?status=DRAFT",
    "/procurement/orders": "/api/procurement/purchase-orders/",
    "/approvals": "/api/approvals/requests/",
    "/companies": "/api/organizations/",
    "/quality": "/api/quality/cases/",
    "/servicedesk": "/api/servicedesk/tickets/",
    "/finance": "/api/finance/journal-entries/",
    "/people": "/api/hr/employees/",
}


@pytest.fixture
def admin(db: Any) -> User:
    org = Organization.objects.create(name="Kigali Central Pharmacy", type="RETAIL", tin="1")
    user = User.objects.create_user(username="qadmin", password="x", organization=org)
    role, _ = Role.objects.get_or_create(code="ORG_ADMIN", defaults={"name": "Org admin"})
    user.roles.add(role)
    return user


@pytest.fixture
def work(admin: User) -> User:
    """Put something in the queue.

    Without this the comparison below has nothing to compare and passes on an
    empty database — which is the same green tick as a working system, and the
    exact shape of "the test passed for the wrong reason". The two orders here
    are the two tiles that were broken.
    """
    from apps.distribution.models import StockOrder

    depot = Organization.objects.create(name="Kigali Central Depot", type="DEPOT", tin="2")
    retail = admin.organization
    assert retail is not None
    # `order_number` is unique and defaults to blank, so several unsaved-number
    # orders collide on the empty string rather than getting numbers.
    for number, status in (
        # Waiting on the depot. The user's org is the *retail* side here, so
        # this must not appear for them — scoping is part of the promise too.
        ("PO-90001", StockOrder.Status.PENDING),
        ("PO-90002", StockOrder.Status.IN_TRANSIT),
        ("PO-90003", StockOrder.Status.IN_TRANSIT),
    ):
        StockOrder.objects.create(depot=depot, retail=retail, status=status, order_number=number)
    return admin


def _all_entries(user: User) -> list[tuple[str, dict[str, Any]]]:
    return [
        (module, entry)
        for module, entries in modulework.queues_for(user, None).items()
        for entry in entries
    ]


class TestEveryTileOpensWhatItCounted:
    def test_every_destination_is_mapped(self, work: User) -> None:
        """A new queue entry must declare where its rows come from.

        Without this the test below silently skips whatever it does not know
        about, which is the failure mode that let the two broken tiles ship.
        """
        unknown = {
            entry["to"] for _, entry in _all_entries(work) if entry["to"] not in DESTINATION_API
        }
        assert not unknown, (
            "These work-queue destinations have no API mapped, so nothing checks that "
            f"the tile and the screen agree: {sorted(unknown)}"
        )

    def test_the_counts_agree(self, work: User) -> None:
        client = APIClient()
        client.force_authenticate(work)

        entries = _all_entries(work)
        assert entries, "nothing in the queue — this test would pass without comparing anything"

        disagreements = []
        for module, entry in entries:
            url = DESTINATION_API[entry["to"]]
            response = client.get(f"{url}{'&' if '?' in url else '?'}page_size=1")
            if response.status_code != 200:
                disagreements.append(
                    f"{module}: '{entry['label']}' links to {entry['to']}, whose API "
                    f"{url} returned {response.status_code}"
                )
                continue
            shown = response.data.get("count")
            if shown != entry["count"]:
                disagreements.append(
                    f"{module}: '{entry['label']}' says {entry['count']} but "
                    f"{entry['to']} shows {shown}"
                )
        assert not disagreements, "\n  " + "\n  ".join(disagreements)


class TestATileIsOnlyShownWhenThereIsSomethingToDo:
    def test_an_empty_queue_produces_no_entry(self, work: User) -> None:
        """A row reading "0 things waiting" is noise that trains people to skip
        the whole panel."""
        for _, entry in _all_entries(work):
            assert entry["count"] > 0, f"{entry['label']} was listed with a count of zero"

    def test_entries_carry_what_the_screen_needs(self, work: User) -> None:
        for _, entry in _all_entries(work):
            assert entry["label"] and entry["to"] and entry["tone"]
            assert entry["to"].startswith("/"), "a destination must be an app route"
