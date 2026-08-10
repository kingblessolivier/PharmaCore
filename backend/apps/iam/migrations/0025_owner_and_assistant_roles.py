"""The two roles a small pharmacy is missing.

The role list was written for an organisation with departments: a procurement
officer, a warehouse clerk, a dispatcher, an accountant, an HR manager. A
two-person pharmacy has none of those. It has a person who owns the business
and a person who runs the counter — and often they are the same person.

Nothing was available to describe either of them. The nearest fit was
ORG_ADMIN, which grants everything including creating organisations and
impersonating users, so a pharmacy owner was being handed system-administration
powers in order to see their own takings.

Two bundles, named after what the person actually is:

**PHARMACY_OWNER** — the business. Money in and out, what to buy, what it is
worth, who works here. Not the system: no impersonation, no creating other
organisations.

**PHARMACY_ASSISTANT** — the counter, under a pharmacist's supervision. Sell,
look up stock, serve customers. No dispensing of prescription-only medicines
and no voiding a sale, because Rwandan Good Pharmacy Practice puts both under
the supervising pharmacist.

PHARMACIST is left as it is: it already describes the professional correctly.
The point of these is that one person can hold PHARMACY_OWNER *and* PHARMACIST
and be one user with two workspaces, rather than two accounts.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import migrations

ROLES = [
    (
        "PHARMACY_OWNER",
        "Pharmacy Owner",
        "Owns the business: money, purchasing, performance and staff. "
        "Not a system administrator.",
        # A ceiling, not a blank cheque. An owner signing off their own
        # purchasing is normal at this size; signing off an unbounded amount
        # with nobody else in the building is not. Raised in settings by
        # somebody who has thought about it.
        Decimal("5000000.00"),
        [
            "catalog.view",
            "catalog.manage",
            "inventory.view",
            "inventory.adjust",
            "inventory.count",
            "order.create",
            "order.approve",
            "order.receive",
            "order.pay",
            "finance.view",
            "finance.manage",
            "user.manage",
            "audit.view",
            "sale.create",
            "sale.void",
            "sale.return",
            "drawer.open",
            "drawer.close",
        ],
    ),
    (
        "PHARMACY_ASSISTANT",
        "Pharmacy Assistant",
        "Serves at the counter under a pharmacist's supervision: sells, looks up "
        "stock, handles customers.",
        Decimal("0.00"),
        [
            "sale.create",
            "sale.return",
            "drawer.open",
            "drawer.close",
            "catalog.view",
            "inventory.view",
        ],
    ),
]


def seed(apps, schema_editor):  # type: ignore[no-untyped-def]
    Role = apps.get_model("iam", "Role")
    Permission = apps.get_model("iam", "Permission")

    for code, name, description, limit, permission_codes in ROLES:
        role, _ = Role.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": description, "approval_limit": limit},
        )
        # `filter` rather than `get`: a permission this bundle names but the
        # catalogue does not have is a mistake to notice later, not a reason to
        # fail a migration halfway and leave the roles half-built.
        role.permissions.set(Permission.objects.filter(code__in=permission_codes))


def unseed(apps, schema_editor):  # type: ignore[no-untyped-def]
    apps.get_model("iam", "Role").objects.filter(
        code__in=[code for code, *_ in ROLES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("iam", "0024_organization_size")]
    operations = [migrations.RunPython(seed, unseed)]
