"""Base RBAC: role seeding and the HasRole permission class."""

from __future__ import annotations

import pytest
from apps.iam.models import Role, User
from apps.iam.permissions import HasRole


@pytest.mark.django_db
def test_base_roles_seeded() -> None:
    # Seeded by migration 0002.
    assert Role.objects.filter(code="SYS_ADMIN").exists()
    assert Role.objects.count() >= 10


@pytest.mark.django_db
def test_has_role_denies_without_role() -> None:
    user = User.objects.create_user(username="bob", password="x")
    assert user.has_role("PHARMACIST") is False


@pytest.mark.django_db
def test_has_role_allows_with_role() -> None:
    user = User.objects.create_user(username="carol", password="x")
    user.roles.add(Role.objects.get(code="PHARMACIST"))
    assert user.has_role("PHARMACIST") is True


@pytest.mark.django_db
def test_has_role_factory_builds_class() -> None:
    perm_cls = HasRole.require("CASHIER")
    assert issubclass(perm_cls, HasRole)
    assert perm_cls.required_role == "CASHIER"
