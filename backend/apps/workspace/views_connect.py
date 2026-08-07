"""Connect API — chat and mail. Transport only; the rules live in ``connect.py``."""

from __future__ import annotations

from typing import Any, cast

from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.core.lookups import lookup_pk
from apps.iam.models import User
from apps.workspace import connect
from apps.workspace.models_connect import MailRecipient, Message, Space


def _users(request: Request, key: str) -> list[User]:
    ids = [lookup_pk(v) for v in (request.data.get(key) or [])]
    return list(User.objects.filter(pk__in=ids))


def _message_payload(message: Message, viewer: User) -> dict[str, Any]:
    reactions: dict[str, int] = {}
    mine: set[str] = set()
    for r in message.reactions.all():
        reactions[r.emoji] = reactions.get(r.emoji, 0) + 1
        if r.user_id == viewer.pk:
            mine.add(r.emoji)
    return {
        "id": message.pk,
        "space": message.space_id,
        "parent": message.parent_id,
        "author": message.author_id,
        "author_name": (
            (message.author.get_full_name() or message.author.username) if message.author else ""
        ),
        "body": message.body,
        "is_deleted": message.is_deleted,
        "is_mine": message.author_id == viewer.pk,
        "edited_at": message.edited_at,
        "created_at": message.created_at,
        "reply_count": message.reply_count,
        "reactions": [
            {"emoji": e, "count": n, "mine": e in mine} for e, n in sorted(reactions.items())
        ],
    }


