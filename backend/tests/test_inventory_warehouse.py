from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.iam.models import Organization, Role, User
from apps.inventory.models import (
    BatchRecall,
    InventoryBatch,
    QualityCheck,
    StockCount,
    StockCountItem,
    StockDisposal,
    StockMovement,
    StorageZone,
)
from rest_framework import status
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def test_data(db):
    org = Organization.objects.create(name="Depot Central HQ", type="DEPOT")
    user = User.objects.create_user(
        username="wh_manager", email="wh@medlink.rw", password="Password123!"
    )
    user.organization = org
    sys_admin = Role.objects.get(code="SYS_ADMIN")
    user.roles.add(sys_admin)
    user.save()

    product = Product.objects.create(
        generic_name="Amoxicillin",
        dosage_form="Capsule",
        strength="500mg",
        requires_prescription=True,
    )
    batch = InventoryBatch.objects.create(
        organization=org,
        product=product,
        batch_number="BAT-2026-001",
        expiry_date=date(2027, 12, 31),
        quantity_available=100,
        status=InventoryBatch.Status.ACTIVE,
    )
    return {"org": org, "user": user, "product": product, "batch": batch}


@pytest.mark.django_db
def test_storage_zones_and_bin_locations(test_data):
    client = _auth(test_data["user"])
    org = test_data["org"]

    # 1. Create Storage Zone
    res = client.post(
        "/api/inventory/storage-zones/",
        {
            "organization": org.id,
            "name": "Cold Room Alpha",
            "zone_type": "COLD_CHAIN",
            "temp_min_celsius": "2.00",
            "temp_max_celsius": "8.00",
        },
        format="json",
    )
    assert res.status_code == status.HTTP_201_CREATED
    zone_id = res.data["id"]

    # 2. Create Bin Location
    res2 = client.post(
        "/api/inventory/bin-locations/",
        {
            "zone": zone_id,
            "aisle": "Aisle 1",
            "shelf": "Shelf B",
            "bin_code": "CR-A01-SB-B03",
        },
        format="json",
    )
    assert res2.status_code == status.HTTP_201_CREATED
    assert res2.data["bin_code"] == "CR-A01-SB-B03"


@pytest.mark.django_db
def test_temperature_logging_and_sensors(test_data):
    client = _auth(test_data["user"])
    org = test_data["org"]

    zone = StorageZone.objects.create(organization=org, name="Ambient Vault", zone_type="AMBIENT")

    # Create Sensor
    res_sensor = client.post(
        "/api/inventory/temp-sensors/",
        {
            "organization": org.id,
            "zone": zone.id,
            "device_id": "SENS-9901",
            "name": "Ambient Sensor #1",
        },
        format="json",
    )
    assert res_sensor.status_code == status.HTTP_201_CREATED
    sensor_id = res_sensor.data["id"]

    # Log Reading
    res_log = client.post(
        "/api/inventory/temp-logs/",
        {
            "sensor": sensor_id,
            "temperature_celsius": "21.50",
            "humidity_percent": "45.00",
            "excursion_status": "NORMAL",
        },
        format="json",
    )
    assert res_log.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_quality_check_pass_and_fail_workflow(test_data):
    """Release and rejection, each by someone other than the inspector.

    This test previously used one user as both inspector and decider, decided the
    same check twice, and rejected with no reason. All three are now refused, so
    it exercises two checks and a second signatory instead.
    """
    org = test_data["org"]
    inspector = test_data["user"]
    batch = test_data["batch"]

    decider = User.objects.create_user(
        username="qa_lead", password="Password123!", organization=org
    )
    decider.roles.add(Role.objects.get(code="SYS_ADMIN"))
    client = _auth(decider)

    passing = QualityCheck.objects.create(
        batch=batch,
        inspector=inspector,
        status=QualityCheck.Status.PENDING_REVIEW,
        visual_integrity_ok=True,
    )
    res_pass = client.post(f"/api/inventory/quality-checks/{passing.id}/pass_qc/")
    assert res_pass.status_code == status.HTTP_200_OK, res_pass.content
    batch.refresh_from_db()
    assert batch.status == InventoryBatch.Status.ACTIVE

    failing = QualityCheck.objects.create(
        batch=batch, inspector=inspector, status=QualityCheck.Status.PENDING_REVIEW
    )
    res_fail = client.post(
        f"/api/inventory/quality-checks/{failing.id}/fail_qc/",
        {"reason": "Seal compromised on two cartons"},
        format="json",
    )
    assert res_fail.status_code == status.HTTP_200_OK, res_fail.content
    batch.refresh_from_db()
    assert batch.status == InventoryBatch.Status.QUARANTINE


@pytest.mark.django_db
def test_quality_decision_needs_a_second_person_and_a_reason(test_data):
    """The two controls the old workflow lacked."""
    batch = test_data["batch"]
    inspector = test_data["user"]
    client = _auth(inspector)

    check = QualityCheck.objects.create(
        batch=batch, inspector=inspector, status=QualityCheck.Status.PENDING_REVIEW
    )
    own = client.post(f"/api/inventory/quality-checks/{check.id}/pass_qc/")
    assert own.status_code == status.HTTP_400_BAD_REQUEST
    assert "second pair of eyes" in str(own.content)

    other = User.objects.create_user(
        username="qa_other", password="Password123!", organization=test_data["org"]
    )
    other.roles.add(Role.objects.get(code="SYS_ADMIN"))
    blank = _auth(other).post(f"/api/inventory/quality-checks/{check.id}/fail_qc/")
    assert blank.status_code == status.HTTP_400_BAD_REQUEST
    assert "say why" in str(blank.content)


