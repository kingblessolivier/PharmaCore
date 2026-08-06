"""Shared fixtures for events-app tests (F1 scope)."""

from __future__ import annotations

import pytest

from apps.iam.models import Organization, User


@pytest.fixture
def organization(db):
    return Organization.objects.create(
        name="Acme Pharmacy Ltd",
        type=Organization.OrgType.RETAIL,
        currency="RWF",
    )


@pytest.fixture
def user(db, organization):
    return User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="testpass123!",
        organization=organization,
    )
