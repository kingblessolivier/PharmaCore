"""Workspace: contextual comments, @mention notifications, notification read."""

from __future__ import annotations

import pytest
from apps.iam.models import Organization, User
from apps.workspace.models import Comment, Notification
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="Kigali", type=Organization.OrgType.RETAIL)


@pytest.fixture
def alice(org: Organization) -> User:
    return User.objects.create_user(username="alice", password="x", organization=org)


@pytest.fixture
def bob(org: Organization) -> User:
    return User.objects.create_user(username="bob", password="x", organization=org)


@pytest.mark.django_db
def test_comment_on_entity_and_list(alice: User, org: Organization) -> None:
    client = _auth(alice)
    resp = client.post(
        "/api/workspace/comments/",
        {
            "entity_type": "stock_order",
            "entity_id": "5",
            "organization": org.pk,
            "body": "Please rush this.",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    listed = client.get("/api/workspace/comments/?entity_type=stock_order&entity_id=5")
    assert listed.json()["count"] == 1
    assert listed.json()["results"][0]["author_name"] == "alice"


@pytest.mark.django_db
def test_mention_creates_notification(alice: User, bob: User, org: Organization) -> None:
    resp = _auth(alice).post(
        "/api/workspace/comments/",
        {
            "entity_type": "grn",
            "entity_id": "9",
            "organization": org.pk,
            "body": "@bob check this",
            "mentions": [bob.pk],
        },
        format="json",
    )
    assert resp.status_code == 201
    n = Notification.objects.filter(recipient=bob, type="MENTION")
    assert n.exists()
    assert n.first().link_entity_type == "grn"


@pytest.mark.django_db
def test_notifications_scoped_and_marked_read(alice: User, bob: User, org: Organization) -> None:
    Notification.objects.create(recipient=bob, title="hi")
    # alice sees none of bob's notifications
    assert _auth(alice).get("/api/workspace/notifications/").json()["count"] == 0
    bob_client = _auth(bob)
    assert bob_client.get("/api/workspace/notifications/unread-count/").json()["count"] == 1
    bob_client.post("/api/workspace/notifications/mark-all-read/")
    assert bob_client.get("/api/workspace/notifications/unread-count/").json()["count"] == 0


@pytest.mark.django_db
def test_strike_only_own_comment(alice: User, bob: User, org: Organization) -> None:
    c = Comment.objects.create(
        entity_type="x", entity_id="1", author=alice, body="mine", organization=org
    )
    assert _auth(bob).post(f"/api/workspace/comments/{c.pk}/strike/").status_code == 403
    assert _auth(alice).post(f"/api/workspace/comments/{c.pk}/strike/").status_code == 200
    c.refresh_from_db()
    assert c.is_struck is True
