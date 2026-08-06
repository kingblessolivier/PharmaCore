"""Seed the standard Chart of Accounts for every active organisation that doesn't
already have one.

Idempotent — re-running has no effect. This is the bootstrap counterpart to
``apps.finance.services.ensure_default_accounts`` (which is called lazily when a
specific account is needed); running this command up front means the Finance page
is usable from day one — the leader's cockpit can show "Cash & Bank", "Sales
Revenue" etc. with real balances (even if those balances start at 0).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.finance.services import ensure_default_accounts
from apps.iam.models import Organization


class Command(BaseCommand):
    help = "Seed the standard Chart of Accounts (12 control accounts) for every active organisation."

    def handle(self, *args, **options) -> None:
        orgs = Organization.objects.filter(is_active=True)
        total_orgs = orgs.count()
        total_accounts = 0
        for org in orgs:
            accounts = ensure_default_accounts(org)
            total_accounts += len(accounts)
            self.stdout.write(
                f"  · {org.name}: {len(accounts)} accounts ready"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete — {total_orgs} organisation(s), "
                f"{total_accounts} control account rows ensured."
            )
        )
