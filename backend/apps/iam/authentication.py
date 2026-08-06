"""Token-version aware JWT auth — lets an admin force-logout a user.

Every issued token carries the user's ``token_version`` (``tv``). Bumping a user's
``token_version`` (force-logout) invalidates all their outstanding access/refresh
tokens at once. Tokens minted before this feature carry no ``tv`` and are honoured
until they expire (grandfathered), so enabling it never logs anyone out spuriously.
"""

from __future__ import annotations

from typing import Any, cast

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken, Token

from apps.iam.models import User


class VersionedTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login serializer that stamps the user's token_version onto the token."""

    @classmethod
    def get_token(cls, user: User) -> Token:  # type: ignore[override]
        token = super().get_token(user)
        token["tv"] = user.token_version
        return token


class VersionedTokenRefreshSerializer(TokenRefreshSerializer):
    """Refresh serializer that carries ``tv`` from the refresh token onto the new
    access token, so refreshed sessions remain revocable."""

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        data = super().validate(attrs)
        refresh = RefreshToken(attrs["refresh"])
        tv = refresh.get("tv")
        if tv is not None:
            from rest_framework_simplejwt.tokens import AccessToken

            access = AccessToken(data["access"])  # type: ignore[arg-type]
            access["tv"] = tv
            data["access"] = str(access)
        return data


class VersionedJWTAuthentication(JWTAuthentication):
    """Rejects a token whose ``tv`` no longer matches the user's token_version."""

    def get_user(self, validated_token: Any) -> User:  # type: ignore[override]
        user = cast(User, super().get_user(validated_token))
        tv = validated_token.get("tv")
        if tv is not None and tv != user.token_version:
            raise AuthenticationFailed(
                "Session ended — please sign in again.", code="token_revoked"
            )
        return user
