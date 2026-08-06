"""F1.2 — ADR-011 idempotency contract on JournalEntry.

Every JournalPostingService handler is required to be idempotent on
(source_doc, source_line). For top-level journal entries that means a unique
(organization, reference_type, reference_id) per posted entry — re-posting the
same source doc must return the existing entry, not create a duplicate.

Conditional (reference_type must be non-empty) so that manual / adjustment
postings which legitimately share an empty reference are still allowed.
"""

import django.db.models.deletion
import django.db.models.expressions
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Skip 0007/0008 — those are untracked WIP from another branch; on
        # the staging merge they will be resolved by their owner. The latest
        # clean anchor on origin/staging is 0006.
        ("finance", "0006_supplierbill_tax_class_supplierbill_vat_amount_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.UniqueConstraint(
                models.F("organization"),
                models.F("reference_type"),
                models.F("reference_id"),
                condition=models.Q(reference_type__gt=""),
                name="uniq_journal_reference_per_org",
            ),
        ),
    ]