"""The photograph on a listing, and who vouches for it.

A picture on a storefront is a claim about which medicine is in the box. The
model has always known that — it keeps who verified a photo and when, and drops
that the moment the photo changes — but nothing exposed it, so every listing
photo was unverifiable and every buyer was trusting an unchecked image.

These pin the rule the whole design rests on: **verification belongs to the
image, not to the row.**
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.distribution import marketplace
from apps.distribution.models import DepotProductListing
from apps.iam.models import Organization, Permission, Role, User
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def depot() -> Organization:
    return Organization.objects.create(name="Kigali Depot", type="DEPOT")


@pytest.fixture
def product() -> Product:
    return Product.objects.create(generic_name="Amoxicillin 500mg", brand_name="Amoxil")


@pytest.fixture
def listing(depot: Organization, product: Product) -> DepotProductListing:
    return marketplace.publish(
        depot=depot,
        product=product,
        offered_qty=100,
        price_per_unit=Decimal("250.00"),
        image_url="/media/uploads/listing/2026/08/photo.png",
    )


def _staff(depot: Organization) -> APIClient:
    """Somebody at this depot with authority over its orders."""
    user = User.objects.create_user(
        username=f"manager-{depot.pk}",
        password="x",  # noqa: S106 - test fixture
        organization=depot,
    )
    role, _ = Role.objects.get_or_create(code="DEPOT_MANAGER", defaults={"name": "Depot manager"})
    permission, _ = Permission.objects.get_or_create(
        code="order.create", defaults={"resource": "order", "action": "create"}
    )
    role.permissions.add(permission)
    user.roles.add(role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestPublishing:
    def test_a_photo_can_be_attached_when_publishing(self, listing: DepotProductListing) -> None:
        assert listing.image_url.endswith("photo.png")

    def test_a_new_photo_arrives_untrusted(self, listing: DepotProductListing) -> None:
        # The whole point. An unverified picture must never be presentable as
        # verified simply because it exists.
        assert listing.image_is_trusted is False

    def test_an_order_multiple_can_be_set(self, depot: Organization, product: Product) -> None:
        updated = marketplace.publish(
            depot=depot,
            product=product,
            offered_qty=100,
            price_per_unit=Decimal("250.00"),
            order_multiple=24,
        )
        assert updated.order_multiple == 24

    def test_editing_a_price_does_not_disturb_the_photo(
        self, depot: Organization, product: Product, listing: DepotProductListing
    ) -> None:
        # `image_url=None` means "leave it alone". If publish() overwrote the
        # photo with a blank on every edit, changing a price would silently
        # strip the picture — and, worse, drop a verification that had been
        # given.
        listing.image_verified_by = User.objects.create_user(
            username="checker",
            password="x",  # noqa: S106 - test fixture
        )
        listing.image_verified_at = timezone.now()
        listing.save()

        marketplace.publish(
            depot=depot,
            product=product,
            offered_qty=100,
            price_per_unit=Decimal("999.00"),
        )
        listing.refresh_from_db()
        assert listing.image_url.endswith("photo.png")
        assert listing.image_is_trusted is True


class TestVerifying:
    def test_confirming_marks_it_trusted_and_records_who(
        self, depot: Organization, listing: DepotProductListing
    ) -> None:
        response = _staff(depot).post(
            f"/api/distribution/listings/{listing.id}/verify-image/",
            {"confirmed": True},
            format="json",
        )
        assert response.status_code == 200, response.data
        listing.refresh_from_db()
        assert listing.image_is_trusted is True
        assert listing.image_verified_by is not None
        assert listing.image_verified_at is not None

    def test_rejecting_removes_the_photo(
        self, depot: Organization, listing: DepotProductListing
    ) -> None:
        # A photo somebody has looked at and judged wrong is the most dangerous
        # kind: leaving it up sells the wrong medicine to a buyer who trusted
        # the picture. Rejection has to take it down, not just withhold a tick.
        response = _staff(depot).post(
            f"/api/distribution/listings/{listing.id}/verify-image/",
            {"confirmed": False},
            format="json",
        )
        assert response.status_code == 200
        listing.refresh_from_db()
        assert listing.image_url == ""
        assert listing.image_is_trusted is False

    def test_there_is_nothing_to_verify_without_a_photo(
        self, depot: Organization, product: Product
    ) -> None:
        bare = marketplace.publish(
            depot=depot, product=product, offered_qty=5, price_per_unit=Decimal("1.00")
        )
        response = _staff(depot).post(
            f"/api/distribution/listings/{bare.id}/verify-image/",
            {"confirmed": True},
            format="json",
        )
        assert response.status_code == 400

    def test_another_depot_cannot_vouch_for_this_photo(self, listing: DepotProductListing) -> None:
        other = Organization.objects.create(name="Rival Depot", type="DEPOT")
        response = _staff(other).post(
            f"/api/distribution/listings/{listing.id}/verify-image/",
            {"confirmed": True},
            format="json",
        )
        assert response.status_code in (403, 404)
        listing.refresh_from_db()
        assert listing.image_is_trusted is False


class TestVerificationBelongsToTheImage:
    def test_swapping_the_photo_drops_the_tick(
        self, depot: Organization, listing: DepotProductListing
    ) -> None:
        """The rule the design rests on.

        Otherwise the check is a one-off: verify a correct picture once, swap
        it for anything at all afterwards, and the tick stays — which is
        exactly the loophole a verification step exists to close.
        """
        _staff(depot).post(
            f"/api/distribution/listings/{listing.id}/verify-image/",
            {"confirmed": True},
            format="json",
        )
        listing.refresh_from_db()
        assert listing.image_is_trusted is True

        listing.image_url = "/media/uploads/listing/2026/08/different.png"
        listing.save()
        listing.refresh_from_db()
        assert listing.image_is_trusted is False
        assert listing.image_verified_by is None

    def test_republishing_with_a_new_photo_also_drops_it(
        self, depot: Organization, product: Product, listing: DepotProductListing
    ) -> None:
        _staff(depot).post(
            f"/api/distribution/listings/{listing.id}/verify-image/",
            {"confirmed": True},
            format="json",
        )
        marketplace.publish(
            depot=depot,
            product=product,
            offered_qty=100,
            price_per_unit=Decimal("250.00"),
            image_url="/media/uploads/listing/2026/08/swapped.png",
        )
        listing.refresh_from_db()
        assert listing.image_is_trusted is False
