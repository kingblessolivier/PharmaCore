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


#: A table cell with nothing in it — no text, only whitespace or comments.
#: Written with String-safe raw strings and proved by the self-test in
#: tests/test_document_layout.py, not by reading.
_EMPTY_CELL = re.compile(r"(<(t[dh])\b[^>]*>)(\s*)(</\2>)", re.IGNORECASE)


def fill_empty_cells(html: str) -> str:
    """Put a non-breaking space in every empty table cell.

    xhtml2pdf collapses a column containing an empty cell to zero width, and
    takes the neighbouring columns down with it. On a journal voucher — where a
    debit line has no credit and a credit line has no debit, so an empty cell is
    not an edge case but the normal shape of a ledger — the Debit and Credit
    columns ended up ten points apart, printing the two figures on top of each
    other: "7,5060.00". The same collapse merged "Delivered by" and "Received
    by" on every goods receipt where the driver's name had not been typed in.

    I first blamed this on declared column widths summing to 100%, which is a
    real constraint of this renderer but was not the cause: a seven-column table
    at 100% renders correctly, and the same table with one empty middle cell
    does not. Filling that one cell fixes it.

    The fix belongs here rather than in fifteen templates. A template author
    cannot reasonably be expected to know that ``{{ line.credit }}`` resolving
    to "" destroys the layout of the whole table, and every template that gets
    written later would have to remember.
    """
    return _EMPTY_CELL.sub(r"\1&nbsp;\4", html)


def render_pdf(html: str) -> bytes:
    """Render an HTML string to PDF bytes."""
    html = fill_empty_cells(strip_remote_images(html))
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
