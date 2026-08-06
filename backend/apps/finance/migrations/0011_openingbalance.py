"""F4.4 — OpeningBalance for onboarding + legacy-system migration.

One typed row per import line; ``kind`` selects the payload schema.
Validation runs at service-layer time so an unbalanced trial balance
or unknown product/employee codes are caught before any row is written.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0010_tenantsettings"),
        ("iam", "0017_user_tin_payroll_email_reports_to"),
    ]

    operations = [
        migrations.CreateModel(
            name="OpeningBalance",
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
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("GL_TRIAL_BALANCE", "GL trial balance"),
                            ("AR_AGING", "AR aging"),
                            ("AP_AGING", "AP aging"),
                            ("STOCK_BATCH", "Inventory batch"),
                            ("EMPLOYEE_LEAVE", "Employee leave"),
                        ],
                        max_length=20,
                    ),
                ),
                ("reference_key", models.CharField(max_length=200)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="opening_balances",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["organization", "kind", "reference_key"],
                "indexes": [
                    models.Index(
                        fields=["organization", "kind"],
                        name="idx_ob_org_kind",
                    ),
                    models.Index(
                        fields=["organization", "kind", "applied_at"],
                        name="idx_ob_org_kind_applied",
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="openingbalance",
            constraint=models.UniqueConstraint(
                fields=("organization", "kind", "reference_key"),
                name="uniq_opening_balance_per_org_kind",
            ),
        ),
    ]   # fmt: skip
