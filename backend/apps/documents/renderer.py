"""PDF rendering + QR helpers.

Uses xhtml2pdf (pure-Python, no native deps → works on Windows dev and CI). The
render function is the single swap point: WeasyPrint can replace it in production
for higher-fidelity CSS without touching callers.
"""

from __future__ import annotations

import base64
import io

import segno
from xhtml2pdf import pisa


def render_pdf(html: str) -> bytes:
    """Render an HTML string to PDF bytes."""
    out = io.BytesIO()
    result = pisa.CreatePDF(src=html, dest=out, encoding="utf-8")
    if result.err:
        raise RuntimeError("PDF rendering failed")
    return out.getvalue()


def qr_data_uri(data: str) -> str:
    """Return a base64 PNG data URI for a QR code encoding ``data``."""
    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="png", scale=3, border=2)
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"
