"""Token-version aware JWT auth — lets an admin force-logout a user.

Every issued token carries the user's ``token_version`` (``tv``). Bumping a user's
``token_version`` (force-logout) invalidates all their outstanding access/refresh
tokens at once. Tokens minted before this feature carry no ``tv`` and are honoured
until they expire (grandfathered), so enabling it never logs anyone out spuriously.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any, cast

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken, Token

from apps.iam.models import ApiKey, User


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return (raw_key, prefix, key_hash). The raw key is shown to the admin once."""
    raw = "pk_" + secrets.token_urlsafe(32)
    return raw, raw[:12], hash_api_key(raw)


class ApiKeyAuthentication(BaseAuthentication):
    """Authenticate a request by an ``X-API-Key`` header, acting as the key's user."""

    def authenticate(self, request: Request) -> tuple[User, ApiKey] | None:
        raw = request.META.get("HTTP_X_API_KEY")
        if not raw:
            return None
        key = (
            ApiKey.objects.select_related("user")
            .filter(key_hash=hash_api_key(raw), is_active=True)
            .first()
        )
        if key is None:
            raise AuthenticationFailed("Invalid API key.")
        if not key.user.is_active:
            raise AuthenticationFailed("The account for this key is inactive.")
        ApiKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return key.user, key

    def authenticate_header(self, request: Request) -> str:
        # Ensures DRF returns 401 (not 403) when an API key is rejected.
        return "Api-Key"


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
