"""Give each role an approval ceiling, and add the roles the business actually has.

Three things happen here, and they belong together because none is useful alone.

**The two missing approval permissions.** ``apps/approvals/views.py`` gates its
claim/decide actions on ``approval.decide`` and reassignment on
``approval.manage``. Neither code was ever seeded, so ``has_permission`` returned
False for everyone except a superuser — the central approvals inbox, which every
subsystem routes payroll runs, credit overrides, purchase orders and write-offs
through, could not be used by any ordinary user. That is the exact inverse of the
D18 hole in the service layer: one let anyone approve, the other let nobody.
Seeding them makes the two-tier check work as intended — ``approval.decide`` is
"may you use the inbox at all", and ``authority.can_decide`` is "may you decide
*this*".

**Limits** (authority.py R2). Until now every role had unbounded authority in
practice, because nothing checked. The figures below are starting points for a
Rwandan pharmacy group in RWF — an owner will tune them in Admin, and that is
expected. What matters is that the *shape* is right: operational staff approve
nothing, supervisors approve routine spend, managers approve a day's trading, and
only the group holds an open ceiling.

**Three missing roles.** The audit (D8, D9) found that ``PROCUREMENT_OFFICER``
gates the whole Procurement app and is not a role anyone can hold, and that there
is no role for a manager at all — so the only way to let a pharmacy owner see
yesterday's margin was to make them ORG_ADMIN, which is also the power to delete
users. ``BRANCH_MANAGER`` and ``AUDITOR`` close that.

Note what ``BRANCH_MANAGER`` does *not* get: ``sale.dispense``,
``inventory.adjust``, ``catalog.manage``. That is R1 — rank does not confer
competence. A branch manager oversees a pharmacist; they do not become one.
``AUDITOR`` is read-only by construction: every code it holds ends in ``.view``.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import migrations

#: role code -> approval ceiling in RWF. None means unlimited.
LIMITS: dict[str, Decimal | None] = {
    "SYS_ADMIN": None,
    "ORG_ADMIN": None,
    # A branch manager signs off a day's ordinary trading, not a capital purchase.
    "BRANCH_MANAGER": Decimal("2000000"),
    # Procurement commits real money to suppliers; above this it is the owner's call.
    "PROCUREMENT_OFFICER": Decimal("5000000"),
    # An accountant processes what is already owed; committing new spend is not
    # their decision, so the ceiling is deliberately modest.
    "ACCOUNTANT": Decimal("10000000"),
    "HR_MANAGER": Decimal("3000000"),
    "PHARMACIST": Decimal("500000"),
    "DISPATCHER": Decimal("500000"),
    # Operational staff approve nothing. Zero is not an insult; it is the point of
    # having an approvals engine.
    "CASHIER": Decimal("0"),
    "WAREHOUSE_CLERK": Decimal("0"),
    "INSURANCE_CLERK": Decimal("0"),
    "DRIVER": Decimal("0"),
    "AUDITOR": Decimal("0"),
}

#: (code, description) — referenced by approvals/views.py, never seeded until now.
NEW_PERMISSIONS = [
    ("approval.decide", "Claim and decide approval requests"),
    ("approval.manage", "Senior oversight — reassign a claimed approval"),
]

#: Who may use the approvals inbox. Fine-grained authority (which *specific*
#: request you may decide) is enforced separately by apps/iam/authority.py.
#:
#: ``PROCUREMENT_OFFICER`` is deliberately absent. ``procurement/migrations/
#: 0002_seed_procurement_rbac.py`` withholds approval rights from the buy side on
#: purpose — the person who raises requisitions and purchase orders must not be
#: able to approve any of them. That is maker-checker, and it is why buying
#: approvals route to a manager rather than back to the buyer.
DECIDERS = [
    "ORG_ADMIN",
    "BRANCH_MANAGER",
    "ACCOUNTANT",
    "HR_MANAGER",
    "PHARMACIST",
    "DISPATCHER",
]
#: Senior oversight — may forward someone else's claim.
OVERSEERS = ["ORG_ADMIN", "BRANCH_MANAGER"]

NEW_ROLES = [
    (
        "BRANCH_MANAGER",
        "Branch Manager",
        "Runs one pharmacy or depot: oversight of the team, the branch's numbers, "
        "and approval of routine spend. Explicitly not a dispensing role.",
        [
            "catalog.view",
            "inventory.view",
            "finance.view",
            "order.create",
            "order.approve",
            "order.receive",
            "audit.view",
        ],
    ),
    (
        "PROCUREMENT_OFFICER",
        "Procurement Officer",
        "Raises requisitions and purchase orders, manages suppliers and quotes.",
        [
            "catalog.view",
            "inventory.view",
            "order.create",
            "order.approve",
            "order.receive",
            "finance.view",
        ],
    ),
    (
        "AUDITOR",
        "Auditor",
        "Read-only oversight across the organization — sees everything, changes nothing.",
        ["catalog.view", "inventory.view", "finance.view", "audit.view"],
    ),
]


def seed(apps, schema_editor):  # type: ignore[no-untyped-def]
    Role = apps.get_model("iam", "Role")
    Permission = apps.get_model("iam", "Permission")

    for code, description in NEW_PERMISSIONS:
        resource, _, action = code.partition(".")
        Permission.objects.get_or_create(
            code=code,
            defaults={"resource": resource, "action": action, "description": description},
        )

    # Roles first — the approval grants below address roles created here.
    for code, name, description, perms in NEW_ROLES:
        role, _ = Role.objects.get_or_create(
            code=code, defaults={"name": name, "description": description}
        )
        if not role.description:
            role.description = description
            role.save(update_fields=["description"])
        for perm_code in perms:
            permission = Permission.objects.filter(code=perm_code).first()
            if permission is not None:
                role.permissions.add(permission)

    decide = Permission.objects.filter(code="approval.decide").first()
    manage = Permission.objects.filter(code="approval.manage").first()
    if decide is not None:
        for role in Role.objects.filter(code__in=DECIDERS):
            role.permissions.add(decide)
    if manage is not None:
        for role in Role.objects.filter(code__in=OVERSEERS):
            role.permissions.add(manage)

    for code, limit in LIMITS.items():
        Role.objects.filter(code=code).update(approval_limit=limit)


def unseed(apps, schema_editor):  # type: ignore[no-untyped-def]
    Role = apps.get_model("iam", "Role")
    Role.objects.filter(code__in=[c for c, _, _, _ in NEW_ROLES]).delete()
    Role.objects.update(approval_limit=None)


class Migration(migrations.Migration):
    dependencies = [("iam", "0018_approval_limits")]
    operations = [migrations.RunPython(seed, unseed)]
