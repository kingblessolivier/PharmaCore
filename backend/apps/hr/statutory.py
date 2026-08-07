"""Statutory filing generation — PAYE, RSSB, CBHI, VAT and the annual PIT summary.

The rule that makes this worth having: a filing is generated from the payroll
register *and* cross-checked against the matching GL sub-ledger balance. If the
two disagree the filing still generates, but it cannot be marked filed — which
is exactly the moment you want to find out, rather than after RRA has the return.

Sub-ledger mapping (see ``apps.finance.services._CONTROL_ACCOUNTS``):

    PAYE      → 2200 PAYE Payable
    RSSB      → 2210 RSSB Pension Payable + 2220 RSSB Maternity Payable
    CBHI      → 2230 CBHI Payable
    VAT       → 2300 VAT Payable (Output) less 1350 VAT Input
    WHT       → 2500 WHT Payable
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.finance.models import Account, JournalLine
from apps.hr.models import PayrollRecord, StatutoryFiling
from apps.hr.services_people import PeopleError
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User

ZERO = Decimal("0.00")

#: filing kind → the GL accounts whose balance it must tie to
SUB_LEDGERS: dict[str, tuple[str, ...]] = {
    StatutoryFiling.Kind.PAYE_MONTHLY: ("2200",),
    StatutoryFiling.Kind.RSSB_MONTHLY: ("2210", "2220"),
    StatutoryFiling.Kind.CBHI_MONTHLY: ("2230",),
    StatutoryFiling.Kind.VAT_MONTHLY: ("2300",),
    StatutoryFiling.Kind.WHT_MONTHLY: ("2500",),
    StatutoryFiling.Kind.PIT_ANNUAL: ("2200",),
}


def _q(value: Decimal | None) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def sub_ledger_balance(organization: Organization, codes: tuple[str, ...], upto: date) -> Decimal:
    """Credit-less-debit balance of the statutory payable accounts up to a date."""
    lines = JournalLine.objects.filter(
        entry__organization=organization,
        entry__entry_date__lte=upto,
        account__code__in=codes,
        account__organization=organization,
    )
    credit = lines.filter(side=JournalLine.Side.CREDIT).aggregate(t=Sum("amount"))["t"] or 0
    debit = lines.filter(side=JournalLine.Side.DEBIT).aggregate(t=Sum("amount"))["t"] or 0
    return _q(Decimal(credit) - Decimal(debit))


def statutory_due_date(kind: str, period_end: date) -> date:
    """PAYE/RSSB/CBHI/VAT are due on the 15th of the following month; PIT on 31 March."""
    if kind == StatutoryFiling.Kind.PIT_ANNUAL:
        return date(period_end.year + 1, 3, 31)
    first_next = (period_end.replace(day=1) + timedelta(days=32)).replace(day=1)
    return first_next.replace(day=15)


@transaction.atomic
def generate_filing(
    *,
    organization: Organization,
    kind: str,
    period_start: date,
    period_end: date,
    user: User | None = None,
) -> StatutoryFiling:
    """Aggregate the period's payroll into a return and cross-check the ledger."""
    if kind not in SUB_LEDGERS:
        raise PeopleError(f"'{kind}' is not a filing kind this system generates.")
    if period_end < period_start:
        raise PeopleError("A filing period cannot end before it starts.")

    records = PayrollRecord.objects.filter(
        run__organization=organization,
        run__period_start__gte=period_start,
        run__period_end__lte=period_end,
        run__status__in=["APPROVED", "PAID"],
    ).select_related("employee", "run")

    totals = records.aggregate(
        gross=Sum("gross"),
        paye=Sum("paye"),
        pension_ee=Sum("pension_employee"),
        pension_er=Sum("pension_employer"),
        maternity_ee=Sum("maternity_employee"),
        maternity_er=Sum("maternity_employer"),
        cbhi=Sum("cbhi"),
    )
    gross = _q(totals["gross"])

    if kind in {StatutoryFiling.Kind.PAYE_MONTHLY, StatutoryFiling.Kind.PIT_ANNUAL}:
        employee_part, employer_part = _q(totals["paye"]), ZERO
    elif kind == StatutoryFiling.Kind.RSSB_MONTHLY:
        employee_part = _q(totals["pension_ee"]) + _q(totals["maternity_ee"])
        employer_part = _q(totals["pension_er"]) + _q(totals["maternity_er"])
    elif kind == StatutoryFiling.Kind.CBHI_MONTHLY:
        employee_part, employer_part = _q(totals["cbhi"]), ZERO
    else:  # VAT / WHT are ledger-driven, not payroll-driven
        employee_part = employer_part = ZERO

    amount_due = _q(employee_part + employer_part)
    ledger = sub_ledger_balance(organization, SUB_LEDGERS[kind], period_end)
    if kind in {StatutoryFiling.Kind.VAT_MONTHLY, StatutoryFiling.Kind.WHT_MONTHLY}:
        amount_due = ledger  # the ledger *is* the source for these

    filing, _created = StatutoryFiling.objects.update_or_create(
        organization=organization,
        kind=kind,
        period_start=period_start,
        period_end=period_end,
        defaults={
            "status": StatutoryFiling.Status.GENERATED,
            "due_date": statutory_due_date(kind, period_end),
            "employee_count": records.values("employee").distinct().count(),
            "gross_total": gross,
            "employee_contribution": employee_part,
            "employer_contribution": employer_part,
            "amount_due": amount_due,
            "gl_balance_at_generation": ledger,
            "payload": {
                "lines": [
                    {
                        "employee_number": r.employee.employee_number,
                        "employee_name": r.employee.full_name,
                        "rssb_number": r.employee.rssb_number,
                        "tin": r.employee.tin,
                        "gross": str(r.gross),
                        "paye": str(r.paye),
                        "pension_employee": str(r.pension_employee),
                        "pension_employer": str(r.pension_employer),
                        "maternity_employee": str(r.maternity_employee),
                        "maternity_employer": str(r.maternity_employer),
                        "cbhi": str(r.cbhi),
                        "net_pay": str(r.net_pay),
                    }
                    for r in records
                ],
                "sub_ledger_accounts": list(SUB_LEDGERS[kind]),
            },
        },
    )
    if not filing.reference:
        filing.reference = f"{kind[:4]}-{period_end:%Y%m}-{organization.pk:03d}"
        filing.save(update_fields=["reference"])

    record_audit(
        action="STATUTORY_FILING_GENERATED",
        user=user,
        organization=organization,
        entity_type="statutory_filing",
        entity_id=str(filing.pk),
        changes={
            "kind": kind,
            "period": f"{period_start}–{period_end}",
            "amount_due": str(amount_due),
            "gl_balance": str(ledger),
            "ties": filing.ties_to_ledger,
        },
    )
    return filing


def filing_csv(filing: StatutoryFiling) -> str:
    """The upload-ready return file (RRA/RSSB take a flat CSV)."""
    header = (
        "employee_number,employee_name,rssb_number,tin,gross,paye,"
        "pension_employee,pension_employer,maternity_employee,maternity_employer,cbhi,net_pay"
    )
    rows = [
        ",".join(
            [
                line.get("employee_number", ""),
                f'"{line.get("employee_name", "")}"',
                line.get("rssb_number", ""),
                line.get("tin", ""),
                line.get("gross", "0"),
                line.get("paye", "0"),
                line.get("pension_employee", "0"),
                line.get("pension_employer", "0"),
                line.get("maternity_employee", "0"),
                line.get("maternity_employer", "0"),
                line.get("cbhi", "0"),
                line.get("net_pay", "0"),
            ]
        )
        for line in filing.payload.get("lines", [])
    ]
    return "\n".join([header, *rows])


def ensure_statutory_accounts(organization: Organization) -> dict[str, Account]:
    """The statutory payables a filing reads — created by the finance bootstrap."""
    from apps.finance.services import ensure_default_accounts

    return ensure_default_accounts(organization)
