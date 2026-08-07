"""Connect services: chat and mail, with the rules that keep them honest.

Three rules do most of the work here, and each exists because its absence is a
specific, familiar bug:

1. **Unread is per person.** One recipient opening an email must not mark it read
   for the other five, so read state is written on the recipient's own row.
2. **A space you are not in is invisible** — in listings, in search, and when
   posting. Membership is checked on every read path rather than only on the UI.
3. **Nothing is hard-deleted.** A removed chat message leaves a thread that no
   longer reads sensibly, and a removed email leaves the other party's copy
   referring to something that is gone. Both are marked instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.workspace.models_connect import (
    MailMessage,
    MailRecipient,
    MailThread,
    Message,
    MessageReaction,
    Space,
    SpaceMember,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.iam.models import User


class ConnectError(ValueError):
    """A chat or mail action is not permitted as asked."""


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


def spaces_for(user: User) -> QuerySet[Space]:
    """Only the spaces this user belongs to. Everything else does not exist."""
    return Space.objects.filter(members__user=user).distinct().order_by("-last_activity_at")


def _membership(space: Space, user: User) -> SpaceMember:
    member = SpaceMember.objects.filter(space=space, user=user).first()
    if member is None:
        raise ConnectError("You are not a member of that space.")
    return member


@transaction.atomic
def create_space(
    *,
    name: str,
    created_by: User,
    organization: Any = None,
    members: list[User] | None = None,
    topic: str = "",
    is_private: bool = False,
) -> Space:
    """Open a named space. The creator is always a member and its manager."""
    if not name.strip():
        raise ConnectError("A space needs a name.")
    space = Space.objects.create(
        organization=organization,
        kind=Space.Kind.SPACE,
        name=name.strip(),
        topic=topic,
        is_private=is_private,
        created_by=created_by,
    )
    SpaceMember.objects.create(space=space, user=created_by, role=SpaceMember.Role.MANAGER)
    for person in members or []:
        if person.pk != created_by.pk:
            SpaceMember.objects.get_or_create(space=space, user=person)
    return space


@transaction.atomic
def direct_space(*, a: User, b: User) -> Space:
    """The one-to-one space between two people, created on first use.

    Returns the existing space rather than opening a second: two parallel DM
    threads between the same pair is the fastest way to lose a message.
    """
    if a.pk == b.pk:
        raise ConnectError("A direct message needs two different people.")

    # Two filters on `members` join the table twice, so annotating Count("members")
    # here counts join rows rather than people and never equals 2. The membership
    # count is therefore checked per candidate; the candidate set is at most the
    # handful of spaces these two share.
    for candidate in (
        Space.objects.filter(kind=Space.Kind.DIRECT, members__user=a)
        .filter(members__user=b)
        .distinct()
    ):
        if candidate.members.count() == 2:
            return candidate

    space = Space.objects.create(kind=Space.Kind.DIRECT, is_private=True, created_by=a)
    SpaceMember.objects.create(space=space, user=a)
    SpaceMember.objects.create(space=space, user=b)
    return space


@transaction.atomic
def post_message(
    *, space: Space, author: User, body: str, parent: Message | None = None
) -> Message:
    """Say something. A ``parent`` makes it a reply inside that thread."""
    _membership(space, author)
    if not body.strip():
        raise ConnectError("An empty message cannot be posted.")
    if parent is not None:
        if parent.space_id != space.pk:
            raise ConnectError("That thread belongs to another space.")
        # One level of nesting: replies attach to the message that opened the
        # thread, never to another reply, so a thread stays readable.
        if parent.parent_id is not None:
            parent = parent.parent

    message = Message.objects.create(space=space, author=author, body=body.strip(), parent=parent)
    space.last_activity_at = message.created_at
    space.save(update_fields=["last_activity_at"])

    # Posting counts as reading your own message, or your space would show as
    # unread to you the moment you spoke in it.
    SpaceMember.objects.filter(space=space, user=author).update(last_read_at=message.created_at)
    return message


@transaction.atomic
def edit_message(*, message: Message, user: User, body: str) -> Message:
    if message.author_id != user.pk:
        raise ConnectError("You can only edit your own messages.")
    if message.is_deleted:
        raise ConnectError("A deleted message cannot be edited.")
    if not body.strip():
        raise ConnectError("An empty message cannot be saved — delete it instead.")
    message.body = body.strip()
    message.edited_at = timezone.now()
    message.save(update_fields=["body", "edited_at"])
    return message


@transaction.atomic
def delete_message(*, message: Message, user: User) -> Message:
    """Mark rather than remove, so the thread around it still makes sense."""
    if message.author_id != user.pk:
        raise ConnectError("You can only delete your own messages.")
    message.body = ""
    message.deleted_at = timezone.now()
    message.save(update_fields=["body", "deleted_at"])
    return message


@transaction.atomic
def react(*, message: Message, user: User, emoji: str) -> bool:
    """Toggle a reaction. Returns True if it was added, False if removed."""
    _membership(message.space, user)
    existing = MessageReaction.objects.filter(message=message, user=user, emoji=emoji).first()
    if existing is not None:
        existing.delete()
        return False
    MessageReaction.objects.create(message=message, user=user, emoji=emoji)
    return True


@transaction.atomic
def mark_space_read(*, space: Space, user: User) -> SpaceMember:
    member = _membership(space, user)
    member.last_read_at = timezone.now()
    member.save(update_fields=["last_read_at"])
    return member


def unread_counts(*, user: User) -> dict[int, int]:
    """Unread messages per space for this user.

    Counted from their own ``last_read_at``, and never counting their own
    messages — you have read what you just wrote.
    """
    counts: dict[int, int] = {}
    for member in SpaceMember.objects.filter(user=user).select_related("space"):
        qs = Message.objects.filter(space_id=member.space_id, deleted_at__isnull=True).exclude(
            author=user
        )
        if member.last_read_at is not None:
            qs = qs.filter(created_at__gt=member.last_read_at)
        counts[member.space_id] = qs.count()
    return counts


def space_payload(*, space: Space, user: User) -> dict[str, Any]:
    """One space as the list shows it, including the name a DM should carry."""
    members = list(space.members.select_related("user").all())
    name = space.name
    if space.is_direct:
        other = next((m.user for m in members if m.user_id != user.pk), None)
        name = (other.get_full_name() or other.username) if other else "Direct message"
    return {
        "id": space.pk,
        "kind": space.kind,
        "name": name,
        "topic": space.topic,
        "is_private": space.is_private,
        "is_direct": space.is_direct,
        "members": [
            {
                "user": m.user_id,
                "name": m.user.get_full_name() or m.user.username,
                "role": m.role,
            }
            for m in members
        ],
        "last_activity_at": space.last_activity_at,
    }


# ---------------------------------------------------------------------------
# Mail
# ---------------------------------------------------------------------------


@dataclass
class SentMail:
    thread: MailThread
    message: MailMessage
    recipients: int


@transaction.atomic
def send_mail(
    *,
    sender: User,
    subject: str,
    body: str,
    to: list[User],
    cc: list[User] | None = None,
    bcc: list[User] | None = None,
    thread: MailThread | None = None,
    organization: Any = None,
) -> SentMail:
    """Send internal mail, starting a thread or replying to one."""
    if not to and not cc and not bcc:
        raise ConnectError("Mail needs at least one recipient.")
    if thread is None and not subject.strip():
        raise ConnectError("A new message needs a subject.")

    if thread is None:
        thread = MailThread.objects.create(organization=organization, subject=subject.strip())

    sent_at = timezone.now()
    message = MailMessage.objects.create(thread=thread, sender=sender, body=body, sent_at=sent_at)
    thread.last_message_at = sent_at
    thread.save(update_fields=["last_message_at"])

    seen: set[int] = set()
    count = 0
    for people, kind in (
        (to or [], MailRecipient.Kind.TO),
        (cc or [], MailRecipient.Kind.CC),
        (bcc or [], MailRecipient.Kind.BCC),
    ):
        for person in people:
            # A person addressed twice gets one copy, in the strongest role they
            # were given — two rows would double their unread count.
            if person.pk in seen:
                continue
            seen.add(person.pk)
            MailRecipient.objects.create(message=message, user=person, kind=kind)
            count += 1

    return SentMail(thread=thread, message=message, recipients=count)


def inbox(*, user: User, folder: str = "inbox") -> QuerySet[MailRecipient]:
    """This user's mail, in the folder they asked for.

    Folders are views over the recipient's own flags, not separate storage — the
    same message is in someone's inbox and someone else's archive at once.
    """
    qs = MailRecipient.objects.filter(user=user).select_related(
        "message", "message__thread", "message__sender"
    )
    if folder == "inbox":
        return qs.filter(is_archived=False, is_trashed=False).order_by("-message__sent_at")
    if folder == "starred":
        return qs.filter(is_starred=True, is_trashed=False).order_by("-message__sent_at")
    if folder == "archived":
        return qs.filter(is_archived=True, is_trashed=False).order_by("-message__sent_at")
    if folder == "trash":
        return qs.filter(is_trashed=True).order_by("-message__sent_at")
    if folder == "unread":
        return qs.filter(read_at__isnull=True, is_trashed=False).order_by("-message__sent_at")
    raise ConnectError(f"Unknown folder '{folder}'.")


def sent_mail(*, user: User) -> QuerySet[MailMessage]:
    return (
        MailMessage.objects.filter(sender=user, is_draft=False)
        .select_related("thread")
        .order_by("-sent_at")
    )


@transaction.atomic
def mark_read(*, recipient: MailRecipient, user: User, read: bool = True) -> MailRecipient:
    """Read state belongs to this person alone."""
    if recipient.user_id != user.pk:
        raise ConnectError("That is not your copy of the message.")
    recipient.read_at = timezone.now() if read else None
    recipient.save(update_fields=["read_at"])
    return recipient


@transaction.atomic
def set_flag(*, recipient: MailRecipient, user: User, flag: str, value: bool) -> MailRecipient:
    """Star, archive or trash — all per recipient, never for everyone."""
    if recipient.user_id != user.pk:
        raise ConnectError("That is not your copy of the message.")
    field = {"starred": "is_starred", "archived": "is_archived", "trashed": "is_trashed"}.get(flag)
    if field is None:
        raise ConnectError(f"Unknown flag '{flag}'.")
    setattr(recipient, field, value)
    recipient.save(update_fields=[field])
    return recipient


def mail_summary(*, user: User) -> dict[str, int]:
    """Counts for the mail sidebar."""
    mine = MailRecipient.objects.filter(user=user)
    return {
        "inbox": mine.filter(is_archived=False, is_trashed=False).count(),
        "unread": mine.filter(read_at__isnull=True, is_trashed=False, is_archived=False).count(),
        "starred": mine.filter(is_starred=True, is_trashed=False).count(),
        "archived": mine.filter(is_archived=True, is_trashed=False).count(),
        "trash": mine.filter(is_trashed=True).count(),
        "sent": MailMessage.objects.filter(sender=user, is_draft=False).count(),
    }


def search(*, user: User, term: str) -> dict[str, list[dict[str, Any]]]:
    """Search chat and mail together, scoped to what this user may see.

    Spaces they do not belong to are excluded — a search that leaks message text
    from a private room is the same breach as showing them the room.
    """
    term = term.strip()
    if not term:
        return {"messages": [], "mail": []}

    visible = spaces_for(user).values_list("id", flat=True)
    messages = (
        Message.objects.filter(space_id__in=visible, deleted_at__isnull=True)
        .filter(body__icontains=term)
        .select_related("space", "author")
        .order_by("-created_at")[:25]
    )
    mail = (
        MailRecipient.objects.filter(user=user, is_trashed=False)
        .filter(Q(message__body__icontains=term) | Q(message__thread__subject__icontains=term))
        .select_related("message", "message__thread", "message__sender")
        .order_by("-message__sent_at")[:25]
    )
    return {
        "messages": [
            {
                "id": m.pk,
                "space": m.space_id,
                "space_name": m.space.name or "Direct message",
                "author": (m.author.get_full_name() or m.author.username) if m.author else "",
                "body": m.body,
                "created_at": m.created_at,
            }
            for m in messages
        ],
        "mail": [
            {
                "recipient": r.pk,
                "thread": r.message.thread_id,
                "subject": r.message.thread.subject,
                "sender": (
                    (r.message.sender.get_full_name() or r.message.sender.username)
                    if r.message.sender
                    else ""
                ),
                "sent_at": r.message.sent_at,
                "is_read": r.is_read,
            }
            for r in mail
        ],
    }
