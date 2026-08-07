"""Connect: chat and mail.

Most of these pin the same rule from different angles — **state that differs per
person lives on that person's row**. Getting it wrong is the classic bug in both
media: one recipient opening an email marks it read for everyone, or one person's
last-read marker clears another's unread badge.
"""

import pytest
from apps.iam.models import Organization, User
from apps.workspace import connect
from apps.workspace.models_connect import MailRecipient, Message, Space

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="Kigali Pharmacy", type="RETAIL")


@pytest.fixture
def alice(org):
    return User.objects.create_user(username="alice", password="x", organization=org)


@pytest.fixture
def bob(org):
    return User.objects.create_user(username="bob", password="x", organization=org)


@pytest.fixture
def carol(org):
    return User.objects.create_user(username="carol", password="x", organization=org)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


def test_a_space_you_are_not_in_does_not_exist(alice, bob):
    connect.create_space(name="Managers", created_by=alice)
    assert connect.spaces_for(alice).count() == 1
    assert connect.spaces_for(bob).count() == 0, "not a member, so not visible"


def test_posting_to_a_space_you_are_not_in_is_refused(alice, bob):
    space = connect.create_space(name="Managers", created_by=alice)
    with pytest.raises(connect.ConnectError, match="not a member"):
        connect.post_message(space=space, author=bob, body="hello")


def test_a_direct_message_is_reused_not_duplicated(alice, bob):
    """Two parallel DM threads between the same pair is how a message goes missing."""
    first = connect.direct_space(a=alice, b=bob)
    second = connect.direct_space(a=bob, b=alice)
    assert first.pk == second.pk
    assert Space.objects.filter(kind=Space.Kind.DIRECT).count() == 1


def test_you_cannot_direct_message_yourself(alice):
    with pytest.raises(connect.ConnectError, match="two different people"):
        connect.direct_space(a=alice, b=alice)


def test_replies_thread_one_level_deep(alice):
    """A reply to a reply attaches to the thread's opener, so it stays readable."""
    space = connect.create_space(name="Ops", created_by=alice)
    root = connect.post_message(space=space, author=alice, body="Stock arrives Tuesday")
    reply = connect.post_message(space=space, author=alice, body="Which supplier?", parent=root)
    nested = connect.post_message(space=space, author=alice, body="Acme", parent=reply)

    assert reply.parent_id == root.pk
    assert nested.parent_id == root.pk, "flattened onto the opener, not nested under a reply"
    assert root.replies.count() == 2


def test_unread_is_counted_per_person_and_excludes_your_own(alice, bob):
    space = connect.create_space(name="Ops", created_by=alice, members=[bob])
    connect.post_message(space=space, author=alice, body="one")
    connect.post_message(space=space, author=alice, body="two")

    assert connect.unread_counts(user=bob)[space.pk] == 2
    assert connect.unread_counts(user=alice)[space.pk] == 0, "you have read what you wrote"

    connect.mark_space_read(space=space, user=bob)
    assert connect.unread_counts(user=bob)[space.pk] == 0


def test_one_persons_read_marker_does_not_clear_anothers(alice, bob, carol):
    space = connect.create_space(name="Ops", created_by=alice, members=[bob, carol])
    connect.post_message(space=space, author=alice, body="notice")
    connect.mark_space_read(space=space, user=bob)

    assert connect.unread_counts(user=bob)[space.pk] == 0
    assert connect.unread_counts(user=carol)[space.pk] == 1, "carol has still not read it"


def test_a_deleted_message_is_marked_not_removed(alice):
    """A vanished message leaves a thread that no longer reads sensibly."""
    space = connect.create_space(name="Ops", created_by=alice)
    message = connect.post_message(space=space, author=alice, body="oops")
    connect.delete_message(message=message, user=alice)

    message.refresh_from_db()
    assert message.is_deleted
    assert message.body == ""
    assert Message.objects.filter(pk=message.pk).exists()


def test_you_can_only_edit_your_own_messages(alice, bob):
    space = connect.create_space(name="Ops", created_by=alice, members=[bob])
    message = connect.post_message(space=space, author=alice, body="mine")
    with pytest.raises(connect.ConnectError, match="your own"):
        connect.edit_message(message=message, user=bob, body="hijacked")


