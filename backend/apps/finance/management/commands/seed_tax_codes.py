"""Seed the Rwanda VAT tax codes (A/B/C/D) for every active organisation.

Versions are rows, not code: a new Finance Law = one new row with effective_from
set, never a migration. The first invocation backfills all four classes at their
2025-01-01 effective date so a freshly-onboarded org starts with a usable map.
"""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from apps.finance.models import TaxCode
from apps.iam.models import Organization

# (code, description, rate_pct, withholding_pct)
_DEFAULT_CODES: list[tuple[str, str, str, float, float]] = [
    ("A", "Class A — Exempt", "Exempt supplies (e.g. certain medical services).", 0.0, 0.0),
    ("B", "Class B — Standard 18%", "Standard-rated supplies (e.g. cosmetics, sundries).", 18.0, 15.0),
    ("C", "Class C — Zero-rated", "Zero-rated supplies (e.g. medicines, medical supplies).", 0.0, 0.0),
    ("D", "Class D — Special handling", "Special-handling supplies (e.g. exported services).", 18.0, 0.0),
]


class Command(BaseCommand):
    help = "Seed the Rwanda VAT tax codes (A/B/C/D) for every active organisation."

    def handle(self, *args, **options) -> None:
        orgs = Organization.objects.filter(is_active=True)
        total_orgs = orgs.count()
        total_rows = 0

        for org in orgs:
            for code, _label, description, rate_pct, wht_pct in _DEFAULT_CODES:
                _, created = TaxCode.objects.get_or_create(
                    organization=org,
                    code=code,
                    effective_from=date(2025, 1, 1),
                    defaults={
                        "description": description,
                        "rate_pct": rate_pct,
                        "withholding_pct": wht_pct,
                        "is_active": True,
                        "source_reference": "RRA VAT Law 21/2022 + 2025 amendments",
                    },
                )
                if created:
                    total_rows += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded TaxCodes for {total_orgs} active org(s); {total_rows} new rows."
            )
        )
