from datetime import date
from decimal import Decimal

import pytest
from apps.finance.budgeting import budget_variance
from apps.finance.models import (
    Budget,
    BudgetLine,
    CostCentre,
    FixedAsset,
    JournalLine,
    TaxRecord,
)
from apps.finance.services import ensure_default_accounts, post_journal
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


def test_budget_variance_reads_actuals_from_the_ledger():
    """Rewritten for the redesign: `Budget.actual_amount` no longer exists.

    The old version of this test created a budget with a hand-typed actual and
    asserted the subtraction — which is exactly the defect the redesign removed,
    because nothing computed that column. Actuals now come from posted journal
    lines and cannot be supplied by a caller.

    Fuller coverage lives in tests/test_finance_ledger_spine.py; this keeps the
    guarantee asserted where the old behaviour used to be.
    """
    org = Organization.objects.create(name="Kigali Retail Pharmacy", type="RETAIL")
    dept = Department.objects.create(organization=org, code="PHARM", name="Pharmacy Dispensing")
    accounts = ensure_default_accounts(org)
    centre = CostCentre.objects.create(
        organization=org, code="PHARM", name="Pharmacy Dispensing", department=dept
    )

    budget = Budget.objects.create(organization=org, name="FY2026 operating", financial_year=2026)
    BudgetLine.objects.create(
        budget=budget,
        account=accounts["6110"],
        cost_centre=centre,
        period_month=6,
        amount=Decimal("500000.00"),
    )
    post_journal(
        organization=org,
        entry_date=date(2026, 6, 30),
        description="Dispensing supplies",
        cost_centre=centre,
        lines=[
            {
                "account": accounts["6110"],
                "side": JournalLine.Side.DEBIT,
                "amount": Decimal("350000.00"),
                "memo": "",
            },
            {
                "account": accounts["1100"],
                "side": JournalLine.Side.CREDIT,
                "amount": Decimal("350000.00"),
                "memo": "",
            },
        ],
    )

    result = budget_variance(budget, start=date(2026, 6, 1), end=date(2026, 6, 30))
    row = next(r for r in result["rows"] if r["code"] == "6110")
    assert row["budget"] == "500000.00"
    assert row["actual"] == "350000.00"
    assert row["variance"] == "150000.00"
    # Under plan on a cost is good news.
    assert row["verdict"] == "FAVOURABLE"
