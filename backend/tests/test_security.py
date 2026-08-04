"""Security headers + deploy-check config."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.test import Client
from django.test.utils import override_settings


def test_security_headers_present() -> None:
    resp = Client().get("/health")
    assert "default-src 'self'" in resp["Content-Security-Policy"]
    assert resp["X-Content-Type-Options"] == "nosniff"
    assert resp["Referrer-Policy"] == "same-origin"
    assert "camera=()" in resp["Permissions-Policy"]


@override_settings(
    DEBUG=False,
    SECRET_KEY="a-sufficiently-long-and-unique-production-secret-key-value-123456",
    SECURE_SSL_REDIRECT=True,
    SECURE_HSTS_SECONDS=31536000,
    SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
    SECURE_HSTS_PRELOAD=True,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    ALLOWED_HOSTS=["pharmacore.rw"],
)
def test_deploy_check_security_clean() -> None:
    # No security-tagged deploy warnings/errors in a production configuration.
    call_command("check", "--deploy", "--tag", "security", "--fail-level", "WARNING")


@pytest.mark.django_db
def test_login_endpoint_is_throttled_scope_configured() -> None:
    from django.conf import settings

    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert "anon" in rates and "user" in rates
