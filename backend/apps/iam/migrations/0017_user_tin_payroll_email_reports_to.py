# Hand-written migration — adds three R/O/C fields to the User model so it can
# carry the Rwanda PAYE/PIT data the Finance + HR modules need:
#   - tin:           Rwanda Revenue Authority TIN (printed on annual PIT summaries)
#   - payroll_email: secondary mailbox for payslip/PDF delivery
#   - reports_to:    self-FK for senior-oversight escalation in the approvals engine

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iam', '0016_apikey'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='tin',
            field=models.CharField(blank=True, default='', help_text='Rwanda Revenue Authority Tax Identification Number — printed on annual PIT summaries.', max_length=30),
        ),
        migrations.AddField(
            model_name='user',
            name='payroll_email',
            field=models.EmailField(blank=True, default='', help_text='Optional secondary email where payslips/PDFs are delivered, in addition to the login email.', max_length=254),
        ),
        migrations.AddField(
            model_name='user',
            name='reports_to',
            field=models.ForeignKey(blank=True, help_text="The user's supervisor — used for senior oversight and approval escalation.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='direct_reports', to=settings.AUTH_USER_MODEL),
        ),
    ]
