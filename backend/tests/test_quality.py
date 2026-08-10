"""Complaints, deviations, adverse events — and the two rules that matter.

Most of this file is refusals. A CAPA system that only records things is a
filing cabinet; what makes it a control is what it will not let you do:

* close a case while actions are outstanding — otherwise "closed" means
  "somebody stopped looking";
* close a critical case with corrective actions only — which fixes this
  occurrence and leaves the cause exactly where it was.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.iam.models import Organization, Permission, Role, User
from apps.quality import services
from apps.quality.models import CapaAction, CaseStatus, QualityCase, Severity
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organization:
    return Organization.objects.create(name="Kigali Central Pharmacy", type="RETAIL")


@pytest.fixture
def reporter(org: Organization) -> User:
    return User.objects.create_user(
        username="counter-staff",
        password="x",  # noqa: S106 - test fixture
        organization=org,
    )


@pytest.fixture
def quality_officer(org: Organization) -> User:
    user = User.objects.create_user(
        username="qa",
        password="x",  # noqa: S106 - test fixture
        organization=org,
    )
    role, _ = Role.objects.get_or_create(code="QA", defaults={"name": "Quality"})
    permission, _ = Permission.objects.get_or_create(
        code="inventory.adjust", defaults={"resource": "inventory", "action": "adjust"}
    )
    role.permissions.add(permission)
    user.roles.add(role)
    return user


def a_case(org: Organization, user: User, **kw) -> QualityCase:
    return services.open_case(
        organization=org,
        kind=kw.pop("kind", QualityCase.Kind.DEVIATION),
        title=kw.pop("title", "Fridge above range overnight"),
        description=kw.pop("description", "Cold room CR-01 reached 9.4 C for 18 minutes."),
        user=user,
        **kw,
    )


class TestRaisingACase:
    def test_it_is_numbered_immediately(self, org: Organization, reporter: User) -> None:
        """Somebody on the phone to a patient needs a reference before the call ends."""
        case = a_case(org, reporter, kind=QualityCase.Kind.COMPLAINT, title="Broken seal")
        assert case.case_number.startswith("CMP-")
        assert case.case_number.endswith("00001")

    def test_each_kind_has_its_own_sequence(self, org: Organization, reporter: User) -> None:
        complaint = a_case(org, reporter, kind=QualityCase.Kind.COMPLAINT, title="A")
        deviation = a_case(org, reporter, kind=QualityCase.Kind.DEVIATION, title="B")
        assert complaint.case_number.startswith("CMP-")
        assert deviation.case_number.startswith("DEV-")

    def test_a_case_needs_a_description(self, org: Organization, reporter: User) -> None:
        with pytest.raises(services.QualityError, match="description"):
            services.open_case(
                organization=org,
                kind=QualityCase.Kind.DEVIATION,
                title="Something happened",
                description="   ",
                user=reporter,
            )

    def test_a_serious_complaint_is_flagged_for_the_regulator(
        self, org: Organization, reporter: User
    ) -> None:
        # A judgement the system pre-fills rather than makes: a person can
        # still clear the flag, but nobody has to remember to set it.
        case = a_case(
            org,
            reporter,
            kind=QualityCase.Kind.COMPLAINT,
            title="Tablets discoloured",
            severity=Severity.MAJOR,
        )
        assert case.is_reportable is True

    def test_a_minor_internal_deviation_is_not(self, org: Organization, reporter: User) -> None:
        assert a_case(org, reporter, severity=Severity.MINOR).is_reportable is False

    def test_patient_details_only_belong_on_an_adverse_event(
        self, org: Organization, reporter: User
    ) -> None:
        with pytest.raises(services.QualityError, match="adverse event"):
            services.open_case(
                organization=org,
                kind=QualityCase.Kind.DEVIATION,
                title="Wrong label",
                description="Label printed with the wrong strength.",
                user=reporter,
                adverse_event={"reaction": "rash"},
            )

    def test_an_adverse_event_carries_its_clinical_detail(
        self, org: Organization, reporter: User
    ) -> None:
        case = services.open_case(
            organization=org,
            kind=QualityCase.Kind.ADVERSE_EVENT,
            title="Rash after amoxicillin",
            description="Patient reported a rash 40 minutes after the first dose.",
            severity=Severity.MAJOR,
            user=reporter,
            adverse_event={
                "reaction": "Widespread rash",
                "patient_initials": "JM",
                "patient_age": 34,
                "seriousness": "NON_SERIOUS",
            },
        )
        assert case.adverse_event.reaction == "Widespread rash"
        assert case.adverse_event.patient_age == 34


class TestTheInvestigation:
    def test_it_must_end_in_a_root_cause(self, org: Organization, reporter: User) -> None:
        case = a_case(org, reporter)
        with pytest.raises(services.QualityError, match="root cause"):
            services.record_investigation(
                case=case, investigation="Looked at the logs.", root_cause="", user=reporter
            )

    def test_recording_one_moves_the_case_on(self, org: Organization, reporter: User) -> None:
        case = a_case(org, reporter)
        services.record_investigation(
            case=case,
            investigation="Door seal perished.",
            root_cause="Seal not on the maintenance schedule.",
            user=reporter,
        )
        assert case.status == CaseStatus.ACTIONS_PENDING


class TestClosingACase:
    def _investigated(self, org: Organization, user: User, **kw) -> QualityCase:
        case = a_case(org, user, **kw)
        services.record_investigation(
            case=case,
            investigation="Door seal perished.",
            root_cause="Seal not on the maintenance schedule.",
            user=user,
        )
        return case

    def test_it_cannot_close_with_actions_outstanding(
        self, org: Organization, reporter: User, quality_officer: User
    ) -> None:
        """The first of the two rules. "Closed" must not mean "abandoned"."""
        case = self._investigated(org, reporter)
        services.add_action(case=case, description="Replace the seal", user=reporter)
        with pytest.raises(services.QualityError, match="not verified effective"):
            services.close_case(case=case, user=quality_officer)

    def test_it_cannot_close_without_a_root_cause(
        self, org: Organization, reporter: User, quality_officer: User
    ) -> None:
        case = a_case(org, reporter)
        with pytest.raises(services.QualityError, match="root cause"):
            services.close_case(case=case, user=quality_officer)

    def test_a_major_case_needs_a_preventive_action(
        self, org: Organization, reporter: User, quality_officer: User
    ) -> None:
        """The second rule, and the one that stops repeat deviations.

        Replacing the seal fixes this fridge. It does nothing about the fact
        that no seal is on a maintenance schedule, which is why the same
        deviation appears again in six months.
        """
        case = self._investigated(org, reporter, severity=Severity.MAJOR)
        fix = services.add_action(case=case, description="Replace the seal", user=reporter)
        services.complete_action(action=fix, user=reporter)
        services.verify_action(action=fix, effective=True, user=quality_officer)

        with pytest.raises(services.QualityError, match="preventive"):
            services.close_case(case=case, user=quality_officer)

    def test_it_closes_once_a_preventive_action_is_verified(
        self, org: Organization, reporter: User, quality_officer: User
    ) -> None:
        case = self._investigated(org, reporter, severity=Severity.MAJOR)
        for kind in (CapaAction.Kind.CORRECTIVE, CapaAction.Kind.PREVENTIVE):
            item = services.add_action(
                case=case, description=f"{kind} step", kind=kind, user=reporter
            )
            services.complete_action(action=item, user=reporter)
            services.verify_action(action=item, effective=True, user=quality_officer)

        services.close_case(
            case=case, note="Seal replaced, schedule updated.", user=quality_officer
        )
        case.refresh_from_db()
        assert case.status == CaseStatus.CLOSED
        assert case.closed_by == quality_officer

    def test_a_minor_case_closes_without_a_preventive_action(
        self, org: Organization, reporter: User, quality_officer: User
    ) -> None:
        # The rule is proportionate. Insisting on a preventive action for a
        # mislabelled shelf edge is how people learn to write filler.
        case = self._investigated(org, reporter, severity=Severity.MINOR)
        item = services.add_action(case=case, description="Reprint the label", user=reporter)
        services.complete_action(action=item, user=reporter)
        services.verify_action(action=item, effective=True, user=quality_officer)
        services.close_case(case=case, user=quality_officer)
        assert case.status == CaseStatus.CLOSED


class TestEffectiveness:
    def test_the_owner_cannot_verify_their_own_action(
        self, org: Organization, reporter: User
    ) -> None:
        """ "I did it" and "it worked" are different claims."""
        case = a_case(org, reporter)
        item = services.add_action(
            case=case, description="Retrain the team", owner=reporter, user=reporter
        )
        services.complete_action(action=item, user=reporter)
        with pytest.raises(services.QualityError, match="second pair of eyes"):
            services.verify_action(action=item, effective=True, user=reporter)

    def test_an_action_cannot_be_verified_before_it_is_done(
        self, org: Organization, reporter: User, quality_officer: User
    ) -> None:
        case = a_case(org, reporter)
        item = services.add_action(case=case, description="Retrain", user=reporter)
        with pytest.raises(services.QualityError, match="not been completed"):
            services.verify_action(action=item, effective=True, user=quality_officer)

    def test_an_ineffective_action_reopens_the_case(
        self, org: Organization, reporter: User, quality_officer: User
    ) -> None:
        """A check that can only conclude "yes" is a signature, not a check."""
        case = a_case(org, reporter)
        services.record_investigation(case=case, investigation="x", root_cause="y", user=reporter)
        item = services.add_action(case=case, description="Retrain", user=reporter)
        services.complete_action(action=item, user=reporter)
        services.verify_action(
            action=item, effective=False, note="Same error recurred.", user=quality_officer
        )
        case.refresh_from_db()
        assert item.status == CapaAction.Status.INEFFECTIVE
        assert case.status == CaseStatus.ACTIONS_PENDING


class TestTheWorkload:
    def test_it_counts_what_is_actually_open(
        self, org: Organization, reporter: User, quality_officer: User
    ) -> None:
        a_case(org, reporter, severity=Severity.CRITICAL, title="Critical one")
        overdue = a_case(org, reporter, title="Overdue one")
        services.add_action(
            case=overdue,
            description="Late thing",
            due_date=timezone.localdate() - timedelta(days=3),
            user=reporter,
        )
        summary = services.open_workload(organization=org.pk)
        assert summary["open_cases"] == 2
        assert summary["critical"] == 1
        assert summary["open_actions"] == 1
        assert summary["overdue_actions"] == 1


class TestTheApi:
    def _client(self, user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_anyone_may_raise_a_case(self, org: Organization, reporter: User) -> None:
        # The person who notices a problem is usually a cashier or a driver.
        # Making reporting hard produces fewer reports, not fewer problems.
        response = self._client(reporter).post(
            "/api/quality/cases/",
            {
                "organization": org.pk,
                "kind": "COMPLAINT",
                "title": "Pack arrived crushed",
                "description": "Two boxes crushed on delivery.",
                "severity": "MINOR",
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["case_number"].startswith("CMP-")

    def test_closing_needs_quality_authority(self, org: Organization, reporter: User) -> None:
        case = a_case(org, reporter)
        response = self._client(reporter).post(
            f"/api/quality/cases/{case.pk}/close/", {}, format="json"
        )
        assert response.status_code == 400
        assert "authority" in str(response.data)

    def test_the_workload_endpoint_answers(self, org: Organization, reporter: User) -> None:
        a_case(org, reporter)
        response = self._client(reporter).get(f"/api/quality/cases/workload/?organization={org.pk}")
        assert response.status_code == 200
        assert response.data["open_cases"] == 1
