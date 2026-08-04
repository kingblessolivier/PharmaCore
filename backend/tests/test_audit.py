"""AuditLog is append-only (GDP immutability)."""

from __future__ import annotations

import pytest
from apps.iam.audit import record_audit
from apps.iam.models import AuditLog


@pytest.mark.django_db
def test_record_audit_creates_entry() -> None:
    entry = record_audit(action="TEST", entity_type="thing", entity_id="42")
    assert entry.pk is not None
    assert AuditLog.objects.filter(action="TEST", entity_id="42").exists()


@pytest.mark.django_db
def test_audit_cannot_be_updated() -> None:
    entry = record_audit(action="TEST")
    entry.action = "TAMPERED"
    with pytest.raises(ValueError, match="append-only"):
        entry.save()


@pytest.mark.django_db
def test_audit_cannot_be_deleted() -> None:
    entry = record_audit(action="TEST")
    with pytest.raises(ValueError, match="append-only"):
        entry.delete()
