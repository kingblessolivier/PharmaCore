"""Seed permission codes for the approvals engine and grant them to the roles
that already exist (ACCOUNTANT, HR_MANAGER decide; ORG_ADMIN senior-oversight
manages/reassigns). Idempotent; additive only — does not touch iam's own seed."""

from __future__ import annotations

from django.db import migrations

PERMISSIONS = [
    ("approval", "decide", "Claim and decide a pending approval"),
    ("approval", "manage", "Senior oversight: see all approvals, reassign a claim"),
]

ROLE_GRANTS = {
    "ACCOUNTANT": ["approval.decide"],
    "HR_MANAGER": ["approval.decide"],
    "ORG_ADMIN": ["approval.decide", "approval.manage"],
}


def seed(apps, schema_editor):
    Permission = apps.get_model("iam", "Permission")
    Role = apps.get_model("iam", "Role")
    for resource, action, desc in PERMISSIONS:
        Permission.objects.update_or_create(
            code=f"{resource}.{action}",
            defaults={"resource": resource, "action": action, "description": desc},
        )
    by_code = {p.code: p for p in Permission.objects.filter(resource="approval")}
    for role_code, perm_codes in ROLE_GRANTS.items():
        role = Role.objects.filter(code=role_code).first()
        if not role:
            continue
        role.permissions.add(*[by_code[c] for c in perm_codes if c in by_code])


def unseed(apps, schema_editor):
    apps.get_model("iam", "Permission").objects.filter(resource="approval").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("approvals", "0001_initial"),
        ("iam", "0010_seed_permissions"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
