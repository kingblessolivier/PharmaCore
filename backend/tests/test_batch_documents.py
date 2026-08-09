"""Paperwork that belongs to a lot, not to a party.

The system held compliance documents for organizations, users and suppliers and
none at all for the things they trade — but a Certificate of Analysis is issued
for a specific batch, and "we hold a GMP certificate for the manufacturer" is
not an answer to "show me the CoA for this one" at an inspection.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.iam.models import Organization, User
from apps.inventory.models import BatchDocument, InventoryBatch, missing_batch_documents
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

URL = "/api/inventory/batch-documents/"


@pytest.fixture
def org():
    return Organization.objects.create(name="Kigali Depot", type="DEPOT")


@pytest.fixture
def keeper(org):
    return User.objects.create_superuser(username="keeper", password="pw", organization=org)


@pytest.fixture
def client(keeper):
    api = APIClient()
    api.force_authenticate(user=keeper)
    return api


@pytest.fixture
def batch(org):
    product = Product.objects.create(generic_name="Amoxicillin", dosage_form="CAPSULE")
    return InventoryBatch.objects.create(
        organization=org,
        product=product,
        batch_number="LOT-42",
        expiry_date=timezone.localdate() + timedelta(days=365),
        quantity_available=Decimal("500"),
        status=InventoryBatch.Status.QUARANTINE,
    )


def test_a_lot_with_no_paperwork_reports_what_it_is_missing(batch):
    assert missing_batch_documents(batch) == ["Certificate of Analysis"]


def test_an_unverified_upload_does_not_count(batch, keeper):
    """Attaching a file is not the same as checking it is the right file."""
    BatchDocument.objects.create(
        batch=batch,
        doc_type=BatchDocument.DocType.CERTIFICATE_OF_ANALYSIS,
        document_url="https://example.test/coa.pdf",
        uploaded_by=keeper,
    )
    assert missing_batch_documents(batch) == ["Certificate of Analysis"]


def test_a_verified_certificate_closes_the_gap(batch, keeper):
    BatchDocument.objects.create(
        batch=batch,
        doc_type=BatchDocument.DocType.CERTIFICATE_OF_ANALYSIS,
        document_url="https://example.test/coa.pdf",
        is_verified=True,
        verified_by=keeper,
    )
    assert missing_batch_documents(batch) == []


def test_a_lot_cannot_hold_two_certificates_of_analysis(batch):
    """Two CoAs is a lot where nobody can say which one is current."""
    from django.db.utils import IntegrityError

    BatchDocument.objects.create(
        batch=batch, doc_type=BatchDocument.DocType.CERTIFICATE_OF_ANALYSIS
    )
    with pytest.raises(IntegrityError):
        BatchDocument.objects.create(
            batch=batch, doc_type=BatchDocument.DocType.CERTIFICATE_OF_ANALYSIS
        )


def test_several_other_documents_are_allowed(batch):
    """'Other' is the escape hatch and must not be limited to one."""
    for n in range(3):
        BatchDocument.objects.create(
            batch=batch, doc_type=BatchDocument.DocType.OTHER, document_number=f"D{n}"
        )
    assert batch.documents.filter(doc_type="OTHER").count() == 3


# ---------------------------------------------------------------------------
# Over HTTP
# ---------------------------------------------------------------------------


def test_a_document_can_be_attached_to_a_lot(client, batch):
    resp = client.post(
        URL,
        {
            "batch": batch.pk,
            "doc_type": "COA",
            "document_number": "COA-2026-118",
            "document_url": "https://example.test/coa.pdf",
            "issued_by": "Cipla QA",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["doc_type_display"] == "Certificate of Analysis"
    assert batch.documents.count() == 1


def test_verifying_is_a_separate_act_from_uploading(client, batch, keeper):
    document = BatchDocument.objects.create(
        batch=batch, doc_type=BatchDocument.DocType.CERTIFICATE_OF_ANALYSIS
    )
    assert document.is_verified is False

    resp = client.post(f"{URL}{document.pk}/verify/")
    assert resp.status_code == 200, resp.content

    document.refresh_from_db()
    assert document.is_verified is True
    assert document.verified_by == keeper
    assert document.verified_at is not None


def test_documents_are_listed_for_one_lot(client, batch, org):
    other = InventoryBatch.objects.create(
        organization=org,
        product=batch.product,
        batch_number="LOT-99",
        expiry_date=timezone.localdate() + timedelta(days=200),
        quantity_available=Decimal("10"),
    )
    BatchDocument.objects.create(batch=batch, doc_type="COA")
    BatchDocument.objects.create(batch=other, doc_type="COA")

    rows = client.get(f"{URL}?batch={batch.pk}").json()
    results = rows["results"] if isinstance(rows, dict) else rows
    assert len(results) == 1
    assert results[0]["batch_number"] == "LOT-42"


def test_a_lot_in_another_organization_is_not_visible(batch):
    """Paperwork is as org-scoped as the stock it describes."""
    outsider_org = Organization.objects.create(name="Elsewhere", type="RETAIL")
    outsider = User.objects.create_user(
        username="outsider", password="pw", organization=outsider_org
    )
    BatchDocument.objects.create(batch=batch, doc_type="COA")

    api = APIClient()
    api.force_authenticate(user=outsider)
    rows = api.get(URL).json()
    results = rows["results"] if isinstance(rows, dict) else rows
    assert results == []
