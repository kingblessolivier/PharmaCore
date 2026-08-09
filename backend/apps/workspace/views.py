"""Workspace API: contextual comments (+ @mention notifications) and notifications."""

from __future__ import annotations

from typing import Any, cast

from django.db.models import Q, QuerySet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to
from apps.workspace.models import Comment, Notification
from apps.workspace.serializers import CommentSerializer, NotificationSerializer


class CommentViewSet(viewsets.ModelViewSet):
    """Threaded comments on any record; list requires ?entity_type=&entity_id=."""

    serializer_class = CommentSerializer
    queryset = Comment.objects.select_related("author").all()
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[Comment]:
        user = cast(User, self.request.user)
        qs = Comment.objects.select_related("author").filter(
            Q(organization__in=organizations_visible_to(user)) | Q(organization__isnull=True)
        )
        et = self.request.query_params.get("entity_type")
        eid = self.request.query_params.get("entity_id")
        if et and eid:
            qs = qs.filter(entity_type=et, entity_id=eid)
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        author = cast(User, self.request.user)
        mentions: list[int] = serializer.validated_data.pop("mentions", [])
        comment = serializer.save(author=author)
        for uid in mentions:
            target = User.objects.filter(pk=uid).first()
            if target and target.pk != author.pk:
                Notification.objects.create(
                    recipient=target,
                    type=Notification.Type.MENTION,
                    title=f"{author.username} mentioned you",
                    body=comment.body[:200],
                    link_entity_type=comment.entity_type,
                    link_entity_id=comment.entity_id,
                )

    @action(detail=True, methods=["post"])
    def strike(self, request: Request, pk: str | None = None) -> Response:
        """Soft-delete (strike through) your own comment."""
        comment = self.get_object()
        if comment.author_id != cast(User, request.user).pk:
            raise PermissionDenied("You can only strike your own comment.")
        comment.is_struck = True
        comment.save(update_fields=["is_struck", "updated_at"])
        return Response(CommentSerializer(comment).data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """The current user's in-app notifications."""

    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Notification]:
        return Notification.objects.filter(recipient=cast(User, self.request.user))

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request: Request) -> Response:
        count = Notification.objects.filter(
            recipient=cast(User, request.user), is_read=False
        ).count()
        return Response({"count": count})

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request: Request, pk: str | None = None) -> Response:
        n = self.get_object()
        n.is_read = True
        n.save(update_fields=["is_read"])
        return Response(NotificationSerializer(n).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request: Request) -> Response:
        Notification.objects.filter(recipient=cast(User, request.user), is_read=False).update(
            is_read=True
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MentionableUsersView(APIView):
    """Users in an organization who can be @mentioned (id + username)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        org = request.query_params.get("organization")
        qs = User.objects.filter(is_active=True)
        if org and org.isdigit() and organizations_visible_to(user).filter(pk=int(org)).exists():
            qs = qs.filter(organization_id=int(org))
        elif not (user.is_superuser or user.has_role("SYS_ADMIN")):
            oid = user.organization_id
            qs = qs.filter(organization_id=oid) if oid else qs.none()
        data = [{"id": u.pk, "username": u.username} for u in qs.order_by("username")[:50]]
        return Response(data)


class MyWorkView(APIView):
    """What is waiting for you, what you cannot action, and what your team raised.

    The nav answers "which table would you like to open". This answers "what needs
    doing", which is the question people actually arrive with.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.workspace import worklist

        user = cast(User, request.user)
        return Response({**worklist.for_user(user), "next_steps": worklist.next_steps(user)})


class ModuleWorkView(APIView):
    """What needs doing inside one app — a module home as a queue, not a menu."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.workspace import modulework

        user = cast(User, request.user)
        module = request.query_params.get("module") or None
        return Response({"queues": modulework.queues_for(user, module)})


class ModuleInsightsView(APIView):
    """How this part of the business is doing — the figures behind a module home.

    Paired with `ModuleWorkView`: that one says what needs doing, this one says
    how it is going. Between them a module home has no reason left to be a
    second copy of the menu.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.workspace import moduleinsights

        user = cast(User, request.user)
        module = request.query_params.get("module") or ""
        return Response(moduleinsights.insights_for(user, module))
