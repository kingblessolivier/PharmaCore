"""PDF rendering + QR helpers.

Uses xhtml2pdf (pure-Python, no native deps → works on Windows dev and CI). The
render function is the single swap point: WeasyPrint can replace it in production
for higher-fidelity CSS without touching callers.
"""

from __future__ import annotations

import base64
import io
import re
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
    if uri.startswith("data:"):
        # Already inline — that is how QR codes get in.
        return uri

    if uri.startswith(("http://", "https://")):
        # Refused, deliberately. Letting the renderer fetch it means this
        # process makes an outbound request every time it draws a document,
        # and all three of the ways that goes wrong were in one log:
        #
        #   * it is slow — a dead host cost three DNS retries and held the
        #     request open for two seconds, long enough for a user to press
        #     the button again;
        #   * it is a server-side request forgery vector — `logo_url` is set
        #     by a user, so an internal address would be fetched from inside
        #     the network by a process holding our credentials;
        #   * it fails — a supplier's CDN going down should not degrade our
        #     ability to issue a purchase order.
        #
        # Documents therefore only ever draw images we hold. Anything else is
        # dropped, which renders a document without a logo rather than one
        # that hangs. The upload endpoint exists so nobody needs a remote URL.
        return ""

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


#: Any <img> whose source is a remote URL. Matched on the whole tag so it can
#: be removed rather than left with a broken src.
_REMOTE_IMAGE = re.compile(
    r"""<img[^>]*\ssrc\s*=\s*["']\s*https?://[^"']*["'][^>]*>""",
    re.IGNORECASE,
)


def strip_remote_images(html: str) -> str:
    """Remove images the renderer would have to go to the network for.

    Returning "" from ``link_callback`` is not enough: xhtml2pdf resolves an
    absolute http(s) source through its own file layer and never consults the
    callback, so the request is made regardless. The only reliable place to
    stop it is before the renderer sees the markup.

    Why stop it at all — one log showed all three failure modes at once. A dead
    host cost three DNS retries and held the request open for two seconds
    (long enough for the user to press the button again and get a 400 from the
    duplicate). ``logo_url`` is set by a user, so a remote fetch is a
    server-side request forgery vector pointed at our own network. And a
    supplier's CDN going down should never affect our ability to issue a
    purchase order.

    A document therefore only ever draws images we hold ourselves.
    """
    return _REMOTE_IMAGE.sub("", html)


def render_pdf(html: str) -> bytes:
    """Render an HTML string to PDF bytes."""
    html = strip_remote_images(html)
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
