"""F4.4 — Import opening balances for one organization from a JSON file.

This is the one-shot onboarding / migration command. The file format is a
JSON document of the shape::

    {
        "organization": "Acme Pharmacy Ltd",
        "rows": [
            {"kind": "GL_TRIAL_BALANCE", "reference_key": "1000-cash",
             "payload": {"account_code": "1000", "debit": "1500000.00", "credit": "0"}},
            {"kind": "AR_AGING", "reference_key": "AR-INV-0001",
             "payload": {"partner_ref": "BPH", "invoice_number": "INV-001",
                         "amount": "120000.00", "aging_bucket": "d30"}},
            {"kind": "STOCK_BATCH", "reference_key": "AMOX-2024-A",
             "payload": {"product_code": "AMOX500", "batch_number": "B-2024-A",
                         "expiry_date": "2026-12-31", "quantity": 240,
                         "unit_cost": "450.00"}}
        ]
    }

Validation runs first and fails fast on tie-out errors (unbalanced trial
balance, unknown account codes / product codes / employee ids, bad aging
buckets, duplicate keys). On success, the rows are persisted as drafts
or, with ``--apply``, promoted to applied — which writes the GL opening
journal, creates inventory batches, etc., all in a single transaction.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.finance.services import (
    OpeningBalanceValidationError,
    import_opening_balances,
)
from apps.iam.models import Organization


class Command(BaseCommand):
    help = "Import opening balances (trial balance, AR/AP aging, inventory, leave) from JSON."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "file",
            type=Path,
            help="Path to a JSON file with {organization, rows}.",
        )
        parser.add_argument(
            "--org",
            dest="organization",
            default=None,
            help="Override the organization name (otherwise read from the file).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Promote drafts to applied (writes GL journal, creates batches).",
        )

    def handle(self, *args, **options) -> None:
        path: Path = options["file"]
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {path}: {exc}") from exc

        org_name = options["organization"] or data.get("organization")
        if not org_name:
            raise CommandError(
                "Organization name not provided — pass --org or include 'organization' in the JSON."
            )
        try:
            organization = Organization.objects.get(name=org_name)
        except Organization.DoesNotExist as exc:
            raise CommandError(f"Unknown organization {org_name!r}.") from exc

        rows = data.get("rows", [])
        if not isinstance(rows, list):
            raise CommandError("'rows' must be a JSON array of row objects.")

        try:
            saved = import_opening_balances(
                organization=organization,
                rows=rows,
                apply=bool(options["apply"]),
                user=None,
            )
        except OpeningBalanceValidationError as exc:
            self.stdout.write(self.style.ERROR("Validation failed:"))
            for err in exc.errors:
                self.stdout.write(self.style.ERROR(f"  · {err}"))
            raise CommandError("Refusing to import — fix the errors and re-run.") from exc

        kind_counts: dict[str, int] = {}
        for row in saved:
            kind_counts[row.kind] = kind_counts.get(row.kind, 0) + 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(saved)} opening-balance row(s) for {organization.name} "
                f"(applied={bool(options['apply'])}, at={timezone.now():%Y-%m-%d %H:%M:%S})."
            )
        )
        for kind, count in sorted(kind_counts.items()):
            self.stdout.write(f"  · {kind}: {count}")
