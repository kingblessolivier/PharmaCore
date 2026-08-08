"""Post the month-end entries that nothing else triggers.

Depreciation and the IAS 2 stock provision are not caused by a user action — they
are caused by a month ending. Before this command they were simply never posted,
so assets sat at cost forever and expiring stock stayed on the balance sheet at
full value.

Both postings are idempotent on their period reference, so running this twice for
the same month is safe and running it late is safe too.

    python manage.py run_month_end --as-of 2026-06-30
    python manage.py run_month_end --organization 3 --dry-run
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.finance.accruals import run_schedules, schedule_summary
from apps.finance.operations import (
    current_provision_balance,
    depreciation_schedule,
    post_expiry_provision,
    run_depreciation,
)
from apps.iam.models import Organization


class Command(BaseCommand):
    help = "Post month-end depreciation and the expiry provision for one or all organizations."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--as-of",
            dest="as_of",
            help="Any date inside the month to post (default: today).",
        )
        parser.add_argument(
            "--organization",
            dest="organization",
            type=int,
            help="Restrict to one organization id (default: every organization).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be posted without writing anything.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        as_of = timezone.localdate()
        if options.get("as_of"):
            try:
                as_of = date.fromisoformat(options["as_of"])
            except ValueError as exc:
                raise CommandError("--as-of must be an ISO date (YYYY-MM-DD).") from exc

        organizations = Organization.objects.all()
        if options.get("organization"):
            organizations = organizations.filter(pk=options["organization"])
            if not organizations.exists():
                raise CommandError(f"No organization with id {options['organization']}.")

        dry_run = bool(options.get("dry_run"))
        for organization in organizations:
            self.stdout.write(self.style.MIGRATE_HEADING(organization.name))

            schedule = depreciation_schedule(organization, as_of=as_of)
            total = sum((charge for _, charge in schedule), start=Decimal("0"))
            if dry_run:
                self.stdout.write(
                    f"  depreciation: {len(schedule)} asset(s), {total} would be charged"
                )
            else:
                entry = run_depreciation(organization=organization, as_of=as_of)
                self.stdout.write(
                    f"  depreciation: {entry.entry_number} ({total})"
                    if entry
                    else "  depreciation: nothing to charge"
                )

            if dry_run:
                self.stdout.write(f"  provision carried: {current_provision_balance(organization)}")
            else:
                entry = post_expiry_provision(organization=organization, as_of=as_of)
                self.stdout.write(
                    f"  expiry provision: {entry.entry_number}"
                    if entry
                    else "  expiry provision: already at the required level"
                )

            # Accruals and prepayments: a cost belongs to the months it was
            # incurred in, not the month it happened to be billed.
            if dry_run:
                summary = schedule_summary(organization, as_of=as_of)
                self.stdout.write(
                    f"  schedules: {len(summary['overdue'])} overdue, "
                    f"prepaid {summary['prepayments_remaining']}, "
                    f"accrued {summary['accruals_remaining']}"
                )
            else:
                result = run_schedules(organization=organization, as_of=as_of)
                self.stdout.write(
                    f"  schedules: {result['runs']} month(s) posted, total {result['total']}"
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — nothing was posted."))
