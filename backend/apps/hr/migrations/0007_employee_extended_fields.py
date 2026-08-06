# Hand-written migration — adds the Finacle-grade R/O/C employee fields for the
# People module (Phase 9). Every field is optional so existing rows continue to
# validate; the new columns are filled in by HR through the employee create/edit
# screens as the operator enriches each profile.
#
# - gender / dob: identity (drives annual-leave entitlement per Law 66/2018 §55)
# - photo:        badge/portal
# - contract_end: fixed-term contract (CDD) end; CDI (permanent) stays blank
# - probation_end:auto-confirmation trigger
# - pay_group:    classification for default salary structure
# - pay_frequency:MONTHLY (default) / FORTNIGHTLY
# - tin:          Rwanda Revenue Authority TIN
# - supervisor:   self-FK for senior oversight / approval routing

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0006_leaverequest_attendancelog_shiftroster'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='gender',
            field=models.CharField(blank=True, default='', help_text="M / F / Other — used for headcount reporting and pension scheme flags.", max_length=10),
        ),
        migrations.AddField(
            model_name='employee',
            name='dob',
            field=models.DateField(blank=True, help_text="Date of birth — drives annual-leave entitlement (Law 66/2018 §55: 25 days if ≥55y).", null=True),
        ),
        migrations.AddField(
            model_name='employee',
            name='photo',
            field=models.URLField(blank=True, default='', help_text="URL of the employee's profile photo (badge)."),
        ),
        migrations.AddField(
            model_name='employee',
            name='probation_end',
            field=models.DateField(blank=True, help_text='Last day of the probation period (auto-confirmation trigger).', null=True),
        ),
        migrations.AddField(
            model_name='employee',
            name='contract_end',
            field=models.DateField(blank=True, help_text='End date of a fixed-term contract (CDD); blank for permanent (CDI).', null=True),
        ),
        migrations.AddField(
            model_name='employee',
            name='pay_group',
            field=models.CharField(blank=True, default='', help_text='Salary band — pharmacist, technician, cashier, driver, manager. Drives default salary structure.', max_length=20),
        ),
        migrations.AddField(
            model_name='employee',
            name='pay_frequency',
            field=models.CharField(blank=True, default='MONTHLY', help_text='Pay period — MONTHLY (Law 66/2018 default) or FORTNIGHTLY.', max_length=10),
        ),
        migrations.AddField(
            model_name='employee',
            name='tin',
            field=models.CharField(blank=True, default='', help_text='RRA TIN — Rwanda tax-identification number; printed on annual PIT summaries.', max_length=30),
        ),
        migrations.AddField(
            model_name='employee',
            name='supervisor',
            field=models.ForeignKey(blank=True, help_text='Direct manager — used by the approvals engine for leave / loan routing.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='hr.employee'),
        ),
    ]
