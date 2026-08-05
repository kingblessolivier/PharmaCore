"""Seed the permission catalogue (resource × action) and assign role bundles.

Idempotent: safe to re-run. SYS_ADMIN is intentionally left unassigned — it holds
every permission implicitly (see User.has_permission)."""

from __future__ import annotations

from django.db import migrations

# (resource, action, description)
PERMISSIONS = [
    ("sale", "create", "Ring up and complete a sale"),
    ("sale", "void", "Void a completed sale"),
    ("sale", "return", "Process a customer return / credit note"),
    ("sale", "dispense", "Dispense prescription / controlled items"),
    ("drawer", "open", "Open a till drawer"),
    ("drawer", "close", "Cash up and close a drawer"),
    ("catalog", "view", "View the product catalog"),
    ("catalog", "manage", "Create and edit products"),
    ("inventory", "view", "View stock and batches"),
    ("inventory", "intake", "Receive supplier intake (depot)"),
    ("inventory", "adjust", "Adjust or write off stock"),
    ("inventory", "count", "Run stock counts"),
    ("order", "create", "Place a purchase order"),
    ("order", "approve", "Approve and ship an order"),
    ("order", "receive", "Receive an order (GRN)"),
    ("order", "pay", "Record B2B payment / settlement"),
    ("organization", "manage", "Create and edit organizations"),
    ("company", "manage", "Create and edit companies"),
    ("user", "manage", "Create and manage users and roles"),
    ("user", "view_as", "View-as / impersonate a user"),
    ("finance", "view", "View finance (aging, settlement)"),
    ("finance", "manage", "Manage finance operations"),
    ("audit", "view", "View the audit log"),
]

# role code -> permission codes it grants
ROLE_PERMS = {
    "CASHIER": ["sale.create", "sale.return", "drawer.open", "drawer.close", "catalog.view"],
    "PHARMACIST": [
        "sale.create", "sale.void", "sale.return", "sale.dispense",
        "drawer.open", "drawer.close", "catalog.view", "inventory.view",
        "order.create", "order.receive",
    ],
    "WAREHOUSE_CLERK": [
        "inventory.view", "inventory.intake", "inventory.adjust", "inventory.count",
        "order.receive",
    ],
    "DISPATCHER": ["order.approve", "inventory.view"],
    "DRIVER": ["order.receive"],
    "ACCOUNTANT": ["finance.view", "finance.manage", "order.pay", "audit.view"],
    "INSURANCE_CLERK": ["catalog.view", "finance.view"],
    "HR_MANAGER": ["user.manage"],
    "ORG_ADMIN": [
        "sale.create", "sale.void", "sale.return", "sale.dispense",
        "drawer.open", "drawer.close", "catalog.view", "catalog.manage",
        "inventory.view", "inventory.intake", "inventory.adjust", "inventory.count",
        "order.create", "order.approve", "order.receive", "order.pay",
        "organization.manage", "company.manage", "user.manage", "user.view_as",
        "finance.view", "finance.manage", "audit.view",
    ],
}


def seed(apps, schema_editor):
    Permission = apps.get_model("iam", "Permission")
    Role = apps.get_model("iam", "Role")
    for resource, action, desc in PERMISSIONS:
        Permission.objects.update_or_create(
            code=f"{resource}.{action}",
            defaults={"resource": resource, "action": action, "description": desc},
        )
    by_code = {p.code: p for p in Permission.objects.all()}
    for role_code, perm_codes in ROLE_PERMS.items():
        role = Role.objects.filter(code=role_code).first()
        if not role:
            continue
        role.permissions.add(*[by_code[c] for c in perm_codes if c in by_code])


def unseed(apps, schema_editor):
    apps.get_model("iam", "Permission").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("iam", "0009_permission_role_permissions")]
    operations = [migrations.RunPython(seed, unseed)]
