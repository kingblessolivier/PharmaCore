"""PDF rendering + QR helpers.

Uses xhtml2pdf (pure-Python, no native deps → works on Windows dev and CI). The
render function is the single swap point: WeasyPrint can replace it in production
for higher-fidelity CSS without touching callers.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import segno
from django.conf import settings
from xhtml2pdf import pisa


def _resolve_asset(uri: str, rel: str) -> str:
    """Turn a URL in the HTML into something the renderer can actually open.

    An uploaded logo is stored as ``/media/uploads/logo/…`` — a path relative
    to the site, which is right for the database and meaningless to a PDF
    renderer running in a process with no web server. Without this, the logo
    that documents were rebuilt around silently renders as nothing.

    The resolved path is checked to be *inside* the media root before it is
    returned. ``logo_url`` is set by a user, and a value like
    ``/media/../../../etc/passwd`` would otherwise make the PDF generator read
    whatever the caller named and draw it into a document they can download.
    """
    if uri.startswith(("http://", "https://", "data:")):
        # Left to the renderer. A data: URI is already inline (that is how QR
        # codes get in), and a remote URL is the caller's own hosting.
        return uri

    for prefix, root in (
        (settings.MEDIA_URL, settings.MEDIA_ROOT),
        (settings.STATIC_URL, getattr(settings, "STATIC_ROOT", None)),
    ):
        if not prefix or not root:
            continue
        marker = f"/{prefix.strip('/')}/"
        if not uri.startswith(marker):
            continue
        base = Path(root).resolve()
        candidate = (base / uri[len(marker) :]).resolve()
        if candidate.is_relative_to(base) and candidate.is_file():
            return str(candidate)
        return ""
    return uri


def render_pdf(html: str) -> bytes:
    """Render an HTML string to PDF bytes."""
    out = io.BytesIO()
    result = pisa.CreatePDF(src=html, dest=out, encoding="utf-8", link_callback=_resolve_asset)
    if result.err:
        raise RuntimeError("PDF rendering failed")
    return out.getvalue()


def qr_data_uri(data: str) -> str:
    """Return a base64 PNG data URI for a QR code encoding ``data``."""
    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="png", scale=3, border=2)
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"
