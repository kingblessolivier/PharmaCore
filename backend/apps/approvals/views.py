"""Central approvals inbox — every pending approval across subsystems in one queue."""

from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.approvals.models import ApprovalRequest
from apps.approvals.serializers import ApprovalRequestSerializer
from apps.approvals.services import ApprovalError, refresh_sla
from apps.approvals.services import claim as claim_approval
from apps.approvals.services import decide as decide_approval
from apps.approvals.services import reassign as reassign_approval
from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to


class ApprovalRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only listing + action endpoints (claim/approve/reject/reassign).

    Scoped to the organizations the user can see. Holding ``approval.decide`` lets
    a user claim/decide requests; ``approval.manage`` (senior oversight) additionally
    lets them see everything visible and reassign a claim to another approver.
    """

    serializer_class = ApprovalRequestSerializer
    queryset = ApprovalRequest.objects.select_related(
        "organization", "requested_by", "claimed_by", "decided_by"
    )

    def get_queryset(self) -> QuerySet[ApprovalRequest]:
        user = cast(User, self.request.user)
        qs = ApprovalRequest.objects.select_related(
            "organization", "requested_by", "claimed_by", "decided_by"
        )
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
        refresh_sla(qs)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        mine = self.request.query_params.get("claimed_by_me")
        if mine == "1":
            qs = qs.filter(claimed_by=user)
        return qs

    def _require_decide(self, user: User) -> None:
        if not (user.is_superuser or user.has_permission("approval.decide")):
            raise PermissionDenied("You may not act on approvals.")

    @action(detail=True, methods=["post"])
    def claim(self, request: Request, pk: str | None = None) -> Response:
        user = cast(User, request.user)
        self._require_decide(user)
        approval = self.get_object()
        try:
            claim_approval(approval=approval, user=user)
        except ApprovalError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(ApprovalRequestSerializer(approval).data)

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        return self._decide(request, pk, approve=True)

    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk: str | None = None) -> Response:
        return self._decide(request, pk, approve=False)

    def _decide(self, request: Request, pk: str | None, *, approve: bool) -> Response:
        user = cast(User, request.user)
        self._require_decide(user)
        approval = self.get_object()
        try:
            decide_approval(
                approval=approval,
                user=user,
                approve=approve,
                note=str(request.data.get("note", "")),
            )
        except (ApprovalError, ValueError) as exc:
            raise ValidationError(str(exc)) from exc
        approval.refresh_from_db()
        return Response(ApprovalRequestSerializer(approval).data)

    @action(detail=True, methods=["post"])
    def reassign(self, request: Request, pk: str | None = None) -> Response:
        """Senior oversight: forward a claim to another approver."""
        user = cast(User, request.user)
        if not (user.is_superuser or user.has_permission("approval.manage")):
            raise PermissionDenied("Only senior oversight may reassign approvals.")
        approval = self.get_object()
        to_user_id = str(request.data.get("to_user"))
        try:
            to_user = User.objects.get(pk=to_user_id)
        except (User.DoesNotExist, TypeError, ValueError) as exc:
            raise ValidationError("A valid 'to_user' id is required.") from exc
        try:
            reassign_approval(approval=approval, to_user=to_user, by=user)
        except ApprovalError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(ApprovalRequestSerializer(approval).data)
