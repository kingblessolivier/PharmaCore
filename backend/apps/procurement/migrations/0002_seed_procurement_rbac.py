"""Seed the procurement permission codes, the PROCUREMENT_OFFICER role, and the
role bundles that make the buy side usable out of the box.

Idempotent and additive — it never removes a grant another migration made.
Approving a requisition/PO/invoice deliberately needs ``approval.decide`` (the
approvals engine), not a procurement permission: that is what keeps claim-to-lock
and no-self-approval honest.
"""

from __future__ import annotations

from django.db import migrations

PERMISSIONS = [
    ("procurement", "view", "View requisitions, purchase orders, receipts and supplier invoices"),
    ("procurement", "manage", "Raise and edit requisitions, RFQs, purchase orders and notes"),
    ("procurement", "receive", "Book goods in against a purchase order (GRN)"),
    ("procurement", "invoice", "Register supplier invoices and run the 3-way match"),
]

ROLE_GRANTS = {
    "PROCUREMENT_OFFICER": [
        "procurement.view",
        "procurement.manage",
        "procurement.receive",
        "procurement.invoice",
        "catalog.view",
        "inventory.view",
    ],
    "ORG_ADMIN": [
        "procurement.view",
        "procurement.manage",
        "procurement.receive",
        "procurement.invoice",
    ],
    "ACCOUNTANT": ["procurement.view", "procurement.invoice"],
    "WAREHOUSE_CLERK": ["procurement.view", "procurement.receive"],
    "PHARMACIST": ["procurement.view"],
}


def seed(apps, schema_editor):  # type: ignore[no-untyped-def]
    Permission = apps.get_model("iam", "Permission")
    Role = apps.get_model("iam", "Role")

    Role.objects.get_or_create(
        code="PROCUREMENT_OFFICER", defaults={"name": "Procurement Officer"}
    )
    for resource, action, description in PERMISSIONS:
        Permission.objects.update_or_create(
            code=f"{resource}.{action}",
            defaults={"resource": resource, "action": action, "description": description},
        )
    by_code = {p.code: p for p in Permission.objects.all()}
    for role_code, perm_codes in ROLE_GRANTS.items():
        role = Role.objects.filter(code=role_code).first()
        if not role:
            continue
        role.permissions.add(*[by_code[c] for c in perm_codes if c in by_code])


def unseed(apps, schema_editor):  # type: ignore[no-untyped-def]
    apps.get_model("iam", "Permission").objects.filter(resource="procurement").delete()
    apps.get_model("iam", "Role").objects.filter(code="PROCUREMENT_OFFICER").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0001_initial"),
        ("iam", "0010_seed_permissions"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
