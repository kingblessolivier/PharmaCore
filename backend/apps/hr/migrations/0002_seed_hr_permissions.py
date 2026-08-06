"""Seed HR permission codes and grant them to HR_MANAGER / ORG_ADMIN. Idempotent;
additive only — does not touch iam's own seed."""

from __future__ import annotations

from django.db import migrations

PERMISSIONS = [
    ("employee", "view", "View employee records"),
    ("employee", "manage", "Create and edit employee records"),
    ("employee", "terminate", "Request an employee's termination"),
]

ROLE_GRANTS = {
    "HR_MANAGER": ["employee.view", "employee.manage", "employee.terminate"],
    "ORG_ADMIN": ["employee.view", "employee.manage", "employee.terminate"],
}


def seed(apps, schema_editor):
    Permission = apps.get_model("iam", "Permission")
    Role = apps.get_model("iam", "Role")
    for resource, action, desc in PERMISSIONS:
        Permission.objects.update_or_create(
            code=f"{resource}.{action}",
            defaults={"resource": resource, "action": action, "description": desc},
        )
    by_code = {p.code: p for p in Permission.objects.filter(resource="employee")}
    for role_code, perm_codes in ROLE_GRANTS.items():
        role = Role.objects.filter(code=role_code).first()
        if not role:
            continue
        role.permissions.add(*[by_code[c] for c in perm_codes if c in by_code])


def unseed(apps, schema_editor):
    apps.get_model("iam", "Permission").objects.filter(resource="employee").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hr", "0001_initial"),
        ("iam", "0010_seed_permissions"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
