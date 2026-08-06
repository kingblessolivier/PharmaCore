"""Catalog clinical tests: drug interactions, contraindications, WHO standards (DDD, essential)."""

from __future__ import annotations

import pytest
from apps.catalog.models import (
    ActiveIngredient,
    Product,
    ProductContraindication,
    ProductInteraction,
)
from apps.iam.models import AuditLog, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin(db: None) -> User:
    u = User.objects.create_user(username="clinical_admin", password="x")
    u.roles.add(Role.objects.get(code="SYS_ADMIN"))
    return u


@pytest.fixture
def clerk(db: None) -> User:
    return User.objects.create_user(username="pharm_clerk", password="x")


@pytest.fixture
def amoxicillin(db: None) -> Product:
    return Product.objects.create(
        generic_name="Amoxicillin",
        strength="500mg",
        ddd="1000mg/day",
        is_essential=True,
        rxnorm_id="308182",
    )


@pytest.mark.django_db
def test_who_clinical_standards_fields(clerk: User, amoxicillin: Product) -> None:
    resp = _auth(clerk).get(f"/api/catalog/products/{amoxicillin.pk}/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ddd"] == "1000mg/day"
    assert data["is_essential"] is True
    assert data["rxnorm_id"] == "308182"


@pytest.mark.django_db
def test_admin_creates_drug_interaction_audited(admin: User) -> None:
    ing_a = ActiveIngredient.objects.create(name="Warfarin")
    ing_b = ActiveIngredient.objects.create(name="Aspirin")
    resp = _auth(admin).post(
        "/api/catalog/product-interactions/",
        {
            "ingredient_a": ing_a.pk,
            "ingredient_b": ing_b.pk,
            "severity": "MAJOR",
            "effect": "Increased risk of severe bleeding",
            "management": "Avoid co-administration or monitor INR closely",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert ProductInteraction.objects.filter(severity="MAJOR").exists()
    assert AuditLog.objects.filter(action="CREATE", entity_type="product_interaction").exists()


@pytest.mark.django_db
def test_admin_creates_contraindication_audited(admin: User, amoxicillin: Product) -> None:
    resp = _auth(admin).post(
        "/api/catalog/product-contraindications/",
        {
            "product": amoxicillin.pk,
            "condition": "Severe Penicillin Allergy",
            "icd10_code": "Z88.0",
            "severity": "CONTRAINDICATED",
            "message": "Do not administer in patients with documented anaphylaxis to beta-lactams.",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert ProductContraindication.objects.filter(severity="CONTRAINDICATED").exists()
    assert AuditLog.objects.filter(action="CREATE", entity_type="product_contraindication").exists()
