"""Gross → net payroll engine. Reads rates from the versioned, effective-dated
``StatutoryRate`` table — never hardcoded — so a rate change (e.g. RSSB's scheduled
+2%/yr increase toward 2030) only requires a new row, not a code change.

Formula (ROADMAP "10. People", docs/18-rwanda-integrations-and-statutory.md §3):
Gross = base + allowances + overtime + bonus/commission + shift premium.
PAYE is progressive on gross (RSSB is not deductible from the PAYE base).
CBHI is 0.5% of net pay *after* PAYE/pension/maternity (not of gross).
Net = gross − PAYE − pension(employee) − maternity(employee) − CBHI − loans − other.
Employer-side RSSB pension + maternity are computed for cost, not deducted from pay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Q

from apps.hr.models import Employee, StatutoryRate


def _active_on(on_date: date) -> Any:
    return Q(effective_to__isnull=True) | Q(effective_to__gte=on_date)


def _rate(rate_type: str, on_date: date) -> Decimal:
    row = (
        StatutoryRate.objects.filter(rate_type=rate_type, effective_from__lte=on_date)
        .filter(_active_on(on_date))
        .order_by("-effective_from")
        .first()
    )
    if row is None:
        raise ValueError(f"No effective '{rate_type}' statutory rate as of {on_date}.")
    return row.rate_pct


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_paye(gross: Decimal, on_date: date) -> Decimal:
    """Progressive PAYE across the bracket rows effective on ``on_date``."""
    brackets = list(
        StatutoryRate.objects.filter(
            rate_type=StatutoryRate.RateType.PAYE_BRACKET, effective_from__lte=on_date
        )
        .filter(_active_on(on_date))
        .order_by("band_min")
    )
    if not brackets:
        raise ValueError(f"No effective PAYE brackets as of {on_date}.")
    tax = Decimal("0")
    for band in brackets:
        band_top = band.band_max if band.band_max is not None else gross
        if gross <= band.band_min:
            break
        taxable_in_band = min(gross, band_top) - band.band_min
        if taxable_in_band > 0:
            tax += taxable_in_band * (band.rate_pct / Decimal("100"))
    return _round(tax)


@dataclass
class PayrollLine:
    employee: Employee
    base_salary: Decimal
    allowances: Decimal = Decimal("0")
    overtime_amount: Decimal = Decimal("0")
    bonus_commission: Decimal = Decimal("0")
    shift_premium: Decimal = Decimal("0")
    loans_advances: Decimal = Decimal("0")
    other_deductions: Decimal = Decimal("0")
    gross: Decimal = field(default=Decimal("0"))
    paye: Decimal = field(default=Decimal("0"))
    pension_employee: Decimal = field(default=Decimal("0"))
    pension_employer: Decimal = field(default=Decimal("0"))
    maternity_employee: Decimal = field(default=Decimal("0"))
    maternity_employer: Decimal = field(default=Decimal("0"))
    cbhi: Decimal = field(default=Decimal("0"))
    net_pay: Decimal = field(default=Decimal("0"))


def compute_payroll_line(
    *,
    employee: Employee,
    on_date: date,
    allowances: Decimal = Decimal("0"),
    overtime_amount: Decimal = Decimal("0"),
    bonus_commission: Decimal = Decimal("0"),
    shift_premium: Decimal = Decimal("0"),
    loans_advances: Decimal = Decimal("0"),
    other_deductions: Decimal = Decimal("0"),
) -> PayrollLine:
    line = PayrollLine(
        employee=employee,
        base_salary=employee.base_salary,
        allowances=allowances,
        overtime_amount=overtime_amount,
        bonus_commission=bonus_commission,
        shift_premium=shift_premium,
        loans_advances=loans_advances,
        other_deductions=other_deductions,
    )
    line.gross = _round(
        line.base_salary + allowances + overtime_amount + bonus_commission + shift_premium
    )
    line.paye = compute_paye(line.gross, on_date)
    line.pension_employee = _round(
        line.gross * _rate(StatutoryRate.RateType.PENSION_EMPLOYEE, on_date) / 100
    )
    line.pension_employer = _round(
        line.gross * _rate(StatutoryRate.RateType.PENSION_EMPLOYER, on_date) / 100
    )
    line.maternity_employee = _round(
        line.gross * _rate(StatutoryRate.RateType.MATERNITY_EMPLOYEE, on_date) / 100
    )
    line.maternity_employer = _round(
        line.gross * _rate(StatutoryRate.RateType.MATERNITY_EMPLOYER, on_date) / 100
    )
    net_before_cbhi = line.gross - line.paye - line.pension_employee - line.maternity_employee
    line.cbhi = _round(net_before_cbhi * _rate(StatutoryRate.RateType.CBHI, on_date) / 100)
    line.net_pay = _round(net_before_cbhi - line.cbhi - loans_advances - other_deductions)
    return line