def test_reacting_twice_with_the_same_emoji_toggles_it_off(alice):
    space = connect.create_space(name="Ops", created_by=alice)
    message = connect.post_message(space=space, author=alice, body="ship it")

    assert connect.react(message=message, user=alice, emoji="👍") is True
    assert message.reactions.count() == 1
    assert connect.react(message=message, user=alice, emoji="👍") is False
    assert message.reactions.count() == 0


# ---------------------------------------------------------------------------
# Mail
# ---------------------------------------------------------------------------


def test_mail_reaches_every_recipient(alice, bob, carol):
    sent = connect.send_mail(sender=alice, subject="Rota", body="Next week", to=[bob], cc=[carol])
    assert sent.recipients == 2
    assert connect.inbox(user=bob).count() == 1
    assert connect.inbox(user=carol).count() == 1


def test_reading_is_per_recipient(alice, bob, carol):
    """The bug this prevents: one person's click marking everybody's mail read."""
    connect.send_mail(sender=alice, subject="Rota", body="Next week", to=[bob, carol])
    bobs = connect.inbox(user=bob).first()
    connect.mark_read(recipient=bobs, user=bob)

    assert connect.mail_summary(user=bob)["unread"] == 0
    assert connect.mail_summary(user=carol)["unread"] == 1


def test_you_cannot_flag_someone_elses_copy(alice, bob, carol):
    connect.send_mail(sender=alice, subject="Rota", body="Next week", to=[bob, carol])
    bobs = connect.inbox(user=bob).first()
    with pytest.raises(connect.ConnectError, match="not your copy"):
        connect.mark_read(recipient=bobs, user=carol)


def test_archiving_moves_it_out_of_the_inbox_for_that_person_only(alice, bob, carol):
    connect.send_mail(sender=alice, subject="Rota", body="Next week", to=[bob, carol])
    bobs = connect.inbox(user=bob).first()
    connect.set_flag(recipient=bobs, user=bob, flag="archived", value=True)

    assert connect.inbox(user=bob).count() == 0
    assert connect.inbox(user=bob, folder="archived").count() == 1
    assert connect.inbox(user=carol).count() == 1, "carol's copy is untouched"


def test_a_reply_joins_the_same_thread(alice, bob):
    first = connect.send_mail(sender=alice, subject="Rota", body="Next week", to=[bob])
    reply = connect.send_mail(sender=bob, subject="", body="Noted", to=[alice], thread=first.thread)
    assert reply.thread.pk == first.thread.pk
    assert first.thread.message_count == 2


def test_mail_needs_a_recipient_and_a_subject(alice, bob):
    with pytest.raises(connect.ConnectError, match="at least one recipient"):
        connect.send_mail(sender=alice, subject="Hi", body="x", to=[])
    with pytest.raises(connect.ConnectError, match="needs a subject"):
        connect.send_mail(sender=alice, subject="  ", body="x", to=[bob])


def test_someone_addressed_twice_gets_one_copy(alice, bob):
    """Two rows would double their unread count for a single email."""
    sent = connect.send_mail(sender=alice, subject="Rota", body="x", to=[bob], cc=[bob])
    assert sent.recipients == 1
    assert MailRecipient.objects.filter(message=sent.message, user=bob).count() == 1


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_never_leaks_a_space_you_are_not_in(alice, bob):
    """Leaking the message text is the same breach as showing the room."""
    private = connect.create_space(name="Board", created_by=alice, is_private=True)
    connect.post_message(space=private, author=alice, body="confidential merger")

    assert len(connect.search(user=alice, term="merger")["messages"]) == 1
    assert connect.search(user=bob, term="merger")["messages"] == []


def test_search_finds_mail_by_subject_and_body(alice, bob):
    connect.send_mail(sender=alice, subject="Quarterly rota", body="starts Monday", to=[bob])
    assert len(connect.search(user=bob, term="rota")["mail"]) == 1
    assert len(connect.search(user=bob, term="Monday")["mail"]) == 1
    assert connect.search(user=bob, term="")["mail"] == []
