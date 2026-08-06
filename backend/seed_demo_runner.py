import os
import sys
import django
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.iam.models import Organization, Department, User
from apps.catalog.models import Product, PriceList, Manufacturer, ActiveIngredient
from apps.inventory.models import InventoryBatch, StorageZone, BinLocation, TemperatureSensor, TemperatureLog, QualityCheck, BatchRecall, StockCount, StockDisposal
from apps.distribution.models import StockOrder, DepotProductListing, SalesRepresentative, JourneyPlan, SalesVisitLog, TenderContract, CustomerReturn
from apps.finance.models import FixedAsset, TaxRecord, Budget, CustomerInvoice, CustomerCredit, CustomerReceipt
from apps.hr.models import Employee, AttendanceLog, ShiftRoster, LeaveRequest

print("Starting Enterprise Demo Data Seeding...")

# 1. Fetch or Create Core Organizations & Users
depot_org = Organization.objects.filter(type="DISTRIBUTOR").first()
if not depot_org:
    depot_org = Organization.objects.create(
        name="Kigali Central Distribution Depot",
        type="DISTRIBUTOR",
        email="depot@pharmacore.rw",
        phone="+250788100100",
        is_active=True,
    )

retail_org = Organization.objects.filter(type="RETAIL_PHARMACY").first()
if not retail_org:
    retail_org = Organization.objects.create(
        name="Nyashishi Retail Pharmacy",
        type="RETAIL_PHARMACY",
        email="nyarugenge@pharmacore.rw",
        phone="+250788200200",
        is_active=True,
    )

admin_user = User.objects.filter(is_superuser=True).first()
if not admin_user:
    admin_user = User.objects.filter(username="admin").first()

if not admin_user:
    admin_user = User.objects.create_superuser(
        username="admin",
        email="admin@pharmacore.rw",
        password="AdminPassword123!",
        full_name="System Administrator",
        organization=depot_org
    )

print(f"Using Admin User: {admin_user.username}, Depot: {depot_org.name}, Retail: {retail_org.name}")

# 2. Seed Catalog Items
p1 = Product.objects.filter(brand_name="Panadol").first()
if not p1:
    p1 = Product.objects.create(
        generic_name="Paracetamol 500mg Tablets",
        brand_name="Panadol",
        dosage_form="TABLET",
        strength="500mg",
        requires_prescription=False,
        is_controlled_substance=False,
    )

p2 = Product.objects.filter(brand_name="Amoxil").first()
if not p2:
    p2 = Product.objects.create(
        generic_name="Amoxicillin 500mg Capsules",
        brand_name="Amoxil",
        dosage_form="CAPSULE",
        strength="500mg",
        requires_prescription=True,
        is_controlled_substance=False,
    )

p3 = Product.objects.filter(brand_name="Humulin R").first()
if not p3:
    p3 = Product.objects.create(
        generic_name="Human Insulin 100IU/ml Vial",
        brand_name="Humulin R",
        dosage_form="INJECTION",
        strength="100IU/ml",
        requires_prescription=True,
        is_controlled_substance=False,
    )

mfg, _ = Manufacturer.objects.get_or_create(
    name="GlaxoSmithKline Pharmaceuticals",
    defaults={"country": "United Kingdom", "is_active": True}
)

ing, _ = ActiveIngredient.objects.get_or_create(
    name="Paracetamol",
    defaults={"atc_code": "N02BE01"}
)

# 3. Seed Inventory & Storage Zones
z1, _ = StorageZone.objects.get_or_create(
    organization=depot_org,
    name="Main Ambient Warehouse Zone (15-25°C)",
    defaults={
        "zone_type": "AMBIENT",
        "temp_min_celsius": Decimal("15.00"),
        "temp_max_celsius": Decimal("25.00"),
    }
)

z2, _ = StorageZone.objects.get_or_create(
    organization=depot_org,
    name="Vaccine Cold Chain Vault (2-8°C)",
    defaults={
        "zone_type": "COLD_CHAIN",
        "temp_min_celsius": Decimal("2.00"),
        "temp_max_celsius": Decimal("8.00"),
    }
)

sensor, _ = TemperatureSensor.objects.get_or_create(
    name="Cold Room Sensor 01",
    defaults={
        "device_id": "SENS-VAULT-01",
        "organization": depot_org,
        "zone": z2,
        "is_active": True,
    }
)

# Create recent temperature log
TemperatureLog.objects.create(
    sensor=sensor,
    temperature_celsius=Decimal("4.20"),
    humidity_percent=Decimal("55.00"),
    excursion_status="NORMAL",
)

