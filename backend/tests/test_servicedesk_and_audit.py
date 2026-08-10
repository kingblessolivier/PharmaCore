"""The service desk, and internal audit.

Both are queues with a promise attached, and both fail the same way — by
letting somebody mark work finished without saying what was done. These tests
are mostly about the refusals that stop that.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.iam.models import Organization, User
from apps.quality import services as quality
from apps.quality.models import AuditEngagement, AuditFinding, CaseStatus, Severity
from apps.servicedesk import services as desk
from apps.servicedesk.models import Ticket
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organization:
    return Organization.objects.create(name="Kigali Central Pharmacy", type="RETAIL")


@pytest.fixture
def agent(org: Organization) -> User:
    return User.objects.create_user(
        username="agent",
        password="x",  # noqa: S106 - test fixture
        organization=org,
    )


# --------------------------------------------------------------------------- #
# Service desk
# --------------------------------------------------------------------------- #


class TestTheClock:
    def test_the_promise_is_derived_from_the_priority(self, org: Organization, agent: User) -> None:
        """Derived, not entered — a priority and its deadline cannot disagree."""
        urgent = desk.raise_ticket(
            organization=org,
            subject="Cold chain delivery missing",
            body="Vaccine consignment not delivered.",
            priority=Ticket.Priority.URGENT,
            user=agent,
        )
        normal = desk.raise_ticket(
            organization=org, subject="Invoice query", body="Line 3 looks wrong.", user=agent
        )
        assert urgent.due_at is not None and normal.due_at is not None
        assert urgent.due_at < normal.due_at
        assert round((urgent.due_at - timezone.now()).total_seconds() / 3600) == 4

    def test_raising_the_priority_later_does_not_move_a_missed_target(
        self, org: Organization, agent: User
    ) -> None:
        """The whole point of an SLA figure that means something.

        A desk that rewrites the deadline when somebody escalates reports 100%
        compliance while customers wait.
        """
        ticket = desk.raise_ticket(organization=org, subject="Query", body="…", user=agent)
        original = ticket.due_at
        ticket.priority = Ticket.Priority.URGENT
        ticket.save()
        ticket.refresh_from_db()
        assert ticket.due_at == original

    def test_a_ticket_past_its_promise_is_breached(self, org: Organization, agent: User) -> None:
        ticket = desk.raise_ticket(organization=org, subject="Late", body="…", user=agent)
        ticket.due_at = timezone.now() - timedelta(hours=1)
        ticket.save(update_fields=["due_at"])
        assert ticket.is_breached is True

    def test_a_resolved_ticket_is_never_breached(self, org: Organization, agent: User) -> None:
        # The clock stops when the customer is helped, not when the report runs.
        ticket = desk.raise_ticket(organization=org, subject="Late", body="…", user=agent)
        ticket.due_at = timezone.now() - timedelta(hours=1)
        ticket.save(update_fields=["due_at"])
        desk.resolve_ticket(ticket=ticket, resolution="Redelivered same day.", user=agent)
        assert ticket.is_breached is False


class TestResolving:
    def test_it_cannot_resolve_without_saying_how(self, org: Organization, agent: User) -> None:
        """A queue being cleared is not a customer being helped."""
        ticket = desk.raise_ticket(organization=org, subject="Short delivery", body="…", user=agent)
        with pytest.raises(desk.TicketError, match="how it was resolved"):
            desk.resolve_ticket(ticket=ticket, resolution="   ", user=agent)

    def test_it_cannot_resolve_twice(self, org: Organization, agent: User) -> None:
        ticket = desk.raise_ticket(organization=org, subject="X", body="…", user=agent)
        desk.resolve_ticket(ticket=ticket, resolution="Sorted.", user=agent)
        with pytest.raises(desk.TicketError, match="already"):
            desk.resolve_ticket(ticket=ticket, resolution="Sorted again.", user=agent)


class TestFirstResponse:
    def test_an_internal_note_is_not_a_reply(self, org: Organization, agent: User) -> None:
        """Counting it as one is how a desk reports fast responses nobody got."""
        ticket = desk.raise_ticket(organization=org, subject="X", body="…", user=agent)
        desk.add_note(ticket=ticket, body="Who owns this?", internal=True, user=agent)
        ticket.refresh_from_db()
        assert ticket.first_response_at is None

    def test_a_note_to_the_customer_stamps_it(self, org: Organization, agent: User) -> None:
        ticket = desk.raise_ticket(organization=org, subject="X", body="…", user=agent)
        desk.add_note(ticket=ticket, body="Looking into it now.", user=agent)
        ticket.refresh_from_db()
        assert ticket.first_response_at is not None
        assert ticket.status == Ticket.Status.IN_PROGRESS


class TestEscalation:
    def test_a_ticket_can_become_a_quality_case(self, org: Organization, agent: User) -> None:
        ticket = desk.raise_ticket(
            organization=org,
            subject="Tablets discoloured in the pack",
            body="Customer returned a strip with brown tablets.",
            priority=Ticket.Priority.URGENT,
            user=agent,
        )
        desk.escalate_to_quality(ticket=ticket, user=agent)
        assert ticket.quality_case is not None
        assert ticket.quality_case.case_number.startswith("CMP-")

    def test_the_ticket_keeps_its_own_clock(self, org: Organization, agent: User) -> None:
        """A customer should not wait for a CAPA before somebody talks to them."""
        ticket = desk.raise_ticket(organization=org, subject="X", body="…", user=agent)
        desk.escalate_to_quality(ticket=ticket, user=agent)
        desk.resolve_ticket(ticket=ticket, resolution="Replacement sent.", user=agent)
        assert ticket.status == Ticket.Status.RESOLVED
        assert ticket.quality_case.is_open, "the quality case continues on its own"

    def test_it_will_not_escalate_twice(self, org: Organization, agent: User) -> None:
        ticket = desk.raise_ticket(organization=org, subject="X", body="…", user=agent)
        desk.escalate_to_quality(ticket=ticket, user=agent)
        with pytest.raises(desk.TicketError, match="already has a quality case"):
            desk.escalate_to_quality(ticket=ticket, user=agent)


class TestTheQueue:
    def test_it_counts_what_is_about_to_fail(self, org: Organization, agent: User) -> None:
        late = desk.raise_ticket(organization=org, subject="Late", body="…", user=agent)
        late.due_at = timezone.now() - timedelta(hours=2)
        late.save(update_fields=["due_at"])
        desk.raise_ticket(organization=org, subject="Fine", body="…", user=agent)

        summary = desk.queue_summary(organization=org.pk)
        assert summary["open"] == 2
        assert summary["breached"] == 1
        assert summary["unassigned"] == 2
        assert summary["awaiting_first_response"] == 2


# --------------------------------------------------------------------------- #
# Internal audit
# --------------------------------------------------------------------------- #


def an_audit(org: Organization, user: User, **kw) -> AuditEngagement:
    return quality.plan_audit(
        organization=org,
        title=kw.pop("title", "Kigali branch stock accuracy"),
        scope=kw.pop("scope", "Cycle counts and bin accuracy. Excludes cold chain."),
        user=user,
        **kw,
    )


class TestPlanningAnAudit:
    def test_it_is_referenced(self, org: Organization, agent: User) -> None:
        assert an_audit(org, agent).reference.startswith("AUD-")

    def test_it_needs_a_scope(self, org: Organization, agent: User) -> None:
        # "What is deliberately not examined" is half of what a scope is for.
        with pytest.raises(quality.QualityError, match="scope"):
            quality.plan_audit(organization=org, title="Look at things", scope="  ", user=agent)


class TestFindings:
    def test_a_major_finding_raises_a_capa(self, org: Organization, agent: User) -> None:
        """The reason audit lives beside CAPA.

        An audit that closes its own findings on assertion is the usual failure.
        Routing serious ones through the quality lifecycle means their actions
        get verified for effectiveness like anything else.
        """
        engagement = an_audit(org, agent)
        finding = quality.raise_finding(
            engagement=engagement,
            observation="Cold room temperature log had no entries for six days.",
            severity=Severity.MAJOR,
            requirement="SOP-CC-002 §4",
            user=agent,
        )
        assert finding.case is not None
        assert finding.case.kind == "DEVIATION"
        assert finding.case.source == "INSPECTION"
        assert finding.status == AuditFinding.Status.ACTIONS_RAISED

    def test_a_minor_finding_does_not(self, org: Organization, agent: User) -> None:
        # Raising a CAPA for a faded shelf label is how people learn to ignore
        # the CAPA queue.
        finding = quality.raise_finding(
            engagement=an_audit(org, agent),
            observation="Shelf label faded in aisle 3.",
            severity=Severity.MINOR,
            user=agent,
        )
        assert finding.case is None

    def test_a_finding_needs_an_observation(self, org: Organization, agent: User) -> None:
        with pytest.raises(quality.QualityError, match="what was actually seen"):
            quality.raise_finding(engagement=an_audit(org, agent), observation="", user=agent)


class TestClosingAnAudit:
    def test_it_cannot_close_with_findings_unanswered(self, org: Organization, agent: User) -> None:
        """An audit nobody answered is half a conversation."""
        engagement = an_audit(org, agent)
        quality.raise_finding(engagement=engagement, observation="Bin 4 miscounted.", user=agent)
        with pytest.raises(quality.QualityError, match="no management response"):
            quality.close_audit(engagement=engagement, user=agent)

    def test_it_cannot_close_while_a_finding_has_an_open_case(
        self, org: Organization, agent: User
    ) -> None:
        """Otherwise the audit closes on paper while the thing it found is still wrong."""
        engagement = an_audit(org, agent)
        finding = quality.raise_finding(
            engagement=engagement,
            observation="Temperature log not maintained.",
            severity=Severity.MAJOR,
            user=agent,
        )
        quality.respond_to_finding(
            finding=finding, response="Log restarted; supervisor briefed.", user=agent
        )
        with pytest.raises(quality.QualityError, match="open quality cases"):
            quality.close_audit(engagement=engagement, user=agent)

    def test_it_closes_once_everything_is_answered_and_shut(
        self, org: Organization, agent: User
    ) -> None:
        engagement = an_audit(org, agent)
        finding = quality.raise_finding(
            engagement=engagement, observation="Bin 4 miscounted.", user=agent
        )
        quality.respond_to_finding(finding=finding, response="Recounted.", user=agent)
        quality.close_audit(engagement=engagement, summary="No systemic issue.", user=agent)
        assert engagement.status == AuditEngagement.Status.CLOSED
        assert engagement.completed_at is not None

    def test_a_closed_case_lets_the_audit_close(self, org: Organization, agent: User) -> None:
        engagement = an_audit(org, agent)
        finding = quality.raise_finding(
            engagement=engagement,
            observation="Temperature log not maintained.",
            severity=Severity.MAJOR,
            user=agent,
        )
        quality.respond_to_finding(finding=finding, response="Restarted.", user=agent)

        case = finding.case
        quality.record_investigation(
            case=case,
            investigation="Nobody was rostered to record it.",
            root_cause="The task was not on any shift checklist.",
            user=agent,
        )
        checker = User.objects.create_user(
            username="qa2",
            password="x",  # noqa: S106 - test fixture
            organization=org,
        )
        for kind in ("CORRECTIVE", "PREVENTIVE"):
            step = quality.add_action(case=case, description=f"{kind} step", kind=kind, user=agent)
            quality.complete_action(action=step, user=agent)
            quality.verify_action(action=step, effective=True, user=checker)
        quality.close_case(case=case, user=checker)

        quality.close_audit(engagement=engagement, user=agent)
        assert engagement.status == AuditEngagement.Status.CLOSED
        assert case.status == CaseStatus.CLOSED


class TestTheApi:
    def _client(self, user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_a_ticket_can_be_raised_and_queued(self, org: Organization, agent: User) -> None:
        client = self._client(agent)
        response = client.post(
            "/api/service-desk/tickets/",
            {
                "organization": org.pk,
                "subject": "Two boxes short on delivery",
                "body": "Ordered 10, received 8.",
                "category": "SHORTAGE",
                "priority": "HIGH",
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["ticket_number"].startswith("TKT-")
        assert response.data["hours_remaining"] is not None

        queue = client.get(f"/api/service-desk/tickets/queue/?organization={org.pk}")
        assert queue.data["open"] == 1

    def test_resolving_without_a_resolution_is_refused(
        self, org: Organization, agent: User
    ) -> None:
        ticket = desk.raise_ticket(organization=org, subject="X", body="…", user=agent)
        response = self._client(agent).post(
            f"/api/service-desk/tickets/{ticket.pk}/resolve/", {}, format="json"
        )
        assert response.status_code == 400

    def test_an_audit_and_its_findings_are_reachable(self, org: Organization, agent: User) -> None:
        client = self._client(agent)
        created = client.post(
            "/api/quality/audits/",
            {
                "organization": org.pk,
                "title": "Supplier paperwork check",
                "scope": "Licences and CoAs for the last quarter.",
                "kind": "SUPPLIER",
            },
            format="json",
        )
        assert created.status_code == 201, created.data
        pk = created.data["id"]

        added = client.post(
            f"/api/quality/audits/{pk}/add-finding/",
            {"observation": "Two CoAs missing.", "severity": "MAJOR"},
            format="json",
        )
        assert added.status_code == 200
        assert added.data["findings"][0]["case_number"].startswith("DEV-")
