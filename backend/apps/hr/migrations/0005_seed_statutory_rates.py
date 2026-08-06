"""Seed the Rwanda statutory rates the payroll engine reads from (versioned,
effective-dated — see docs/18-rwanda-integrations-and-statutory.md §3):

- PAYE (monthly, progressive on gross): 0–60,000 RWF -> 0%; 60,001–100,000 -> 10%;
  100,001–200,000 -> 20%; >200,000 -> 30%.
- RSSB pension: 6% employee + 6% employer (since Jan 2025).
- Maternity leave: 0.3% employee + 0.3% employer.
- CBHI: 0.5% of net pay (employee only).

Idempotent; additive only.
"""

from __future__ import annotations

from datetime import date

from django.db import migrations

EFFECTIVE_FROM = date(2025, 1, 1)

PAYE_BRACKETS = [
    (0, 60000, 0),
    (60000, 100000, 10),
    (100000, 200000, 20),
    (200000, None, 30),
]

FLAT_RATES = [
    ("PENSION_EMPLOYEE", 6),
    ("PENSION_EMPLOYER", 6),
    ("MATERNITY_EMPLOYEE", 0.3),
    ("MATERNITY_EMPLOYER", 0.3),
    ("CBHI", 0.5),
]


def seed(apps, schema_editor):
    StatutoryRate = apps.get_model("hr", "StatutoryRate")
    for band_min, band_max, rate_pct in PAYE_BRACKETS:
        StatutoryRate.objects.get_or_create(
            rate_type="PAYE_BRACKET",
            band_min=band_min,
            effective_from=EFFECTIVE_FROM,
            defaults={"band_max": band_max, "rate_pct": rate_pct, "country": "RW"},
        )
    for rate_type, rate_pct in FLAT_RATES:
        StatutoryRate.objects.get_or_create(
            rate_type=rate_type,
            band_min=0,
            effective_from=EFFECTIVE_FROM,
            defaults={"band_max": None, "rate_pct": rate_pct, "country": "RW"},
        )


def unseed(apps, schema_editor):
    apps.get_model("hr", "StatutoryRate").objects.filter(effective_from=EFFECTIVE_FROM).delete()


class Migration(migrations.Migration):
    dependencies = [("hr", "0004_payrollrun_payrollrecord_statutoryrate_and_more")]
    operations = [migrations.RunPython(seed, unseed)]
