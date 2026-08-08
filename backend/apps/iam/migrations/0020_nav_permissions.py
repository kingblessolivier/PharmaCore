"""Permissions for the two subsystems that had none, so the nav can gate on capability.

The side nav gates on **role names**, which is why five of eleven roles could not
reach the screens built for their job: a warehouse clerk could not open Inventory,
a dispatcher could not open Distribution, an insurance clerk could not open
Insurance — and all of them landed on the till, because Retail was open to
everyone (audit D7).

Gating on permissions instead needs a permission to gate on. Inventory,
Procurement, Finance, Catalog and People already have theirs. Insurance and
Distribution never did, so they are added here.

``BRANCH_MANAGER`` and ``AUDITOR`` also pick up the read codes for the subsystems
they oversee. Note what a branch manager still does **not** get — ``sale.dispense``,
``inventory.adjust``, ``catalog.manage``. That is R1: overseeing a pharmacist does
not make you one.
"""

from __future__ import annotations

from django.db import migrations

PERMISSIONS = [
    ("insurance", "view", "View schemes, member policies and claims"),
    ("insurance", "manage", "Build, submit and adjudicate claims"),
    ("distribution", "view", "View depot listings, B2B orders and deliveries"),
    ("distribution", "manage", "Publish listings, raise and fulfil B2B orders"),
]

GRANTS = {
    "INSURANCE_CLERK": ["insurance.view", "insurance.manage"],
    "PHARMACIST": ["insurance.view", "insurance.manage", "distribution.view"],
    "ORG_ADMIN": [
        "insurance.view",
        "insurance.manage",
        "distribution.view",
        "distribution.manage",
    ],
    "BRANCH_MANAGER": [
        "insurance.view",
        "distribution.view",
        "distribution.manage",
        "procurement.view",
        "employee.view",
    ],
    "AUDITOR": ["insurance.view", "distribution.view", "procurement.view", "employee.view"],
    # A dispatcher's whole job is moving goods out of the depot.
    "DISPATCHER": ["distribution.view", "distribution.manage"],
    # A driver sees deliveries — and only deliveries.
    "DRIVER": ["distribution.view"],
    "WAREHOUSE_CLERK": ["distribution.view"],
    "ACCOUNTANT": ["insurance.view", "distribution.view"],
    "PROCUREMENT_OFFICER": ["distribution.view"],
}


def seed(apps, schema_editor):  # type: ignore[no-untyped-def]
    Permission = apps.get_model("iam", "Permission")
    Role = apps.get_model("iam", "Role")

    for resource, action, description in PERMISSIONS:
        Permission.objects.update_or_create(
            code=f"{resource}.{action}",
            defaults={"resource": resource, "action": action, "description": description},
        )
    by_code = {p.code: p for p in Permission.objects.all()}
    for role_code, codes in GRANTS.items():
        role = Role.objects.filter(code=role_code).first()
        if role is None:
            continue
        role.permissions.add(*[by_code[c] for c in codes if c in by_code])


def unseed(apps, schema_editor):  # type: ignore[no-untyped-def]
    apps.get_model("iam", "Permission").objects.filter(
        resource__in=["insurance", "distribution"]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("iam", "0019_seed_approval_limits"), ("procurement", "0002_seed_procurement_rbac")]
    operations = [migrations.RunPython(seed, unseed)]