# Seed Inventory Batches
b1, _ = InventoryBatch.objects.get_or_create(
    organization=depot_org,
    batch_number="BATCH-PAR-2026A",
    defaults={
        "product": p1,
        "quantity_available": 1500,
        "quantity_reserved": 100,
        "wholesale_cost": Decimal("1200.00"),
        "expiry_date": date.today() + timedelta(days=365),
    }
)

b2, _ = InventoryBatch.objects.get_or_create(
    organization=depot_org,
    batch_number="BATCH-AMO-2026B",
    defaults={
        "product": p2,
        "quantity_available": 800,
        "quantity_reserved": 50,
        "wholesale_cost": Decimal("3500.00"),
        "expiry_date": date.today() + timedelta(days=540),
    }
)

# Seed Quality Check & Disposal
QualityCheck.objects.get_or_create(
    batch=b2,
    defaults={
        "inspector": admin_user,
        "status": "PASSED",
        "inspection_notes": "Visual inspection and certificate of analysis verified. Approved for active stock.",
    }
)

StockDisposal.objects.get_or_create(
    organization=depot_org,
    disposal_no="DISP-2026-001",
    defaults={
        "reason": "EXPIRED",
        "destruction_method": "INCINERATION",
        "primary_witness": admin_user,
        "status": "APPROVED",
    }
)

# 4. Seed Distribution & Depot Listings (Offered vs On-Hand)
DepotProductListing.objects.get_or_create(
    depot=depot_org,
    product=p1,
    defaults={
        "offered_qty": 500,
        "buffer_qty": 50,
        "price_per_unit": Decimal("2000.00"),
        "is_published": True,
        "customer_segment": "ALL",
        "min_order_qty": 10,
    }
)

DepotProductListing.objects.get_or_create(
    depot=depot_org,
    product=p2,
    defaults={
        "offered_qty": 300,
        "buffer_qty": 30,
        "price_per_unit": Decimal("5500.00"),
        "is_published": True,
        "customer_segment": "ALL",
        "min_order_qty": 5,
    }
)

sales_rep, _ = SalesRepresentative.objects.get_or_create(
    organization=depot_org,
    user=admin_user,
    defaults={
        "territory_code": "KIGALI-CENTRAL",
        "monthly_sales_target": Decimal("25000000.00"),
        "commission_rate_pct": Decimal("2.50"),
        "is_active": True,
    }
)

jp, _ = JourneyPlan.objects.get_or_create(
    rep=sales_rep,
    customer_org=retail_org,
    planned_date=date.today(),
    defaults={"is_completed": True}
)

SalesVisitLog.objects.get_or_create(
    journey_plan=jp,
    rep=sales_rep,
    customer_org=retail_org,
    visited_at=timezone.now(),
    defaults={
        "visit_type": "PRE_SALES",
        "notes": "Reviewed monthly stock levels for Amoxicillin & Panadol. Retailer placed reorder.",
        "sales_amount": Decimal("1500000.00"),
    }
)

TenderContract.objects.get_or_create(
    tender_number="TENDER-MOH-2026-088",
    defaults={
        "depot": depot_org,
        "client_org": retail_org,
        "product": p1,
        "contract_price": Decimal("1750.00"),
        "total_committed_qty": 10000,
        "drawn_qty": 2500,
        "valid_until": date.today() + timedelta(days=180),
        "is_active": True,
    }
)

CustomerReturn.objects.get_or_create(
    return_number="RET-2026-004",
    defaults={
        "depot": depot_org,
        "retail": retail_org,
        "status": "APPROVED",
        "reason": "Near-expiry return within 60-day policy window.",
        "credit_note_amount": Decimal("180000.00"),
    }
)

# 5. Seed Finance Items
FixedAsset.objects.get_or_create(
    asset_number="AST-2026-001",
    defaults={
        "organization": depot_org,
        "name": "Thermo King Transport Refrigeration Unit",
        "category": "VEHICLE",
        "acquisition_date": date.today() - timedelta(days=120),
        "acquisition_cost": Decimal("18500000.00"),
        "useful_life_years": 5,
        "salvage_value": Decimal("1500000.00"),
        "accumulated_depreciation": Decimal("1133333.33"),
        "is_active": True,
    }
)

TaxRecord.objects.get_or_create(
    receipt_number="EBM-2026-009941",
    defaults={
        "organization": depot_org,
        "sdc_id": "SDC-RW-00192",
        "mrc_number": "MRC-88391-2026",
        "taxable_amount": Decimal("1000000.00"),
        "vat_amount": Decimal("180000.00"),
        "tax_class_b": Decimal("180000.00"),
        "qr_code_payload": "https://ebm.rra.gov.rw/verify/SDC-RW-00192/EBM-2026-009941",
    }
)

dept, _ = Department.objects.get_or_create(
    name="Warehouse & Logistics",
    defaults={"code": "LOG-01", "organization": depot_org}
)

from apps.finance.models import Account

