from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.iam.models import Organization
from apps.retail.models import (
    ClinicalService,
    ClinicalServiceRecord,
    ControlledSubstanceRegister,
    POSPromotion,
    Prescription,
)


@pytest.mark.django_db
def test_prescription_lifecycle():
    org = Organization.objects.create(name="Test Pharmacy", type="RETAIL_PHARMACY")
    rx = Prescription.objects.create(
        prescription_number="RX-TEST-001",
        organization=org,
        patient_name="Test Patient",
        patient_id_number="123456789",
        patient_phone="+250788000111",
        prescriber_name="Dr. Test",
        prescriber_license="LIC-001",
        issue_date=date.today(),
        expiry_date=date.today() + timedelta(days=30),
        refills_allowed=3,
        refills_used=1,
        status="ACTIVE",
    )
    assert rx.remaining_refills == 2
    assert str(rx) == "Rx #RX-TEST-001 · Test Patient"


@pytest.mark.django_db
def test_controlled_substance_register():
    org = Organization.objects.create(name="Test Pharmacy", type="RETAIL_PHARMACY")
    p = Product.objects.create(
        generic_name="Morphine 10mg",
        dosage_form="TABLET",
        strength="10mg",
        is_controlled_substance=True,
    )
    log = ControlledSubstanceRegister.objects.create(
        organization=org,
        product=p,
        batch_number="BATCH-M1",
        movement_type="DISPENSING",
        quantity=-10,
        running_balance=90,
        patient_name="John Doe",
        prescriber_name="Dr. Smith",
        witness_name="Pharm. Jane",
    )
    assert log.running_balance == 90
    assert "Morphine 10mg" in str(log)


@pytest.mark.django_db
def test_pos_promotion_and_clinical_service():
    promo = POSPromotion.objects.create(
        code="PROMO10",
        name="10% Off",
        promo_type="PERCENT",
        discount_value=Decimal("10.00"),
        min_spend=Decimal("5000.00"),
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=7),
    )
    assert promo.is_active is True

    org = Organization.objects.create(name="Test Pharmacy", type="RETAIL_PHARMACY")
    svc = ClinicalService.objects.create(
        service_code="SVC-001",
        name="BP Screening",
        category="SCREENING",
        fee_amount=Decimal("2000.00"),
    )
    enc = ClinicalServiceRecord.objects.create(
        organization=org,
        service=svc,
        patient_name="Jane Doe",
        fee_charged=Decimal("2000.00"),
        clinical_notes="120/80 mmHg",
    )
    assert enc.fee_charged == Decimal("2000.00")
