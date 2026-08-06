from datetime import date
from decimal import Decimal

import pytest
from apps.finance.models import Account, Budget, FixedAsset, TaxRecord
from apps.iam.models import Department, Organization

pytestmark = pytest.mark.django_db


def test_fixed_asset_depreciation_and_net_book_value():
    org = Organization.objects.create(name="Central Depot", type="DEPOT")
    asset = FixedAsset.objects.create(
        organization=org,
        asset_number="AST-001",
        name="Ultra-Low Freezer -80C",
        category=FixedAsset.Category.EQUIPMENT,
        acquisition_date=date(2025, 1, 1),
        acquisition_cost=Decimal("1000000.00"),
        useful_life_years=5,
        salvage_value=Decimal("0.00"),
        accumulated_depreciation=Decimal("200000.00"),
    )
    assert asset.net_book_value == Decimal("800000.00")
    assert asset.annual_depreciation == Decimal("200000.00")


def test_ebm_tax_record_creation():
    org = Organization.objects.create(name="Kigali Retail Pharmacy", type="RETAIL")
    tax_rec = TaxRecord.objects.create(
        organization=org,
        receipt_number="001-2026-8812",
        sdc_id="SDC0001",
        mrc_number="MRC0001",
        taxable_amount=Decimal("10000.00"),
        vat_amount=Decimal("1800.00"),
        tax_class_b=Decimal("1800.00"),
        qr_code_payload="https://ebm.rra.gov.rw/verify/001-2026-8812",
    )
    assert tax_rec.vat_amount == Decimal("1800.00")
    assert "EBM-001-2026-8812" in str(tax_rec)


def test_budget_variance_calculation():
    org = Organization.objects.create(name="Kigali Retail Pharmacy", type="RETAIL")
    dept = Department.objects.create(organization=org, code="PHARM", name="Pharmacy Dispensing")
    account = Account.objects.create(
        organization=org,
        code="5000",
        name="Dispensing Supplies Expense",
        account_type=Account.Type.EXPENSE,
        normal_balance=Account.Balance.DEBIT,
    )
    budget = Budget.objects.create(
        organization=org,
        department=dept,
        financial_year=2026,
        account=account,
        budgeted_amount=Decimal("500000.00"),
        actual_amount=Decimal("350000.00"),
    )
    assert budget.variance == Decimal("150000.00")