@pytest.mark.django_db
def test_emergency_batch_recall_freeze(test_data):
    user = test_data["user"]
    product = test_data["product"]
    batch = test_data["batch"]
    client = _auth(user)

    recall = BatchRecall.objects.create(
        recall_reference="REC-2026-999",
        product=product,
        batch_number=batch.batch_number,
        reason="Suspected potency defect from manufacturer",
    )

    # Freezing now reports where the batch went, not just how many rows moved:
    # the count of frozen batches says nothing about the units already gone.
    res = client.post(f"/api/inventory/recalls/{recall.id}/execute_freeze/")
    assert res.status_code == status.HTTP_200_OK, res.content
    assert res.data["status"] == "frozen"
    assert res.data["units_still_held"] == batch.quantity_available
    assert res.data["reached_patients"] is False
    assert any(h["organization"] == batch.organization_id for h in res.data["holders"])

    batch.refresh_from_db()
    assert batch.status == InventoryBatch.Status.RECALLED


@pytest.mark.django_db
def test_stock_count_variance_reconciliation(test_data):
    user = test_data["user"]
    org = test_data["org"]
    batch = test_data["batch"]  # initial qty = 100
    client = _auth(user)

    sc = StockCount.objects.create(
        organization=org,
        reference_no="SC-2026-001",
        counter_user=user,
        status=StockCount.Status.SUBMITTED,
    )
    # Counted 95 (deficit of -5)
    StockCountItem.objects.create(
        stock_count=sc,
        batch=batch,
        system_qty=100,
        counted_qty=95,
        variance_qty=-5,
        variance_reason="Uncounted breakage during handling",
    )

    # The counter may no longer approve their own count, so a second person signs.
    own = client.post(f"/api/inventory/stock-counts/{sc.id}/approve_count/")
    assert own.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot approve their own" in str(own.content)

    approver = User.objects.create_user(
        username="stock_approver", password="Password123!", organization=org
    )
    approver.roles.add(Role.objects.get(code="SYS_ADMIN"))
    res = _auth(approver).post(f"/api/inventory/stock-counts/{sc.id}/approve_count/")
    assert res.status_code == status.HTTP_200_OK, res.content

    batch.refresh_from_db()
    assert batch.quantity_available == 95

    # And it posts exactly once — a second approval is refused, not doubled.
    again = _auth(approver).post(f"/api/inventory/stock-counts/{sc.id}/approve_count/")
    assert again.status_code == status.HTTP_400_BAD_REQUEST
    batch.refresh_from_db()
    assert batch.quantity_available == 95, "not 90"

    # Check StockMovement auto-adjustment ledger row
    movement = StockMovement.objects.filter(batch=batch, movement_type="ADJUSTMENT").first()
    assert movement is not None
    assert movement.quantity_delta == -5


@pytest.mark.django_db
def test_stock_disposal_witness_destruction(test_data):
    user = test_data["user"]
    org = test_data["org"]
    client = _auth(user)

    sd = StockDisposal.objects.create(
        organization=org,
        disposal_no="DISP-2026-001",
        primary_witness=user,
        secondary_witness_name="Inspector Mugisha",
        destruction_method="INCINERATION",
        certificate_no="CERT-INC-8819",
    )

    # A disposal that lists nothing destroys nothing — previously this "succeeded"
    # while the stock stayed on the books and the loss never reached the P&L.
    empty = client.post(f"/api/inventory/disposals/{sd.id}/confirm_destruction/")
    assert empty.status_code == status.HTTP_400_BAD_REQUEST
    assert "Nothing is listed" in str(empty.content)

    doomed = InventoryBatch.objects.create(
        organization=org,
        product=test_data["product"],
        batch_number="DEAD-1",
        expiry_date=date.today() - timedelta(days=5),
        quantity_available=20,
        wholesale_cost=Decimal("500"),
        status=InventoryBatch.Status.EXPIRED,
    )
    added = client.post(
        f"/api/inventory/disposals/{sd.id}/add_line/",
        {"batch": doomed.id, "quantity": 20},
        format="json",
    )
    assert added.status_code == 201, added.content

    res = client.post(f"/api/inventory/disposals/{sd.id}/confirm_destruction/")
    assert res.status_code == status.HTTP_200_OK, res.content
    assert res.data["status"] == "DESTROYED"
    assert res.data["units_destroyed"] == 20
    assert res.data["value_written_off"] == "10000.00"

    doomed.refresh_from_db()
    assert doomed.quantity_available == 0, "the units actually left stock"
    assert StockMovement.objects.filter(
        batch=doomed, movement_type=StockMovement.Type.WASTAGE
    ).exists(), "the stock ledger must explain the change"
