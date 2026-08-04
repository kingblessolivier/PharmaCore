"""Auth views: JWT login (with audit) and the current-user endpoint."""

from __future__ import annotations

from typing import Any, cast

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.iam.serializers import UserSerializer


class LoginView(TokenObtainPairView):
    """Obtain a JWT access/refresh pair; records an audit entry on success."""

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            username = request.data.get("username", "")
            user = User.objects.filter(username=username).first()
            record_audit(action="LOGIN", user=user, request=request)
        return response


class MeView(APIView):
    """Return the authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(UserSerializer(cast(User, request.user)).data)
