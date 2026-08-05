"""Approvals engine: claim-to-lock, no self-approval, SLA timers, senior oversight."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import ApprovalError, claim, decide, refresh_sla
from apps.iam.models import Organization, Role, User
from django.utils import timezone
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="Depot", type="DEPOT")


@pytest.fixture
def requester(org: Organization) -> User:
    return User.objects.create_user(username="req", password="x", organization=org)


@pytest.fixture
def approver(org: Organization) -> User:
    u = User.objects.create_user(username="appr", password="x", organization=org)
    u.roles.add(Role.objects.get(code="ACCOUNTANT"))
    return u


@pytest.fixture
def senior(org: Organization) -> User:
    u = User.objects.create_user(username="senior", password="x", organization=org)
    u.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return u


@pytest.fixture
def approval(org: Organization, requester: User) -> ApprovalRequest:
    return ApprovalRequest.objects.create(
        resource_type="test.thing", resource_id="1", organization=org, requested_by=requester
    )


@pytest.mark.django_db
def test_requester_cannot_claim_own_request(approval: ApprovalRequest, requester: User) -> None:
    with pytest.raises(ApprovalError):
        claim(approval=approval, user=requester)


@pytest.mark.django_db
def test_requester_cannot_decide_own_request(
    approval: ApprovalRequest, requester: User, approver: User
) -> None:
    claim(approval=approval, user=approver)
    approval.claimed_by = requester
    approval.save()
    with pytest.raises(ApprovalError):
        decide(approval=approval, user=requester, approve=True)


@pytest.mark.django_db
def test_second_approver_cannot_claim_already_claimed(
    approval: ApprovalRequest, approver: User, senior: User
) -> None:
    claim(approval=approval, user=approver)
    with pytest.raises(ApprovalError):
        claim(approval=approval, user=senior)


@pytest.mark.django_db
def test_must_claim_before_deciding(approval: ApprovalRequest, approver: User) -> None:
    with pytest.raises(ApprovalError):
        decide(approval=approval, user=approver, approve=True)


@pytest.mark.django_db
def test_claim_then_reject(approval: ApprovalRequest, approver: User) -> None:
    claim(approval=approval, user=approver)
    decide(approval=approval, user=approver, approve=False, note="not now")
    approval.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.REJECTED
    assert approval.decided_by_id == approver.pk


@pytest.mark.django_db
def test_sla_breach_releases_claim(approval: ApprovalRequest, approver: User) -> None:
    claim(approval=approval, user=approver)
    ApprovalRequest.objects.filter(pk=approval.pk).update(
        created_at=timezone.now() - timedelta(hours=100)
    )
    approval.refresh_from_db()
    refresh_sla(ApprovalRequest.objects.filter(pk=approval.pk))
    approval.refresh_from_db()
    assert approval.claimed_by_id is None
    assert approval.sla_breached is True
    assert approval.status == ApprovalRequest.Status.PENDING


@pytest.mark.django_db
def test_inbox_scoped_and_reassign_requires_manage(
    approval: ApprovalRequest, approver: User, senior: User, requester: User
) -> None:
    listed = _auth(approver).get("/api/approvals/requests/")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    claim_resp = _auth(approver).post(f"/api/approvals/requests/{approval.pk}/claim/")
    assert claim_resp.status_code == 200, claim_resp.content

    # A plain approver (no approval.manage) cannot reassign.
    forbidden = _auth(approver).post(
        f"/api/approvals/requests/{approval.pk}/reassign/", {"to_user": senior.pk}
    )
    assert forbidden.status_code == 403

    ok = _auth(senior).post(
        f"/api/approvals/requests/{approval.pk}/reassign/", {"to_user": senior.pk}
    )
    assert ok.status_code == 200, ok.content
    approval.refresh_from_db()
    assert approval.claimed_by_id == senior.pk

    approve = _auth(senior).post(f"/api/approvals/requests/{approval.pk}/approve/")
    # senior is not the requester here, so this should succeed — but the handler
    # for "test.thing" isn't registered, so it should surface a validation error.
    assert approve.status_code == 400