class SpaceViewSet(ViewSet):
    """Chat spaces and direct messages."""

    permission_classes = [IsAuthenticated]

    def list(self, request: Request) -> Response:
        user = cast(User, request.user)
        unread = connect.unread_counts(user=user)
        rows = [
            {**connect.space_payload(space=s, user=user), "unread": unread.get(s.pk, 0)}
            for s in connect.spaces_for(user).prefetch_related("members__user")
        ]
        return Response({"results": rows, "count": len(rows)})

    def create(self, request: Request) -> Response:
        user = cast(User, request.user)
        try:
            space = connect.create_space(
                name=request.data.get("name", ""),
                created_by=user,
                organization=user.organization,
                members=_users(request, "members"),
                topic=request.data.get("topic", ""),
                is_private=bool(request.data.get("is_private", False)),
            )
        except connect.ConnectError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(connect.space_payload(space=space, user=user), status=201)

    def _space(self, request: Request, pk: str | None) -> Space:
        """A space you are not in does not exist — including by direct id."""
        user = cast(User, request.user)
        space = connect.spaces_for(user).filter(pk=lookup_pk(pk)).first()
        if space is None:
            raise ValidationError("No such space.")
        return space

    @action(detail=False, methods=["post"])
    def direct(self, request: Request) -> Response:
        """Open (or reuse) the one-to-one space with another person."""
        user = cast(User, request.user)
        other = get_object_or_404(User, pk=lookup_pk(request.data.get("user")))
        try:
            space = connect.direct_space(a=user, b=other)
        except connect.ConnectError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(connect.space_payload(space=space, user=user))

    @action(detail=True, methods=["get", "post"])
    def messages(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        space = self._space(request, pk)

        if request.method == "POST":
            parent = None
            raw_parent = request.data.get("parent")
            if raw_parent:
                parent = get_object_or_404(Message, pk=lookup_pk(raw_parent))
            try:
                message = connect.post_message(
                    space=space,
                    author=user,
                    body=request.data.get("body", ""),
                    parent=parent,
                )
            except connect.ConnectError as exc:
                raise ValidationError(str(exc)) from exc
            return Response(_message_payload(message, user), status=201)

        # Top-level messages only; replies come back nested under their parent.
        qs = (
            Message.objects.filter(space=space, parent__isnull=True)
            .select_related("author")
            .prefetch_related("reactions", "replies__author", "replies__reactions")
        )
        rows = []
        for message in qs:
            payload = _message_payload(message, user)
            payload["replies"] = [_message_payload(r, user) for r in message.replies.all()]
            rows.append(payload)
        return Response({"results": rows, "count": len(rows)})

    @action(detail=True, methods=["post"])
    def read(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        connect.mark_space_read(space=self._space(request, pk), user=user)
        return Response({"ok": True})


class MessageActionsView(APIView):
    """Edit, delete or react to one message."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk: int, verb: str) -> Response:
        user = cast(User, request.user)
        message = get_object_or_404(Message, pk=pk)
        if not connect.spaces_for(user).filter(pk=message.space_id).exists():
            raise ValidationError("No such message.")
        try:
            if verb == "edit":
                message = connect.edit_message(
                    message=message, user=user, body=request.data.get("body", "")
                )
            elif verb == "delete":
                message = connect.delete_message(message=message, user=user)
            elif verb == "react":
                added = connect.react(
                    message=message, user=user, emoji=request.data.get("emoji", "")
                )
                message.refresh_from_db()
                return Response({**_message_payload(message, user), "added": added})
            else:
                raise ValidationError(f"Unknown action '{verb}'.")
        except connect.ConnectError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(_message_payload(message, user))


class MailViewSet(ViewSet):
    """Internal email."""

    permission_classes = [IsAuthenticated]

    def list(self, request: Request) -> Response:
        user = cast(User, request.user)
        folder = request.query_params.get("folder", "inbox")
        try:
            rows = connect.inbox(user=user, folder=folder)
        except connect.ConnectError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {
                "folder": folder,
                "summary": connect.mail_summary(user=user),
                "results": [
                    {
                        "recipient": r.pk,
                        "message": r.message_id,
                        "thread": r.message.thread_id,
                        "subject": r.message.thread.subject,
                        "sender": r.message.sender_id,
                        "sender_name": (
                            (r.message.sender.get_full_name() or r.message.sender.username)
                            if r.message.sender
                            else ""
                        ),
                        "preview": r.message.body[:140],
                        "kind": r.kind,
                        "is_read": r.is_read,
                        "is_starred": r.is_starred,
                        "is_archived": r.is_archived,
                        "sent_at": r.message.sent_at,
                    }
                    for r in rows[:200]
                ],
            }
        )

    def create(self, request: Request) -> Response:
        """Send mail, or reply into an existing thread."""
        from apps.workspace.models_connect import MailThread

        user = cast(User, request.user)
        thread = None
        raw_thread = request.data.get("thread")
        if raw_thread:
            thread = get_object_or_404(MailThread, pk=lookup_pk(raw_thread))
        try:
            sent = connect.send_mail(
                sender=user,
                subject=request.data.get("subject", ""),
                body=request.data.get("body", ""),
                to=_users(request, "to"),
                cc=_users(request, "cc"),
                bcc=_users(request, "bcc"),
                thread=thread,
                organization=user.organization,
            )
        except connect.ConnectError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {
                "thread": sent.thread.pk,
                "message": sent.message.pk,
                "subject": sent.thread.subject,
                "recipients": sent.recipients,
            },
            status=201,
        )

    @action(detail=False, methods=["get"])
    def sent(self, request: Request) -> Response:
        user = cast(User, request.user)
        return Response(
            {
                "results": [
                    {
                        "message": m.pk,
                        "thread": m.thread_id,
                        "subject": m.thread.subject,
                        "preview": m.body[:140],
                        "sent_at": m.sent_at,
                        "recipients": m.recipients.count(),
                    }
                    for m in connect.sent_mail(user=user)[:200]
                ]
            }
        )

    @action(detail=True, methods=["post"])
    def flag(self, request: Request, pk: str | None = None) -> Response:
        """Read, star, archive or trash — this person's copy only."""
        user = cast(User, request.user)
        recipient = get_object_or_404(MailRecipient, pk=lookup_pk(pk))
        name = request.data.get("flag", "")
        value = bool(request.data.get("value", True))
        try:
            if name == "read":
                recipient = connect.mark_read(recipient=recipient, user=user, read=value)
            else:
                recipient = connect.set_flag(recipient=recipient, user=user, flag=name, value=value)
        except connect.ConnectError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {
                "recipient": recipient.pk,
                "is_read": recipient.is_read,
                "is_starred": recipient.is_starred,
                "is_archived": recipient.is_archived,
                "is_trashed": recipient.is_trashed,
            }
        )

    @action(detail=True, methods=["get"])
    def thread(self, request: Request, pk: str | None = None) -> Response:
        """The whole conversation this message belongs to."""
        user = cast(User, request.user)
        recipient = get_object_or_404(MailRecipient, pk=lookup_pk(pk), user=user)
        messages = recipient.message.thread.messages.select_related("sender").all()
        return Response(
            {
                "thread": recipient.message.thread_id,
                "subject": recipient.message.thread.subject,
                "messages": [
                    {
                        "id": m.pk,
                        "sender": m.sender_id,
                        "sender_name": (
                            (m.sender.get_full_name() or m.sender.username) if m.sender else ""
                        ),
                        "body": m.body,
                        "sent_at": m.sent_at,
                    }
                    for m in messages
                ],
            }
        )


class ConnectSearchView(APIView):
    """Search chat and mail together, scoped to what this user may see."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        return Response(connect.search(user=user, term=request.query_params.get("q", "")))
