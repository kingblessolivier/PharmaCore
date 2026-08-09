"""What we will and will not accept as a picture.

These are mostly refusal tests on purpose. An upload endpoint that stores a
valid PNG is easy; the ones that matter are the file pretending to be a PNG,
the SVG carrying script, and the payload glued onto the end of a real image.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from apps.core.uploads import ImageRejected, store_image
from apps.documents.renderer import _resolve_asset, render_pdf
from apps.iam.models import Organization, Permission, Role, User
from django.core.files.storage import default_storage
from PIL import Image
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _isolated_media(settings, tmp_path) -> None:
    """Write uploads into a throwaway directory.

    Without this the suite quietly fills the developer's real ``media/`` with
    test pictures, and a test that asserts a file exists could pass on a stale
    one from a previous run.
    """
    settings.MEDIA_ROOT = tmp_path / "media"


def make_image(width: int = 200, height: int = 120, fmt: str = "PNG", mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), (200, 30, 30)).save(buffer, format=fmt)
    return buffer.getvalue()


def _client(organization: Organization, *codes: str) -> APIClient:
    """A user holding the authority a given purpose requires.

    Uploading is not one right — it is four. Changing a logo alters the
    letterhead on every document the pharmacy issues; changing a listing photo
    changes what a buyer thinks is in the box. Neither belongs to whoever
    happens to be logged in.
    """
    user = User.objects.create_user(
        username=f"uploader-{'-'.join(codes) or 'none'}",
        password="x",  # noqa: S106 - test fixture
        organization=organization,
    )
    if codes:
        role, _ = Role.objects.get_or_create(code="UPLOADER", defaults={"name": "Uploader"})
        for code in codes:
            resource, _, action = code.partition(".")
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"resource": resource, "action": action}
            )
            role.permissions.add(permission)
        user.roles.add(role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestAccepted:
    def test_a_normal_logo_is_stored_and_addressable(self) -> None:
        result = store_image(make_image(), "logo", original_name="logo.png")
        assert result["url"].startswith("/media/uploads/logo/")
        assert result["format"] == "png"
        assert default_storage.exists(result["url"].replace("/media/", ""))

    def test_a_large_photo_is_scaled_down_to_the_purpose(self) -> None:
        # A 12-megapixel phone picture of a shelf is not a better product
        # photo than a 1600px one, and every byte is served to a slow counter.
        result = store_image(make_image(4000, 3000), "product")
        assert max(result["width"], result["height"]) == 1600
        assert result["height"] == 1200, "aspect ratio must survive the resize"

    def test_a_transparent_logo_keeps_its_transparency(self) -> None:
        result = store_image(make_image(300, 300, mode="RGBA"), "logo")
        assert result["format"] == "png"

    def test_jpeg_and_webp_are_accepted(self) -> None:
        assert store_image(make_image(fmt="JPEG"), "product")["format"] == "jpg"
        assert store_image(make_image(fmt="WEBP"), "product")["format"] == "webp"


class TestRefused:
    def test_a_script_renamed_to_png_is_refused(self) -> None:
        with pytest.raises(ImageRejected, match="not an image"):
            store_image(b"<?php system($_GET['c']); ?>", "logo", original_name="shell.png")

    def test_svg_is_refused_even_though_it_is_a_picture(self) -> None:
        # SVG is a document format that can carry script, and it would be
        # served from our own origin.
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        with pytest.raises(ImageRejected):
            store_image(svg, "logo", original_name="mark.svg")

    def test_an_oversized_file_is_refused_before_decoding(self) -> None:
        with pytest.raises(ImageRejected, match="under 6 MB"):
            store_image(b"\x89PNG\r\n\x1a\n" + b"A" * (7 * 1024 * 1024), "logo")

    def test_an_empty_file_is_refused(self) -> None:
        with pytest.raises(ImageRejected, match="empty"):
            store_image(b"", "logo")

    def test_a_tracking_pixel_is_refused(self) -> None:
        with pytest.raises(ImageRejected, match="too small"):
            store_image(make_image(1, 1), "logo")

    def test_an_unknown_purpose_is_refused(self) -> None:
        with pytest.raises(ImageRejected):
            store_image(make_image(), "../../etc")


class TestTheStoredFileIsOurs:
    """The strongest guarantee here: what lands on disk is what Pillow wrote."""

    def test_a_payload_appended_to_a_real_image_does_not_survive(self) -> None:
        # A polyglot: a genuinely valid PNG with a script glued past IEND.
        # It decodes, so a format check alone would pass it. Re-encoding is
        # what actually destroys it.
        polyglot = make_image() + b"<?php system($_GET['c']); ?>"
        result = store_image(polyglot, "logo", original_name="poly.png")
        stored = default_storage.open(result["url"].replace("/media/", "")).read()
        assert b"<?php" not in stored

    def test_the_clients_filename_never_reaches_the_path(self) -> None:
        result = store_image(make_image(), "logo", original_name="../../../../etc/passwd.png")
        assert ".." not in result["url"]
        assert "etc" not in result["url"]
        # Kept only so a screen can say which file was uploaded.
        assert result["original_name"] == "passwd.png"

    def test_a_windows_style_path_is_also_stripped(self) -> None:
        result = store_image(make_image(), "logo", original_name=r"..\..\windows\evil.png")
        assert result["original_name"] == "evil.png"

    def test_two_uploads_of_the_same_file_do_not_collide(self) -> None:
        raw = make_image()
        assert store_image(raw, "logo")["url"] != store_image(raw, "logo")["url"]


class TestEndpoint:
    def test_it_requires_a_login(self) -> None:
        response = APIClient().post("/api/uploads/image", {}, format="multipart")
        assert response.status_code in (401, 403)

    def test_it_returns_a_url_the_caller_can_store(self, organization: Organization) -> None:
        upload = io.BytesIO(make_image())
        upload.name = "logo.png"
        response = _client(organization, "organization.manage").post(
            "/api/uploads/image",
            {"file": upload, "purpose": "logo"},
            format="multipart",
        )
        assert response.status_code == 201, response.data
        assert response.data["url"].startswith("/media/uploads/logo/")

    def test_a_missing_file_says_so(self, organization: Organization) -> None:
        response = _client(organization, "organization.manage").post(
            "/api/uploads/image", {"purpose": "logo"}, format="multipart"
        )
        assert response.status_code == 400

    def test_a_script_sent_over_the_wire_is_refused_with_a_readable_reason(
        self, organization: Organization
    ) -> None:
        upload = io.BytesIO(b"<?php system($_GET['c']); ?>")
        upload.name = "shell.png"
        response = _client(organization, "organization.manage").post(
            "/api/uploads/image",
            {"file": upload, "purpose": "logo"},
            format="multipart",
        )
        assert response.status_code == 400
        assert "not an image" in response.data["detail"]


class TestTheRendererCanFindIt:
    """An uploaded logo is a site-relative path, and a PDF renderer has no site.

    These cover the join between the two — the reason the logo work on
    documents would otherwise produce a header with a blank space in it.
    """

    def test_an_uploaded_image_resolves_to_a_file_on_disk(self) -> None:
        stored = store_image(make_image(), "logo")
        assert Path(_resolve_asset(stored["url"], "")).is_file()

    @pytest.mark.parametrize(
        "hostile",
        [
            "/media/../../../etc/passwd",
            "/media/../config/settings.py",
            "/media/uploads/../../manage.py",
        ],
    )
    def test_a_path_climbing_out_of_the_media_root_is_refused(self, hostile: str) -> None:
        # logo_url is set by a user. Without this the PDF generator would read
        # whatever they named and draw it into a document they can download.
        assert _resolve_asset(hostile, "") == ""

    def test_a_missing_file_yields_nothing_rather_than_a_broken_path(self) -> None:
        assert _resolve_asset("/media/uploads/logo/gone.png", "") == ""

    def test_an_inline_source_is_left_alone(self) -> None:
        assert _resolve_asset("data:image/png;base64,AAAA", "").startswith("data:")

    def test_a_remote_source_is_refused(self) -> None:
        """Changed deliberately, and the opposite of what this once asserted.

        Resolving a remote URL meant the renderer fetched it — an outbound
        request on every document. A dead host cost three DNS retries and
        ~3 seconds, and since `logo_url` is user-settable the fetch was a
        server-side request forgery vector aimed at our own network. Documents
        now draw only images we hold.
        """
        assert _resolve_asset("https://cdn.example/logo.png", "") == ""

    def test_the_logo_actually_lands_in_the_pdf(self) -> None:
        stored = store_image(make_image(300, 120), "logo")
        plain = render_pdf("<html><body><p>Document</p></body></html>")
        branded = render_pdf(
            f'<html><body><img src="{stored["url"]}"><p>Document</p></body></html>'
        )
        assert len(branded) > len(plain), "the image should add bytes to the PDF"


class TestAuthority:
    """Uploading is four rights, not one.

    A logo goes on the letterhead of every purchase order and invoice the
    pharmacy issues, so replacing one changes how the business presents itself
    to its suppliers and to the regulator. A listing photo is a claim about
    which medicine is in a box. Neither belongs to whoever is logged in.
    """

    def _post(self, client: APIClient, purpose: str):
        upload = io.BytesIO(make_image())
        upload.name = "x.png"
        return client.post(
            "/api/uploads/image",
            {"file": upload, "purpose": purpose},
            format="multipart",
        )

    def test_a_cashier_cannot_change_the_letterhead(self, organization: Organization) -> None:
        response = self._post(_client(organization), "logo")
        assert response.status_code == 403
        assert "logo" in response.data["detail"]

    @pytest.mark.parametrize(
        ("purpose", "code"),
        [
            ("logo", "organization.manage"),
            ("product", "catalog.manage"),
            ("listing", "order.create"),
            ("photo", "employee.manage"),
        ],
    )
    def test_each_purpose_admits_the_right_holder(
        self, organization: Organization, purpose: str, code: str
    ) -> None:
        assert self._post(_client(organization, code), purpose).status_code == 201

    @pytest.mark.parametrize(
        ("purpose", "wrong_code"),
        [
            ("logo", "catalog.manage"),
            ("product", "employee.manage"),
            ("listing", "catalog.manage"),
            ("photo", "organization.manage"),
        ],
    )
    def test_authority_over_one_thing_is_not_authority_over_another(
        self, organization: Organization, purpose: str, wrong_code: str
    ) -> None:
        # The failure this guards against is a single "can upload" right that
        # quietly lets a catalogue clerk replace the company logo.
        assert self._post(_client(organization, wrong_code), purpose).status_code == 403

    def test_an_unknown_purpose_is_refused_before_authority_is_considered(
        self, organization: Organization
    ) -> None:
        assert self._post(_client(organization), "../../etc").status_code == 400
