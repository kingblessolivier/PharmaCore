"""Security-headers middleware — sets CSP, Referrer-Policy and Permissions-Policy
on every response (see docs/08-security-and-compliance.md §6)."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

# Strict for our own responses (JSON API + admin); allows the swagger-ui CDN so
# /api/docs/ keeps working. The React SPA is served from its own origin.
_CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "object-src 'none'"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", _CSP)
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()"
        )
        return response
