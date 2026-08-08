"""Connect: chat and email, in the shape people already know.

Modelled on Google Workspace and Microsoft 365 because that is what staff have
used before — nobody needs to be taught an inbox, and a pharmacy is not the place
to teach one.

**Chat.** Spaces are Teams channels / Google Chat Spaces: a named room with its
own history. A direct message is the same object with two members and no name,
which keeps one set of rules for membership, unread counts and search rather than
two that drift apart. Everything is threadable — Google extended inline threading
to DMs and group chats in November 2025, so threads-only-in-channels is now the
odd behaviour rather than the expected one.

**Email.** Internal mail, so someone can be given an inbox without provisioning a
mailbox anywhere.

The rule that shapes both: **state that differs per person lives on the person's
row, not the message.** A message read by one recipient is unread for everyone
else, so read/starred/archived belong to ``MailRecipient`` and the last-read
marker belongs to ``SpaceMember``. Putting them on the message is the bug that
makes one person's click mark everybody's mail as read.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class Space(models.Model):
    """A room: a branch channel, a department, or a direct message between two."""

    class Kind(models.TextChoices):
        SPACE = "SPACE", "Space"
        DIRECT = "DIRECT", "Direct message"

    organization = models.ForeignKey(
        "iam.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="spaces"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.SPACE)
    #: Blank for a direct message — its name is whoever else is in it.
    name = models.CharField(max_length=120, blank=True, default="")
    topic = models.CharField(max_length=255, blank=True, default="")
    is_private = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    #: Bumped on every message so a space list can sort by activity without
    #: aggregating over the whole message table on each request.
    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_activity_at"]
        indexes = [models.Index(fields=["organization", "kind"])]

    def __str__(self) -> str:
        return self.name or f"Direct message #{self.pk}"

    @property
    def is_direct(self) -> bool:
        return self.kind == self.Kind.DIRECT


class SpaceMember(models.Model):
    """Who is in a space, and how far they have read.

    ``last_read_at`` is per member because unread is a property of the person.
    """

    class Role(models.TextChoices):
        MEMBER = "MEMBER", "Member"
        MANAGER = "MANAGER", "Manager"

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="space_memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["space", "user"], name="uniq_space_member")]
        indexes = [models.Index(fields=["user", "space"])]

    def __str__(self) -> str:
        return f"{self.user} in {self.space}"


class Message(models.Model):
    """A chat message, optionally a reply inside a thread."""

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    #: A reply points at the message that started the thread. Null means it *is*
    #: a top-level message, which may itself have replies.
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    body = models.TextField()
    edited_at = models.DateTimeField(null=True, blank=True)
    #: Deleting blanks the body and marks it rather than removing the row: a
    #: vanished message leaves a thread that no longer makes sense to read.
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["space", "created_at"]),
            models.Index(fields=["parent"]),
        ]

    def __str__(self) -> str:
        return f"{self.author}: {self.body[:40]}"

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def reply_count(self) -> int:
        return self.replies.count()


class MessageReaction(models.Model):
    """One emoji from one person on one message."""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    emoji = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user", "emoji"], name="uniq_reaction_per_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.emoji} by {self.user}"


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


class MailThread(models.Model):
    """A conversation. Replies group under it, as an inbox expects."""

    organization = models.ForeignKey(
        "iam.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="mail"
    )
    subject = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self) -> str:
        return self.subject or "(no subject)"

    @property
    def message_count(self) -> int:
        return self.messages.count()


class MailMessage(models.Model):
    """One email in a thread."""

    thread = models.ForeignKey(MailThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = models.TextField()
    #: Kept out of the recipient rows: a draft has no recipients yet, and a sent
    #: message must not become a draft again.
    is_draft = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["thread", "created_at"])]

    def __str__(self) -> str:
        return f"{self.sender} — {self.thread.subject[:40]}"


class MailRecipient(models.Model):
    """One person's copy of one message, and what they have done with it.

    Read, starred, archived and trashed all live here rather than on the message,
    because they are true of a person and not of the mail. One recipient reading
    an email must not mark it read for the other five.
    """

    class Kind(models.TextChoices):
        TO = "TO", "To"
        CC = "CC", "Cc"
        BCC = "BCC", "Bcc"

    message = models.ForeignKey(MailMessage, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mail_received"
    )
    kind = models.CharField(max_length=4, choices=Kind.choices, default=Kind.TO)
    read_at = models.DateTimeField(null=True, blank=True)
    is_starred = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_trashed = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["message", "user"], name="uniq_mail_recipient")
        ]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self) -> str:
        return f"{self.user} ({self.kind})"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class MailLabel(models.Model):
    """A user's own folder. Labels are personal, like Gmail's."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mail_labels"
    )
    name = models.CharField(max_length=60)
    colour = models.CharField(max_length=20, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["user", "name"], name="uniq_label_per_user")]

    def __str__(self) -> str:
        return self.name


class MailThreadLabel(models.Model):
    """A label applied to a thread, by the person who owns the label."""

    label = models.ForeignKey(MailLabel, on_delete=models.CASCADE, related_name="threads")
    thread = models.ForeignKey(MailThread, on_delete=models.CASCADE, related_name="labels")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["label", "thread"], name="uniq_thread_label")
        ]

    def __str__(self) -> str:
        return f"{self.label} on {self.thread}"
