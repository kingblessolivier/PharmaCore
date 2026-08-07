"""Give every pre-existing budget line a header and a cost centre.

The old rows carried `(organization, department, financial_year, account, amount)`.
A header is created per `(organization, financial_year)` and a `CostCentre` per
department that was actually budgeted against, so the plans survive the reshape
with their meaning intact rather than being silently reduced to org totals.

Old budgets were annual figures, so `period_month` stays null — which is exactly
what null means in the new model. Spreading them across twelve months would have
invented a monthly profile nobody ever agreed.
"""

from __future__ import annotations

import re

from django.db import migrations


def _slug(name: str, fallback: str) -> str:
    """A short, stable cost-centre code from a department name."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", name or "").upper()
    return (cleaned[:12] or fallback)[:20]


def forwards(apps, schema_editor):  # type: ignore[no-untyped-def]
    BudgetLine = apps.get_model("finance", "BudgetLine")
    Budget = apps.get_model("finance", "Budget")
    CostCentre = apps.get_model("finance", "CostCentre")

    lines = list(BudgetLine.objects.all())
    if not lines:
        return

    headers: dict[tuple[int, int], object] = {}
    centres: dict[tuple[int, int], object] = {}

    for line in lines:
        org_id = line.organization_id
        year = line.financial_year

        key = (org_id, year)
        header = headers.get(key)
        if header is None:
            header, _ = Budget.objects.get_or_create(
                organization_id=org_id,
                financial_year=year,
                name=f"FY{year} operating budget",
                defaults={"status": "APPROVED", "notes": "Migrated from the pre-redesign budget."},
            )
            headers[key] = header

        centre = None
        if line.department_id:
            ckey = (org_id, line.department_id)
            centre = centres.get(ckey)
            if centre is None:
                dept = line.department
                centre, _ = CostCentre.objects.get_or_create(
                    organization_id=org_id,
                    code=_slug(getattr(dept, "name", ""), f"DEPT{line.department_id}"),
                    defaults={
                        "name": getattr(dept, "name", f"Department {line.department_id}"),
                        "kind": "DEPARTMENT",
                        "department_id": line.department_id,
                    },
                )
                centres[ckey] = centre

        line.budget = header
        line.cost_centre = centre
        line.save(update_fields=["budget", "cost_centre"])


def backwards(apps, schema_editor):  # type: ignore[no-untyped-def]
    """Detach the lines; the headers and centres are left for inspection."""
    BudgetLine = apps.get_model("finance", "BudgetLine")
    BudgetLine.objects.update(budget=None, cost_centre=None)


class Migration(migrations.Migration):
    dependencies = [("finance", "0017_ledger_spine")]
    operations = [migrations.RunPython(forwards, backwards)]
