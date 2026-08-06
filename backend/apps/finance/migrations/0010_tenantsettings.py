"""F4.3 — TenantSettings first-class data (ADR-014).

Per-tenant configuration (costing method, FX provider, pay period,
statutory remittance day, PIT filing deadline) lives in the DB, not in
code. There is exactly one row per organization, lazily created the
first time :func:`apps.finance.services.tenant_settings_for` is called
for a new tenant.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    # Depends on 0006 (skip 0007/0008 which are untracked WIP from a sibling
    # branch). Forward-compatible: adds a new table; existing rows untouched.
    dependencies = [
        ("iam", "0017_user_tin_payroll_email_reports_to"),
        ("finance", "0009_journalentry_uniq_reference_per_org"),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("base_currency", models.CharField(default="RWF", max_length=3)),
                ("fx_provider", models.CharField(blank=True, default="", max_length=30)),
                (
                    "costing_method",
                    models.CharField(
                        choices=[
                            ("WAC", "Weighted average cost"),
                            ("FEFO_LOT", "FEFO at the lot level (batch cost)"),
                        ],
                        default="FEFO_LOT",
                        max_length=10,
                    ),
                ),
                (
                    "pay_period",
                    models.CharField(
                        choices=[
                            ("DAILY", "Daily"),
                            ("WEEKLY", "Weekly"),
                            ("FORTNIGHTLY", "Fortnightly"),
                            ("MONTHLY", "Monthly"),
                        ],
                        default="MONTHLY",
                        max_length=12,
                    ),
                ),
                ("statutory_remittance_day", models.PositiveSmallIntegerField(default=15)),
                ("pit_filing_deadline_month", models.PositiveSmallIntegerField(default=3)),
                ("pit_filing_deadline_day", models.PositiveSmallIntegerField(default=31)),
                ("default_country", models.CharField(default="RW", max_length=2)),
                ("timezone", models.CharField(default="Africa/Kigali", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tenant_settings",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["organization__name"],
            },
        ),
    ]   # fmt: skip
