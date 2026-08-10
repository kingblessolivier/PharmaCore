"""Who may delete what.

Thirty writable resources answered ``DELETE`` with a bare 405. Some of those
refusals are right and permanent — a posted journal entry, a fiscalised sale, a
closed period are *records*, and the correction for a record is a reversing
entry, not a disappearance. But "Method \\"DELETE\\" not allowed" says none of
that. It reads as a route somebody forgot, and it left the person setting the
system up unable to clear a mistake and unable to tell which kind of refusal
they had hit.

So there are two outcomes to get right, and both are tested here:

* a **409 with a sentence** for anything that is never deleted, naming what to
  do instead;
* a **working delete for an administrator** — SYS_ADMIN anywhere, ORG_ADMIN in
  their own organisation — that stops at records which are referenced, and
  writes an audit row, because deletion is the one action that otherwise leaves
  no trace of itself.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.core.deletion import NEVER_DELETE, _organization_of, never_deletable_reason
from apps.distribution.models import StockOrder
from apps.finance.models import Account, JournalEntry, JournalLine
from apps.finance.services import post_journal
from apps.iam.models import AuditLog, Organization, Role, User
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organization:
    return Organization.objects.create(name="Kigali Central Pharmacy", type="RETAIL", tin="1")


@pytest.fixture
def depot() -> Organization:
    return Organization.objects.create(name="Kigali Central Depot", type="DEPOT", tin="2")


def _user(username: str, org: Organization, role_code: str | None) -> User:
    user = User.objects.create_user(username=username, password="x", organization=org)
    if role_code:
        role, _ = Role.objects.get_or_create(code=role_code, defaults={"name": role_code})
        user.roles.add(role)
    return user


@pytest.fixture
def org_admin(org: Organization) -> User:
    return _user("org-admin", org, "ORG_ADMIN")


@pytest.fixture
def cashier(org: Organization) -> User:
    return _user("till", org, "CASHIER")


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


# --------------------------------------------------------------------------- #


class TestThingsThatAreNeverDeleted:
    """The refusal is the feature: it teaches the rule."""

    def test_a_posted_journal_entry_says_to_reverse_it(
        self, org: Organization, org_admin: User
    ) -> None:
        cash = Account.objects.create(
            organization=org, code="1100", name="Cash on Hand", account_type="ASSET"
        )
        payable = Account.objects.create(
            organization=org, code="2100", name="Payables", account_type="LIABILITY"
        )
        entry = post_journal(
            organization=org,
            description="Settlement",
            lines=[
                {"account": payable, "side": JournalLine.Side.DEBIT, "amount": Decimal("100")},
                {"account": cash, "side": JournalLine.Side.CREDIT, "amount": Decimal("100")},
            ],
            source_module=JournalEntry.Source.TREASURY,
        )
        response = client_for(org_admin).delete(f"/api/finance/journal-entries/{entry.pk}/")

        assert response.status_code == 409, "a 405 here reads as a missing route"
        assert "reversing entry" in response.data["detail"]
        assert JournalEntry.objects.filter(pk=entry.pk).exists()

    def test_every_standing_refusal_names_a_real_model(self) -> None:
        """A rule about a model that no longer exists protects nothing."""
        from django.apps import apps as django_apps

        for label in NEVER_DELETE:
            django_apps.get_model(label)  # raises LookupError if it has gone

    def test_every_standing_refusal_says_what_to_do_instead(self) -> None:
        """A refusal that only refuses sends the reader off to ask someone.

        "never removable" counts: for an audit entry there genuinely is no
        alternative, and saying so plainly is the useful answer. What is not
        allowed is a refusal that leaves the reader with no next step at all.
        """
        vague = [
            label
            for label, reason in NEVER_DELETE.items()
            if not any(
                word in reason.lower()
                # "revers" covers reverse / reversing / reversal.
                for word in (
                    "instead",
                    "revers",
                    "reopen",
                    "void",
                    "credit note",
                    "close it",
                    "never removable",
                )
            )
        ]
        assert not vague, f"these refusals do not name an alternative: {vague}"


class TestThingsBlockedByTheirOwnState:
    def test_a_delivered_order_cannot_be_deleted(
        self, org: Organization, depot: Organization, org_admin: User
    ) -> None:
        """Stock has moved against it, and a delivery note quotes its number."""
        order = StockOrder.objects.create(
            depot=depot, retail=org, status=StockOrder.Status.DELIVERED
        )
        response = client_for(org_admin).delete(f"/api/distribution/orders/{order.pk}/")

        assert response.status_code == 409
        assert "Cancel the order instead" in response.data["detail"]

    def test_a_draft_order_can_be(
        self, org: Organization, depot: Organization, org_admin: User
    ) -> None:
        order = StockOrder.objects.create(depot=depot, retail=org, status=StockOrder.Status.DRAFT)
        response = client_for(org_admin).delete(f"/api/distribution/orders/{order.pk}/")

        assert response.status_code == 204, response.data
        assert not StockOrder.objects.filter(pk=order.pk).exists()

    def test_an_account_with_postings_says_to_deactivate_it(
        self, org: Organization, org_admin: User
    ) -> None:
        cash = Account.objects.create(
            organization=org, code="1100", name="Cash on Hand", account_type="ASSET"
        )
        payable = Account.objects.create(
            organization=org, code="2100", name="Payables", account_type="LIABILITY"
        )
        post_journal(
            organization=org,
            description="Settlement",
            lines=[
                {"account": payable, "side": JournalLine.Side.DEBIT, "amount": Decimal("100")},
                {"account": cash, "side": JournalLine.Side.CREDIT, "amount": Decimal("100")},
            ],
            source_module=JournalEntry.Source.TREASURY,
        )
        response = client_for(org_admin).delete(f"/api/finance/accounts/{cash.pk}/")

        assert response.status_code == 409
        assert "Deactivate it instead" in response.data["detail"]

    def test_an_unused_account_can_be_deleted(self, org: Organization, org_admin: User) -> None:
        spare = Account.objects.create(
            organization=org, code="9999", name="Opened by mistake", account_type="ASSET"
        )
        assert client_for(org_admin).delete(f"/api/finance/accounts/{spare.pk}/").status_code == 204


class TestOnlyAdministratorsDelete:
    def test_a_cashier_is_told_who_to_ask(
        self, org: Organization, depot: Organization, cashier: User
    ) -> None:
        order = StockOrder.objects.create(depot=depot, retail=org, status=StockOrder.Status.DRAFT)
        response = client_for(cashier).delete(f"/api/distribution/orders/{order.pk}/")

        assert response.status_code == 403
        assert "administrator" in response.data["detail"]
        assert StockOrder.objects.filter(pk=order.pk).exists()

    def test_an_org_admin_cannot_reach_another_organisation(
        self, org: Organization, depot: Organization
    ) -> None:
        """ORG_ADMIN administers an organisation, not the system."""
        elsewhere = Organization.objects.create(name="Huye Pharmacy", type="RETAIL", tin="3")
        outsider = _user("other-admin", elsewhere, "ORG_ADMIN")
        order = StockOrder.objects.create(depot=depot, retail=org, status=StockOrder.Status.DRAFT)

        response = client_for(outsider).delete(f"/api/distribution/orders/{order.pk}/")

        # Either the scoped queryset hides it (404) or the org check refuses
        # it (403). Both are correct; what must never happen is a 204.
        assert response.status_code in (403, 404)
        assert StockOrder.objects.filter(pk=order.pk).exists()

    def test_a_superuser_may_delete_across_organisations(
        self, org: Organization, depot: Organization
    ) -> None:
        root = User.objects.create_superuser(username="root", password="x")
        order = StockOrder.objects.create(depot=depot, retail=org, status=StockOrder.Status.DRAFT)
        assert client_for(root).delete(f"/api/distribution/orders/{order.pk}/").status_code == 204


class TestDeletionLeavesATrace:
    def test_an_audit_row_records_what_went(
        self, org: Organization, depot: Organization, org_admin: User
    ) -> None:
        """The only action with no other evidence of itself.

        Every other change leaves the changed record behind to be inspected.
        A deletion leaves nothing, so the audit row has to carry the identity
        of what was removed, not merely its id.
        """
        order = StockOrder.objects.create(depot=depot, retail=org, status=StockOrder.Status.DRAFT)
        identity = str(order)
        client_for(org_admin).delete(f"/api/distribution/orders/{order.pk}/")

        row = AuditLog.objects.filter(action="DELETE", entity_id=str(order.pk)).first()
        assert row is not None, "a deletion with no audit row is untraceable"
        assert row.user == org_admin
        assert row.organization == org
        assert row.changes is not None
        assert row.changes["deleted"] == identity


class TestFindingTheOwningOrganisation:
    """The org check is only as good as its ability to find the org."""

    def test_it_reads_the_obvious_field(self, org: Organization) -> None:
        account = Account.objects.create(
            organization=org, code="1100", name="Cash", account_type="ASSET"
        )
        assert _organization_of(account) == org

    def test_it_reads_a_differently_named_one(self, org: Organization, depot: Organization) -> None:
        """A distribution order calls its parties `retail` and `depot`."""
        order = StockOrder.objects.create(depot=depot, retail=org)
        assert _organization_of(order) == org

    def test_it_gives_up_rather_than_guessing_wrong(self) -> None:
        """A record with no organisation must fall to a system administrator."""
        role = Role.objects.create(code="TEMP", name="Temp")
        assert _organization_of(role) is None


class TestTheRegistryIsUsable:
    def test_a_known_model_is_refused(self, org: Organization) -> None:
        entry = JournalEntry.objects.create(
            organization=org, entry_date=date(2026, 8, 10), description="x"
        )
        assert never_deletable_reason(entry) is not None

    def test_an_ordinary_model_is_not(self, org: Organization) -> None:
        account = Account.objects.create(
            organization=org, code="1100", name="Cash", account_type="ASSET"
        )
        assert never_deletable_reason(account) is None