acc = Account.objects.filter(organization=depot_org).first()
if not acc:
    acc = Account.objects.create(
        organization=depot_org,
        code="6000-LOGISTICS",
        name="Warehouse Freight & Cold-Chain Operations",
        account_type="EXPENSE",
    )

Budget.objects.get_or_create(
    organization=depot_org,
    department=dept,
    financial_year=2026,
    account=acc,
    defaults={
        "budgeted_amount": Decimal("45000000.00"),
        "actual_amount": Decimal("38200000.00"),
    }
)

# 6. Seed HR Items
emp, _ = Employee.objects.get_or_create(
    user=admin_user,
    defaults={
        "organization": depot_org,
        "department": dept,
        "employee_number": "EMP-001",
        "first_name": "Admin",
        "last_name": "System",
        "hire_date": date.today() - timedelta(days=365),
        "employment_status": "ACTIVE",
        "base_salary": Decimal("2500000.00"),
    }
)

AttendanceLog.objects.get_or_create(
    employee=emp,
    date=date.today(),
    defaults={
        "clock_in": timezone.now() - timedelta(hours=8),
        "clock_out": timezone.now(),
        "status": "PRESENT",
        "notes": "Biometric Gate 1 clock-in logged.",
    }
)

ShiftRoster.objects.get_or_create(
    organization=depot_org,
    employee=emp,
    date=date.today(),
    defaults={
        "shift_type": "MORNING",
        "requires_pharmacist_license": True,
    }
)

LeaveRequest.objects.get_or_create(
    employee=emp,
    leave_type="ANNUAL",
    start_date=date.today() + timedelta(days=14),
    end_date=date.today() + timedelta(days=21),
    defaults={
        "days_count": 7,
        "status": "APPROVED",
        "reason": "Annual statutory leave balance utilization.",
        "approved_by": admin_user,
    }
)

# 7. Seed Retail POS Advanced Items
from apps.retail.models import Prescription, ControlledSubstanceRegister, POSPromotion, ClinicalService, ClinicalServiceRecord

Prescription.objects.get_or_create(
    prescription_number="RX-2026-009",
    defaults={
        "organization": retail_org,
        "patient_name": "Jean-Pierre Niyonzima",
        "patient_id_number": "1199080012345678",
        "patient_phone": "+250788123456",
        "prescriber_name": "Dr. Emmanuel Habimana",
        "prescriber_license": "CPM-RW-8849",
        "issue_date": date.today() - timedelta(days=5),
        "expiry_date": date.today() + timedelta(days=25),
        "refills_allowed": 3,
        "refills_used": 1,
        "status": "ACTIVE",
        "notes": "Amoxicillin 500mg TDS for 7 days",
    }
)

ControlledSubstanceRegister.objects.get_or_create(
    organization=retail_org,
    batch_number="BATCH-CS-2026-X",
    movement_type="DISPENSING",
    defaults={
        "product": p2,
        "quantity": -20,
        "running_balance": 80,
        "patient_name": "Jean-Pierre Niyonzima",
        "prescriber_name": "Dr. Emmanuel Habimana",
        "witness_name": "Pharm. Marie Claire Mukamana",
        "rx_reference": "RX-2026-009",
        "logged_by": admin_user,
    }
)

POSPromotion.objects.get_or_create(
    code="RAMADAN2026",
    defaults={
        "name": "Ramadan Health & Wellness 10% Discount",
        "promo_type": "PERCENT",
        "discount_value": Decimal("10.00"),
        "min_spend": Decimal("10000.00"),
        "valid_from": date.today() - timedelta(days=10),
        "valid_until": date.today() + timedelta(days=20),
        "is_active": True,
    }
)

cs1, _ = ClinicalService.objects.get_or_create(
    service_code="SVC-VACC-01",
    defaults={
        "name": "Hepatitis B Vaccination Dose",
        "category": "VACCINATION",
        "fee_amount": Decimal("15000.00"),
        "is_active": True,
    }
)

cs2, _ = ClinicalService.objects.get_or_create(
    service_code="SVC-SCREEN-02",
    defaults={
        "name": "Blood Pressure & Blood Glucose Screening",
        "category": "SCREENING",
        "fee_amount": Decimal("3000.00"),
        "is_active": True,
    }
)

ClinicalServiceRecord.objects.get_or_create(
    organization=retail_org,
    service=cs2,
    patient_name="Claudine Uwase",
    defaults={
        "patient_phone": "+250788998877",
        "performed_by": admin_user,
        "clinical_notes": "BP: 120/80 mmHg (Normal), Glucose: 5.4 mmol/L (Fasting).",
        "fee_charged": Decimal("3000.00"),
    }
)

print("SUCCESS: Seeded rich enterprise demo data across all modules!")
