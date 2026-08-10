"""Service desk API."""

from __future__ import annotations

from typing import Any, cast

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to
from apps.servicedesk import services
from apps.servicedesk.models import Ticket
from apps.servicedesk.serializers import TicketSerializer


class TicketViewSet(viewsets.ModelViewSet):
    """The queue, ordered by what is closest to breaching."""

    permission_classes = [IsAuthenticated]
    serializer_class = TicketSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        user = cast(User, self.request.user)
        qs = Ticket.objects.select_related(
            "assigned_to", "customer_organization", "product", "quality_case"
        ).prefetch_related("notes")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        params = self.request.query_params
        for field in ("status", "priority", "category"):
            if params.get(field):
                qs = qs.filter(**{field: params[field]})
        if params.get("open") == "true":
            qs = qs.exclude(status__in=["RESOLVED", "CLOSED"])
        if params.get("mine") == "true":
            qs = qs.filter(assigned_to=user)
        if params.get("breached") == "true":
            qs = qs.filter(due_at__lt=timezone.now()).exclude(status__in=["RESOLVED", "CLOSED"])
        return qs

    def perform_create(self, serializer: Any) -> None:
        try:
            serializer.instance = services.raise_ticket(
                user=cast(User, self.request.user), **serializer.validated_data
            )
        except services.TicketError as exc:
            raise ValidationError(str(exc)) from exc

    @action(detail=True, methods=["post"], url_path="add-note")
    def add_note(self, request: Request, pk: str | None = None) -> Response:
        ticket = self.get_object()
        try:
            services.add_note(
                ticket=ticket,
                body=str(request.data.get("body", "")),
                internal=request.data.get("internal") in (True, "true", "1", 1),
                user=cast(User, request.user),
            )
        except services.TicketError as exc:
            raise ValidationError(str(exc)) from exc
        ticket.refresh_from_db()
        return Response(self.get_serializer(ticket).data)

    @action(detail=True, methods=["post"])
    def resolve(self, request: Request, pk: str | None = None) -> Response:
        ticket = self.get_object()
        try:
            services.resolve_ticket(
                ticket=ticket,
                resolution=str(request.data.get("resolution", "")),
                user=cast(User, request.user),
            )
        except services.TicketError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(ticket).data)

    @action(detail=True, methods=["post"])
    def assign(self, request: Request, pk: str | None = None) -> Response:
        ticket = self.get_object()
        owner_id = request.data.get("user")
        owner = User.objects.filter(pk=owner_id).first() if owner_id else None
        ticket.assigned_to = owner
        if ticket.status == Ticket.Status.OPEN and owner:
            ticket.status = Ticket.Status.IN_PROGRESS
        ticket.save(update_fields=["assigned_to", "status", "updated_at"])
        return Response(self.get_serializer(ticket).data)

    @action(detail=True, methods=["post"], url_path="escalate-to-quality")
    def escalate(self, request: Request, pk: str | None = None) -> Response:
        ticket = self.get_object()
        try:
            services.escalate_to_quality(ticket=ticket, user=cast(User, request.user))
        except services.TicketError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(ticket).data)

    @action(detail=False, methods=["get"])
    def queue(self, request: Request) -> Response:
        user = cast(User, request.user)
        org = request.query_params.get("organization") or user.organization_id
        return Response(services.queue_summary(organization=org))
