"""How each organisation is staffed.

The field defaults to MICRO, because that is what a pharmacy signing up in
Rwanda most often is. Applying that default to organisations that already exist
would be wrong in the other direction, so this reads what is already there:
how many people hold an account, whether it has branches, and whether it is a
depot rather than a shop. A place with eight staff and three branches is not
micro whatever the column default says.

Inferred rather than asked because there is nobody to ask during a migration,
and a wrong guess here changes what people see on their next login. The
inference is deliberately conservative — it only calls something small when the
evidence is unambiguous — and any organisation can change it in settings.
"""

from django.db import migrations, models


def infer_size(apps, schema_editor):
    Organization = apps.get_model("iam", "Organization")
    User = apps.get_model("iam", "User")

    for org in Organization.objects.all():
        people = User.objects.filter(organization=org, is_active=True).count()
        branches = Organization.objects.filter(parent=org).count()

        if org.type == "DEPOT" or branches > 0:
            # A depot picks, packs and dispatches; a parent of branches
            # coordinates. Neither is one person with a till.
            size = "ENTERPRISE" if branches > 2 else "MEDIUM"
        elif people <= 2:
            size = "MICRO"
        elif people <= 5:
            size = "SMALL"
        elif people <= 20:
            size = "MEDIUM"
        else:
            size = "ENTERPRISE"

        Organization.objects.filter(pk=org.pk).update(size=size)


def leave_as_is(apps, schema_editor):
    """Nothing to undo: the column goes with the field."""


class Migration(migrations.Migration):

    dependencies = [
        ("iam", "0023_organization_require_coa_before_release"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="size",
            field=models.CharField(
                choices=[
                    ("MICRO", "One or two people, doing everything"),
                    ("SMALL", "A handful of people, roles overlap"),
                    ("MEDIUM", "Distinct roles, one site"),
                    ("ENTERPRISE", "Departments across sites"),
                ],
                default="MICRO",
                help_text=(
                    "How this pharmacy is staffed. Drives navigation, the home screen, "
                    "and how many people an approval can require — never what the "
                    "system can do."
                ),
                max_length=12,
            ),
        ),
        migrations.RunPython(infer_size, leave_as_is),
    ]
