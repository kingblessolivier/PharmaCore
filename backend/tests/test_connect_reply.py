"""Mail you can answer, and a thread that says who is on it.

`send_mail` has always accepted a `thread`, and the API has always passed one
through. What the thread endpoint never returned was **who is on the
conversation** — so a screen could display a conversation and not continue it,
which is exactly what it did: the reader was read-only and compose could only
ever start a new subject.
"""

from __future__ import annotations

import pytest
from apps.iam.models import Organization, User
from apps.workspace import connect
from apps.workspace.models_connect import MailRecipient
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="Remera Pharmacy", type="RETAIL")


def person(org, name):
    return User.objects.create_user(username=name, password="pw", organization=org)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def inbox_row(user):
    return connect.inbox(user=user).first()


# ---------------------------------------------------------------------------
# Replying
# ---------------------------------------------------------------------------


def test_a_reply_joins_the_thread_rather_than_starting_a_new_one(org):
    """The behaviour the whole screen exists for."""
    alice, bob = person(org, "alice"), person(org, "bob")
    sent = connect.send_mail(
        sender=alice, subject="Stock for Friday", body="Do we have enough?", to=[bob],
        organization=org,
    )

    resp = client_for(bob).post(
        "/api/workspace/mail/",
        {"subject": "", "body": "Two boxes left.", "to": [alice.pk], "thread": sent.thread.pk},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["thread"] == sent.thread.pk
    assert sent.thread.messages.count() == 2


def test_a_reply_keeps_the_threads_subject(org):
    """A reply should never rename the conversation it is joining."""
    alice, bob = person(org, "alice"), person(org, "bob")
    sent = connect.send_mail(
        sender=alice, subject="Cold chain report", body="Attached.", to=[bob], organization=org
    )
    client_for(bob).post(
        "/api/workspace/mail/",
        {"subject": "", "body": "Thanks.", "to": [alice.pk], "thread": sent.thread.pk},
        format="json",
    )
    sent.thread.refresh_from_db()
    assert sent.thread.subject == "Cold chain report"


def test_the_reply_lands_in_the_original_senders_inbox(org):
    alice, bob = person(org, "alice"), person(org, "bob")
    sent = connect.send_mail(
        sender=alice, subject="Order query", body="?", to=[bob], organization=org
    )
    client_for(bob).post(
        "/api/workspace/mail/",
        {"subject": "", "body": "Answered.", "to": [alice.pk], "thread": sent.thread.pk},
        format="json",
    )
    assert connect.inbox(user=alice).count() == 1
    assert inbox_row(alice).message.body == "Answered."


# ---------------------------------------------------------------------------
# Who is on the thread — what a reply needs and the payload did not carry
# ---------------------------------------------------------------------------


def test_the_thread_says_who_to_reply_to(org):
    alice, bob = person(org, "alice"), person(org, "bob")
    connect.send_mail(sender=alice, subject="Hello", body="Hi", to=[bob], organization=org)

    body = client_for(bob).get(f"/api/workspace/mail/{inbox_row(bob).pk}/thread/").json()
    assert [p["id"] for p in body["reply_to"]] == [alice.pk]
    assert [p["id"] for p in body["participants"]] == [alice.pk]


def test_reply_all_reaches_everyone_who_was_addressed(org):
    alice, bob, carol = person(org, "alice"), person(org, "bob"), person(org, "carol")
    connect.send_mail(
        sender=alice, subject="Rota", body="See below", to=[bob], cc=[carol], organization=org
    )

    body = client_for(bob).get(f"/api/workspace/mail/{inbox_row(bob).pk}/thread/").json()
    assert {p["id"] for p in body["participants"]} == {alice.pk, carol.pk}
    # Plain "Reply" still goes to the sender alone.
    assert [p["id"] for p in body["reply_to"]] == [alice.pk]


def test_a_bcc_recipient_is_never_disclosed_by_reply_all(org):
    """Surfacing them would disclose exactly what BCC exists to hide."""
    alice, bob, secret = person(org, "alice"), person(org, "bob"), person(org, "secret")
    connect.send_mail(
        sender=alice, subject="Terms", body="FYI", to=[bob], bcc=[secret], organization=org
    )

    body = client_for(bob).get(f"/api/workspace/mail/{inbox_row(bob).pk}/thread/").json()
    assert secret.pk not in {p["id"] for p in body["participants"]}
    # ...though the blind-copied person did receive it.
    assert connect.inbox(user=secret).count() == 1


def test_you_are_never_your_own_reply_recipient(org):
    alice, bob = person(org, "alice"), person(org, "bob")
    connect.send_mail(sender=alice, subject="Hello", body="Hi", to=[bob], organization=org)

    body = client_for(bob).get(f"/api/workspace/mail/{inbox_row(bob).pk}/thread/").json()
    assert bob.pk not in {p["id"] for p in body["participants"]}


def test_each_message_says_whether_it_is_yours(org):
    """What lets the reader draw your own messages on the other side."""
    alice, bob = person(org, "alice"), person(org, "bob")
    sent = connect.send_mail(
        sender=alice, subject="Hello", body="From Alice", to=[bob], organization=org
    )
    connect.send_mail(
        sender=bob, subject="", body="From Bob", to=[alice], thread=sent.thread, organization=org
    )

    body = client_for(bob).get(f"/api/workspace/mail/{inbox_row(bob).pk}/thread/").json()
    mine = {m["body"]: m["is_mine"] for m in body["messages"]}
    assert mine == {"From Alice": False, "From Bob": True}


def test_the_whole_conversation_is_returned_not_just_your_copy(org):
    alice, bob = person(org, "alice"), person(org, "bob")
    sent = connect.send_mail(
        sender=alice, subject="Long one", body="1", to=[bob], organization=org
    )
    for n in ("2", "3"):
        connect.send_mail(
            sender=bob, subject="", body=n, to=[alice], thread=sent.thread, organization=org
        )

    body = client_for(bob).get(f"/api/workspace/mail/{inbox_row(bob).pk}/thread/").json()
    assert [m["body"] for m in body["messages"]] == ["1", "2", "3"]


def test_a_thread_you_are_not_on_is_not_readable(org):
    alice, bob, outsider = person(org, "alice"), person(org, "bob"), person(org, "outsider")
    connect.send_mail(sender=alice, subject="Private", body="x", to=[bob], organization=org)
    row = inbox_row(bob)

    assert client_for(outsider).get(f"/api/workspace/mail/{row.pk}/thread/").status_code == 404


def test_reading_a_thread_does_not_mark_it_read_for_everyone(org):
    """Read state is per person — that is what MailRecipient is for."""
    alice, bob, carol = person(org, "alice"), person(org, "bob"), person(org, "carol")
    connect.send_mail(
        sender=alice, subject="Notice", body="x", to=[bob, carol], organization=org
    )
    connect.mark_read(recipient=inbox_row(bob), user=bob)

    assert MailRecipient.objects.get(user=bob).read_at is not None
    assert MailRecipient.objects.get(user=carol).read_at is None
