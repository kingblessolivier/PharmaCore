"""Tests for OpeningBalance import + validation (F4.4)."""

from __future__ import annotations

import json

import pytest
from apps.finance.models import Account, JournalEntry, OpeningBalance
from apps.finance.services import (
    OpeningBalanceValidationError,
    import_opening_balances,
    validate_opening_balance_rows,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def chart_of_accounts(organization):
    """A minimal pair of accounts to balance a journal against."""
    cash = Account.objects.create(
        organization=organization,
        code="1000",
        name="Cash & Bank",
        account_type=Account.Type.ASSET,
        normal_balance=Account.Balance.DEBIT,
        is_system=True,
    )
    equity = Account.objects.create(
        organization=organization,
        code="3000",
        name="Owner's Equity",
        account_type=Account.Type.EQUITY,
        normal_balance=Account.Balance.CREDIT,
        is_system=True,
    )
    return cash, equity


def _gl_row(account_code: str, debit: str = "0", credit: str = "0", key: str = "") -> dict:
    return {
        "kind": OpeningBalance.Kind.GL_TRIAL_BALANCE,
        "reference_key": key or f"gl-{account_code}",
        "payload": {"account_code": account_code, "debit": debit, "credit": credit},
    }


def test_empty_rows_raises(organization):
    with pytest.raises(OpeningBalanceValidationError) as exc:
        validate_opening_balance_rows(organization=organization, rows=[])
    assert "No opening-balance rows" in str(exc.value)


def test_trial_balance_must_balance(organization, chart_of_accounts):
    cash, equity = chart_of_accounts
    rows = [
        _gl_row("1000", debit="1000.00", credit="0"),
        _gl_row("3000", debit="0", credit="900.00"),  # 100 vs 90 — fails
    ]
    with pytest.raises(OpeningBalanceValidationError) as exc:
        validate_opening_balance_rows(organization=organization, rows=rows)
    assert any("does not balance" in e for e in exc.value.errors)


def test_trial_balance_unknown_account_rejected(organization, chart_of_accounts):
    rows = [_gl_row("9999", debit="100.00", credit="100.00")]
    with pytest.raises(OpeningBalanceValidationError) as exc:
        validate_opening_balance_rows(organization=organization, rows=rows)
    assert any("unknown account code" in e for e in exc.value.errors)


def test_balanced_trial_balance_passes(organization, chart_of_accounts):
    cash, equity = chart_of_accounts
    rows = [
        _gl_row("1000", debit="1500.00", credit="0"),
        _gl_row("3000", debit="0", credit="1500.00"),
    ]
    validated = validate_opening_balance_rows(organization=organization, rows=rows)
    assert len(validated) == 2


def test_duplicate_reference_key_within_import_rejected(organization, chart_of_accounts):
    rows = [
        _gl_row("1000", debit="100.00", credit="0", key="dup"),
        _gl_row("1000", debit="0", credit="100.00", key="dup"),
    ]
    with pytest.raises(OpeningBalanceValidationError) as exc:
        validate_opening_balance_rows(organization=organization, rows=rows)
    assert any("Duplicate row" in e for e in exc.value.errors)


def test_ar_aging_validates_bucket_and_amount(organization):
    rows = [
        {
            "kind": OpeningBalance.Kind.AR_AGING,
            "reference_key": "AR-1",
            "payload": {
                "partner_ref": "BPH",
                "invoice_number": "INV-001",
                "amount": "0.00",  # invalid
                "aging_bucket": "d30",
            },
        }
    ]
    with pytest.raises(OpeningBalanceValidationError) as exc:
        validate_opening_balance_rows(organization=organization, rows=rows)
    assert any("amount must be > 0" in e for e in exc.value.errors)


def test_ar_aging_validates_bucket_value(organization):
    rows = [
        {
            "kind": OpeningBalance.Kind.AR_AGING,
            "reference_key": "AR-1",
            "payload": {
                "partner_ref": "BPH",
                "invoice_number": "INV-001",
                "amount": "1000.00",
                "aging_bucket": "d180",  # not in valid set
            },
        }
    ]
    with pytest.raises(OpeningBalanceValidationError) as exc:
        validate_opening_balance_rows(organization=organization, rows=rows)
    assert any("invalid aging_bucket" in e for e in exc.value.errors)


def test_unknown_kind_rejected(organization):
    with pytest.raises(OpeningBalanceValidationError) as exc:
        validate_opening_balance_rows(
            organization=organization,
            rows=[{"kind": "BOGUS", "reference_key": "x", "payload": {}}],
        )
    assert any("Unknown kind" in e for e in exc.value.errors)


def test_import_persists_rows(organization, chart_of_accounts):
    cash, equity = chart_of_accounts
    rows = [
        _gl_row("1000", debit="5000.00", credit="0"),
        _gl_row("3000", debit="0", credit="5000.00"),
    ]
    saved = import_opening_balances(organization=organization, rows=rows, apply=False)
    assert len(saved) == 2
    assert OpeningBalance.objects.filter(organization=organization).count() == 2
    assert all(r.applied_at is None for r in saved)


def test_import_is_idempotent(organization, chart_of_accounts):
    cash, equity = chart_of_accounts
    rows = [
        _gl_row("1000", debit="1000.00", credit="0"),
        _gl_row("3000", debit="0", credit="1000.00"),
    ]
    import_opening_balances(organization=organization, rows=rows, apply=False)
    import_opening_balances(organization=organization, rows=rows, apply=False)
    # Still 2 rows, not 4.
    assert OpeningBalance.objects.filter(organization=organization).count() == 2


def test_import_with_apply_writes_opening_journal(organization, chart_of_accounts):
    """apply=True promotes drafts to applied and writes the GL opening entry."""
    cash, equity = chart_of_accounts
    rows = [
        _gl_row("1000", debit="2500.00", credit="0"),
        _gl_row("3000", debit="0", credit="2500.00"),
    ]
    import_opening_balances(organization=organization, rows=rows, apply=True)
    # The opening journal exists.
    je = JournalEntry.objects.filter(
        organization=organization, reference_type="opening_balance"
    ).first()
    assert je is not None
    assert je.lines.count() == 2
    # The OpeningBalance rows are now marked applied.
    assert (
        OpeningBalance.objects.filter(organization=organization, applied_at__isnull=True).count()
        == 0
    )


def test_validation_failure_does_not_persist_rows(organization, chart_of_accounts):
    """Validation runs before any write — a failed trial balance leaves the
    OpeningBalance table untouched."""
    rows = [
        _gl_row("1000", debit="100.00", credit="0"),
        _gl_row("3000", debit="0", credit="99.00"),  # fails
    ]
    with pytest.raises(OpeningBalanceValidationError):
        import_opening_balances(organization=organization, rows=rows, apply=False)
    assert OpeningBalance.objects.count() == 0


def test_stock_batch_validation_requires_known_product(organization):
    rows = [
        {
            "kind": OpeningBalance.Kind.STOCK_BATCH,
            "reference_key": "BATCH-1",
            "payload": {
                "product_id": 99999,
                "batch_number": "B-1",
                "expiry_date": "2026-12-31",
                "quantity": 10,
                "unit_cost": "100.00",
            },
        }
    ]
    with pytest.raises(OpeningBalanceValidationError) as exc:
        validate_opening_balance_rows(organization=organization, rows=rows)
    assert any("unknown product_id" in e for e in exc.value.errors)


def test_employee_leave_validates_employee_id(organization):
    rows = [
        {
            "kind": OpeningBalance.Kind.EMPLOYEE_LEAVE,
            "reference_key": "EMP-99-ANNUAL",
            "payload": {
                "employee_id": "99999",
                "leave_type": "ANNUAL",
                "days_accrued": "5",
            },
        }
    ]
    with pytest.raises(OpeningBalanceValidationError) as exc:
        validate_opening_balance_rows(organization=organization, rows=rows)
    assert any("unknown employee_id" in e for e in exc.value.errors)


def test_mixed_kinds_validate_independently(organization, chart_of_accounts):
    """One import can carry multiple kinds — each kind's validation runs."""
    rows = [
        _gl_row("1000", debit="100.00", credit="0"),
        _gl_row("3000", debit="0", credit="100.00"),
        {
            "kind": OpeningBalance.Kind.AR_AGING,
            "reference_key": "AR-1",
            "payload": {
                "partner_ref": "BPH",
                "invoice_number": "INV-001",
                "amount": "500.00",
                "aging_bucket": "d60",
            },
        },
    ]
    validated = validate_opening_balance_rows(organization=organization, rows=rows)
    assert len(validated) == 3


def test_import_opening_balances_command_runs_end_to_end(tmp_path, organization, chart_of_accounts):
    """The management command reads JSON from disk and applies the rows."""
    from django.core.management import call_command

    payload = {
        "organization": organization.name,
        "rows": [
            _gl_row("1000", debit="750.00", credit="0"),
            _gl_row("3000", debit="0", credit="750.00"),
        ],
    }
    f = tmp_path / "opening.json"
    f.write_text(json.dumps(payload), encoding="utf-8")

    call_command("import_opening_balances", str(f))
    assert OpeningBalance.objects.filter(organization=organization).count() == 2


def test_import_opening_balances_command_validation_error_exits(
    tmp_path, organization, chart_of_accounts
):
    """The command surfaces validation errors before any persist."""
    from django.core.management import call_command
    from django.core.management.base import CommandError

    payload = {
        "organization": organization.name,
        "rows": [
            _gl_row("1000", debit="100.00", credit="0"),
            _gl_row("3000", debit="0", credit="99.00"),
        ],
    }
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CommandError):
        call_command("import_opening_balances", str(f))
    assert OpeningBalance.objects.count() == 0
