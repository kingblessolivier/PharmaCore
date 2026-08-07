"""Idempotently seed the Rwanda statutory rates the payroll engine reads.

Additive and safe to re-run — uses ``get_or_create`` so existing rows are
preserved. The originating data migration (``hr/0005_seed_statutory_rates``)
seeds 9 rows from 2025-01-01; this command additionally seeds:

- ``OCCUPATIONAL_HAZARD`` — 2% employer-only (per RSSB scheme rules)
- A 2027 pension bump — Rwanda's gazetted schedule phases pension up to 20%
  total by 2030, so a 2027 row of 7% + 7% is left open for the operator to
  confirm before publishing.

Existing organisations inherit these rows automatically; no per-org seeding
is needed — the rate rows are global (country=RW), and the payroll engine
loads whatever is in effect on the period's end date.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.core.management.base import BaseCommand

from apps.hr.models import StatutoryRate

# Anything you'd want seeded with no expiry (open-ended; a 2026 / 2027 / ...
# bump is a new row, never an edit).
ROOT_RATES = [
    # rate_type, band_min, band_max, rate_pct, effective_from
    ("OCCUPATIONAL_HAZARD", 0, None, 2.0, date(2025, 1, 1)),
]

# Forward-looking bumps that the operator must confirm before publishing.
# A 2027 pension bump is left in place to demonstrate the versioned-rate
# workflow; remove it (or set ``effective_to``) if the gazetted schedule moves.
PHASED_RATES = [
    ("PENSION_EMPLOYEE", 0, None, 7.0, date(2027, 1, 1)),
    ("PENSION_EMPLOYER", 0, None, 7.0, date(2027, 1, 1)),
]


class Command(BaseCommand):
    help = "Seed (or refresh) the Rwanda statutory rates — idempotent."

    def handle(self, *args: Any, **options: Any) -> None:
        seeded_root = 0
        for rate_type, band_min, band_max, rate_pct, eff_from in ROOT_RATES:
            _, created = StatutoryRate.objects.get_or_create(
                rate_type=rate_type,
                band_min=band_min,
                effective_from=eff_from,
                defaults={
                    "band_max": band_max,
                    "rate_pct": rate_pct,
                    "country": "RW",
                },
            )
            if created:
                seeded_root += 1

        seeded_phased = 0
        for rate_type, band_min, band_max, rate_pct, eff_from in PHASED_RATES:
            _, created = StatutoryRate.objects.get_or_create(
                rate_type=rate_type,
                band_min=band_min,
                effective_from=eff_from,
                defaults={
                    "band_max": band_max,
                    "rate_pct": rate_pct,
                    "country": "RW",
                },
            )
            if created:
                seeded_phased += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Statutory rates ready — {seeded_root} root row(s) created, "
                f"{seeded_phased} phased-rate row(s) created. "
                f"Total rows in DB: {StatutoryRate.objects.count()}."
            )
        )
