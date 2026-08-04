"""Seed the base RBAC roles (data model docs/02-data-model.md)."""

from __future__ import annotations

from django.db import migrations

ROLES = [
    ("SYS_ADMIN", "System Administrator"),
    ("ORG_ADMIN", "Organization Administrator"),
    ("PHARMACIST", "Pharmacist"),
    ("CASHIER", "Cashier"),
    ("WAREHOUSE_CLERK", "Warehouse Clerk"),
    ("DISPATCHER", "Dispatcher"),
    ("INSURANCE_CLERK", "Insurance Clerk"),
    ("ACCOUNTANT", "Accountant"),
    ("HR_MANAGER", "HR Manager"),
    ("DRIVER", "Driver"),
]


def seed_roles(apps, schema_editor):  # type: ignore[no-untyped-def]
    Role = apps.get_model("iam", "Role")
    for code, name in ROLES:
        Role.objects.get_or_create(code=code, defaults={"name": name})


def unseed_roles(apps, schema_editor):  # type: ignore[no-untyped-def]
    Role = apps.get_model("iam", "Role")
    Role.objects.filter(code__in=[c for c, _ in ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [("iam", "0001_initial")]
    operations = [migrations.RunPython(seed_roles, unseed_roles)]
