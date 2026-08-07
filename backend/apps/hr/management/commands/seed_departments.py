"""Guarantee every active organisation has the Finance + HR departments.

Idempotent — uses ``get_or_create`` on ``(organization, code)``. The Finance and
HR departments are the system-defined cost-centre anchors for two of our most
important flows (GL postings on the Finance side; payroll + leave approval on
the HR side), and a fresh org that signs in should not have to wait until a
user manually creates them before the Finance cockpit or payroll screen works.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.iam.models import Department, Organization

# A department that the rest of the app expects to exist. Anything else (Pharmacy
# Dispensing, Logistics, etc.) can be added by the org admin via the IAM UI.
CANONICAL_DEPARTMENTS = [
    ("FINANCE", "Finance & Accounting"),
    ("HR", "Human Resources"),
]


class Command(BaseCommand):
    help = "Seed canonical (FINANCE, HR) departments for every active organisation."

    def handle(self, *args: Any, **options: Any) -> None:
        orgs = Organization.objects.filter(is_active=True)
        created = 0
        for org in orgs:
            for code, name in CANONICAL_DEPARTMENTS:
                _, was_new = Department.objects.get_or_create(
                    organization=org,
                    code=code,
                    defaults={"name": name},
                )
                if was_new:
                    created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Department seed complete — {orgs.count()} organisation(s), "
                f"{created} new department row(s)."
            )
        )
