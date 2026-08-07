"""Add disposal metadata fields to FixedAsset.

The disposal flow records the date, proceeds, and reason when an asset is
written off / sold. These fields are nullable on the model because a row's
disposal fields only matter *after* the dispose action runs.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0013_paymentrun_paymentrunline_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="fixedasset",
            name="disposal_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="fixedasset",
            name="disposal_amount",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="fixedasset",
            name="disposal_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]