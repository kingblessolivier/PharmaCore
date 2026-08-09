"""Accepting an image from a user.

Five fields in this system hold a picture — a company logo, an organization
logo, a product photograph, a depot's listing photo, and an employee's badge —
and until now every one of them was a URL the user had to produce somewhere
else first. A pharmacist in Musanze does not have a CDN. So the fields existed,
the documents and storefronts read them, and in practice they stayed empty.

This is the one place a file becomes a URL. Three rules make that safe:

1. **The bytes are decoded, not sniffed.** A content-type header is a claim by
   the sender. Pillow opening the file is a fact.
2. **The stored file is one we wrote.** Every upload is re-encoded, so what
   lands on disk is Pillow's output, not the caller's input. That strips EXIF
   (which carries GPS off a phone camera) and destroys anything appended past
   the image data to make a polyglot file.
3. **The name is ours.** The client's filename is never used for the path —
   it is the classic route to traversal — only recorded for display.

SVG is deliberately not accepted. It is a document format that can carry
script, and it would be served from our own origin.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Final

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, UnidentifiedImageError
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

#: What a caller says the picture is for. It only selects the folder and the
#: size cap — it grants nothing, so an unknown value is simply rejected rather
#: than trusted.
PURPOSES: Final[dict[str, int]] = {
    "logo": 800,  # letterhead marks; 800px is generous at print resolution
    "product": 1600,
    "listing": 1600,
    "photo": 1024,  # employee badge
}

#: Formats we will decode and re-encode. Anything else is refused by name so
#: the caller learns why rather than seeing a generic failure.
ALLOWED_FORMATS: Final[dict[str, str]] = {
    "PNG": "png",
    "JPEG": "jpg",
    "WEBP": "webp",
}

MAX_UPLOAD_BYTES: Final = 6 * 1024 * 1024

#: A guard against decompression bombs: a small file can declare an enormous
#: canvas, and allocating it is the attack. Checked from the header before any
#: pixel is read.
MAX_PIXELS: Final = 50_000_000


class ImageRejected(Exception):
    """The upload is not something we are willing to store."""


def _open_verified(raw: bytes) -> Image.Image:
    """Decode the bytes, or refuse them.

    Pillow wants ``verify()`` on a fresh handle and will not let you use the
    image afterwards, so the file is opened twice: once to check integrity,
    once to actually work with.
    """
    try:
        probe = Image.open(BytesIO(raw))
        probe.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageRejected("That file is not an image we can read.") from exc

    fmt = (probe.format or "").upper()
    if fmt not in ALLOWED_FORMATS:
        allowed = ", ".join(sorted(ALLOWED_FORMATS))
        raise ImageRejected(f"{fmt or 'That format'} is not accepted. Use {allowed}.")

    image = Image.open(BytesIO(raw))
    width, height = image.size
    if width * height > MAX_PIXELS:
        raise ImageRejected("That image's dimensions are too large to process.")
    if width < 8 or height < 8:
        raise ImageRejected("That image is too small to be a picture of anything.")
    return image


def _flatten(image: Image.Image, fmt: str) -> Image.Image:
    """Put the image into a colour mode the target format can actually store.

    A CMYK scan or a palette PNG will not save as JPEG, and transparency has
    nowhere to go in one either — so a transparent logo is laid on white
    rather than saved with a black box behind it.
    """
    if fmt == "JPEG":
        if image.mode in ("RGBA", "LA", "P"):
            rgba = image.convert("RGBA")
            backdrop = Image.new("RGB", rgba.size, (255, 255, 255))
            backdrop.paste(rgba, mask=rgba.split()[-1])
            return backdrop
        if image.mode != "RGB":
            return image.convert("RGB")
        return image
    if image.mode == "P":
        return image.convert("RGBA")
    return image


def store_image(raw: bytes, purpose: str, *, original_name: str = "") -> dict[str, Any]:
    """Validate, re-encode and save one image. Returns what the caller stores.

    Raises :class:`ImageRejected` with a sentence fit to show a user.
    """
    if purpose not in PURPOSES:
        raise ImageRejected("That is not something an image can be uploaded for.")
    if not raw:
        raise ImageRejected("That file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ImageRejected(f"Images must be under {mb} MB.")

    image = _open_verified(raw)
    fmt = (image.format or "PNG").upper()

    # Shrink to what the purpose needs. A 12-megapixel phone photo of a shelf
    # is not more useful as a product picture than a 1600px one, and every
    # byte of it is served to a counter on a slow connection.
    edge = PURPOSES[purpose]
    image = _flatten(image, fmt)
    if max(image.size) > edge:
        image.thumbnail((edge, edge), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    save_options: dict[str, Any] = {"optimize": True}
    if fmt == "JPEG":
        save_options["quality"] = 85
        save_options["progressive"] = True
    elif fmt == "WEBP":
        save_options["quality"] = 88
    image.save(buffer, format=fmt, **save_options)
    encoded = buffer.getvalue()

    now = datetime.now(UTC)
    name = f"{uuid.uuid4().hex}.{ALLOWED_FORMATS[fmt]}"
    path = f"uploads/{purpose}/{now:%Y/%m}/{name}"
    saved = default_storage.save(path, ContentFile(encoded))

    return {
        "url": default_storage.url(saved),
        "width": image.width,
        "height": image.height,
        "bytes": len(encoded),
        "format": ALLOWED_FORMATS[fmt],
        # Kept only so a screen can say "logo.png uploaded" — never used to
        # build a path. PurePosixPath().name strips any directory the caller
        # tried to smuggle in.
        "original_name": PurePosixPath(original_name.replace("\\", "/")).name[:120],
    }


class ImageUploadView(APIView):
    """POST an image, get back a URL to store on whatever record needs it.

    Deliberately not tied to a model. The alternative — an upload endpoint per
    field — would mean five copies of the validation above, and the fifth one
    would be the one that forgot to re-encode.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"detail": "Attach the image as 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Read through the size cap rather than trusting upload.size, which is
        # a declared Content-Length.
        raw = upload.read(MAX_UPLOAD_BYTES + 1)
        try:
            stored = store_image(
                raw,
                str(request.data.get("purpose") or "product"),
                original_name=getattr(upload, "name", "") or "",
            )
        except ImageRejected as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(stored, status=status.HTTP_201_CREATED)
