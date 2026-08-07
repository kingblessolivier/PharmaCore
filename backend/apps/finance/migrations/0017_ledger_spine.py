"""The ledger spine: cost centres, budgets with lines, and the close checklist.

The old ``Budget`` model was itself a budget *line* — one account, one department,
one year, one amount — so it is renamed to ``BudgetLine`` rather than dropped, and
the name ``Budget`` is reused for the header the lines now hang from. Renaming
keeps every existing row; a delete-and-recreate would have thrown the plans away
to save a few lines of migration.

``actual_amount`` is removed here and is not replaced. Actuals are read from the
ledger from now on — see ``apps.finance.budgeting.budget_variance``.
"""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0016_backfill_account_classification"),
        ("iam", "0017_user_tin_payroll_email_reports_to"),
    ]

    operations = [
        # 1. Free the `Budget` name, keeping the rows.
        migrations.RenameModel(old_name="Budget", new_name="BudgetLine"),
        # 2. The analysis dimension.
        migrations.CreateModel(
            name="CostCentre",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("code", models.CharField(max_length=20)),
                ("name", models.CharField(max_length=150)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("BRANCH", "Branch / site"),
                            ("DEPARTMENT", "Department"),
                            ("FUNCTION", "Function"),
                            ("PROJECT", "Project"),
                        ],
                        default="DEPARTMENT",
                        max_length=12,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cost_centres",
                        to="iam.organization",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="finance.costcentre",
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="iam.department",
                    ),
                ),
                (
                    "branch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="iam.organization",
                    ),
                ),
                (
                    "manager",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="iam.user",
                    ),
                ),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.AddConstraint(
            model_name="costcentre",
            constraint=models.UniqueConstraint(
                fields=("organization", "code"), name="uniq_cost_centre_code_per_org"
            ),
        ),
        migrations.AddIndex(
            model_name="costcentre",
            index=models.Index(
                fields=["organization", "is_active"], name="finance_cos_organiz_aa737b_idx"
            ),
        ),
        # 3. The budget header, reusing the freed name.
        migrations.CreateModel(
            name="Budget",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=150)),
                ("financial_year", models.PositiveIntegerField(default=2026)),
                ("year_starts_month", models.PositiveSmallIntegerField(default=1)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("APPROVED", "Approved"),
                            ("LOCKED", "Locked"),
                            ("ARCHIVED", "Archived"),
                        ],
                        default="DRAFT",
                        max_length=10,
                    ),
                ),
                ("notes", models.TextField(blank=True, default="")),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="budget_plans",
                        to="iam.organization",
                    ),
                ),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="iam.user",
                    ),
                ),
            ],
            options={
                "db_table": "finance_budget_plan",
                "ordering": ["-financial_year", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="budget",
            constraint=models.UniqueConstraint(
                fields=("organization", "financial_year", "name"), name="uniq_budget_per_year"
            ),
        ),
        # 4. The close checklist.
        migrations.CreateModel(
            name="PeriodTask",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("code", models.CharField(max_length=40)),
                ("title", models.CharField(max_length=200)),
                ("description", models.CharField(blank=True, default="", max_length=400)),
                ("sequence", models.PositiveSmallIntegerField(default=0)),
                ("is_blocking", models.BooleanField(default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("DONE", "Done"),
                            ("WAIVED", "Waived"),
                        ],
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                (
                    "period",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="finance.accountingperiod",
                    ),
                ),
                (
                    "completed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="iam.user",
                    ),
                ),
            ],
            options={"ordering": ["sequence", "id"]},
        ),
        migrations.AddConstraint(
            model_name="periodtask",
            constraint=models.UniqueConstraint(
                fields=("period", "code"), name="uniq_period_task_code"
            ),
        ),
        # 5. Tag every posting with its origin and its cost centre.
        migrations.AddField(
            model_name="journalentry",
            name="source_module",
            field=models.CharField(
                choices=[
                    ("SALES", "Sales & dispensing"),
                    ("PROCUREMENT", "Procurement & imports"),
                    ("INVENTORY", "Inventory & stock"),
                    ("PAYROLL", "Payroll & people"),
                    ("TREASURY", "Treasury & banking"),
                    ("TAX", "Tax & statutory"),
                    ("CLOSE", "Period close & adjustments"),
                    ("MANUAL", "Manual journal"),
                ],
                db_index=True,
                default="MANUAL",
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="journalline",
            name="cost_centre",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="journal_lines",
                to="finance.costcentre",
            ),
        ),
        # 6. Reshape the renamed rows into budget lines.
        migrations.RemoveConstraint(model_name="budgetline", name="uniq_budget_line"),
        migrations.RenameField(
            model_name="budgetline", old_name="budgeted_amount", new_name="amount"
        ),
        migrations.RemoveField(model_name="budgetline", name="actual_amount"),
        migrations.AddField(
            model_name="budgetline",
            name="budget",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lines",
                to="finance.budget",
            ),
        ),
        migrations.AddField(
            model_name="budgetline",
            name="cost_centre",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="budget_lines",
                to="finance.costcentre",
            ),
        ),
        migrations.AddField(
            model_name="budgetline",
            name="period_month",
            field=models.PositiveSmallIntegerField(
                blank=True, help_text="1–12, or blank for an annual figure", null=True
            ),
        ),
        migrations.AddField(
            model_name="budgetline",
            name="note",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AlterField(
            model_name="budgetline",
            name="amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AlterField(
            model_name="budgetline",
            name="account",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="finance.account",
            ),
        ),
    ]
