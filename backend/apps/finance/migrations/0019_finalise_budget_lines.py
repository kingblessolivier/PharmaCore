"""Drop the columns the budget header now owns, and lock the line shape in.

Runs after the backfill so `budget` is populated before it becomes non-nullable,
and so `organization` / `financial_year` are still readable while the headers are
being built.
"""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0018_migrate_budget_lines")]

    operations = [
        migrations.AlterField(
            model_name="budgetline",
            name="budget",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lines",
                to="finance.budget",
            ),
        ),
        # These now live on the header (organization, financial_year) or are
        # superseded by the cost-centre dimension (department).
        migrations.RemoveField(model_name="budgetline", name="organization"),
        migrations.RemoveField(model_name="budgetline", name="department"),
        migrations.RemoveField(model_name="budgetline", name="financial_year"),
        migrations.RemoveField(model_name="budgetline", name="created_at"),
        migrations.AlterModelOptions(
            name="budgetline", options={"ordering": ["account__code", "period_month"]}
        ),
        migrations.AddConstraint(
            model_name="budgetline",
            constraint=models.UniqueConstraint(
                fields=("budget", "account", "cost_centre", "period_month"),
                name="uniq_budget_line_slice",
            ),
        ),
        migrations.AddIndex(
            model_name="budgetline",
            index=models.Index(fields=["budget", "account"], name="finance_bud_budget__153df1_idx"),
        ),
    ]
