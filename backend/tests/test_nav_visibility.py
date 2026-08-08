"""What each role can reach, computed from the nav's real permission gates.

Audit D7: five of eleven roles appeared in no nav group at all. A warehouse clerk
could not open Inventory, a dispatcher could not open Distribution, an insurance
clerk could not open Insurance — every one of those screens built for exactly the
person who could not reach it. And all five could open the till.

This parses the gates out of AppShell.tsx and evaluates them against the seeded
role→permission matrix, so the nav and the RBAC cannot drift apart silently.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from apps.iam.models import Organization, Role, User

pytestmark = pytest.mark.django_db

SHELL = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "frontend"
    / "src"
    / "components"
    / "AppShell.tsx"
)


def nav_groups() -> list[tuple[str, list[str] | str, int]]:
    """(label, needs, item_count) for every side-nav group."""
    src = SHELL.read_text(encoding="utf-8")
    block = src[src.find("const NAV: NavGroup[] = [") :]
    block = block[: block.find("\n];")]
    out = []
    for m in re.finditer(
        r'label:\s*"([^"]*)",\s*(?:app:\s*"[^"]*",\s*)?needs:\s*("all"|\[[^\]]*\])', block
    ):
        needs = "all" if m.group(2) == '"all"' else re.findall(r'"([^"]+)"', m.group(2))
        rest = block[m.end() :]
        chunk = rest[: rest.find("\n  },")]
        out.append((m.group(1) or "(ungrouped)", needs, len(re.findall(r'\{\s*to:\s*"', chunk))))
    return out


def test_the_gates_were_actually_found() -> None:
    groups = nav_groups()
    assert len(groups) >= 15, f"only parsed {len(groups)} nav groups — the parser is stale"
    assert sum(n for _, _, n in groups) > 100


@pytest.fixture
def org():
    return Organization.objects.create(name="Remera Pharmacy", type="RETAIL")


def visible_for(user) -> tuple[int, list[str]]:
    held = user.permission_codes()
    seen, count = [], 0
    for label, needs, items in nav_groups():
        if needs == "all" or any(code in held for code in needs):
            count += items
            if label != "(ungrouped)":
                seen.append(label)
    return count, seen


def person(org, code):
    user = User.objects.create_user(username=f"u_{code}", password="pw", organization=org)
    user.roles.add(Role.objects.get(code=code))
    return user


def test_every_role_reaches_the_screens_built_for_its_job(org, capsys) -> None:
    expectations = {
        "WAREHOUSE_CLERK": "Inventory",
        "DISPATCHER": "Distribution",
        "INSURANCE_CLERK": "Insurance",
        "ACCOUNTANT": "Finance",
        "HR_MANAGER": "People",
        "PHARMACIST": "Catalog",
        "PROCUREMENT_OFFICER": "Procurement",
        "BRANCH_MANAGER": "Inventory",
        "AUDITOR": "Finance",
    }
    rows, missing = [], []
    for code, expected in expectations.items():
        count, groups = visible_for(person(org, code))
        rows.append((code, count, groups))
        if expected not in groups:
            missing.append(f"{code} still cannot reach {expected} (sees {groups})")

    with capsys.disabled():
        print("\n" + "-" * 96)
        print(f"{'ROLE':<22}{'ENTRIES':>8}   GROUPS")
        print("-" * 96)
        for code, count, groups in rows:
            print(f"{code:<22}{count:>8}   {', '.join(groups)}")
        print("-" * 96)

    assert not missing, "\n  ".join(missing)


def test_only_people_who_sell_land_on_the_till(org) -> None:
    """Retail was `roles: "all"`, so a driver's home screen was the cash drawer."""
    for code in ("DRIVER", "WAREHOUSE_CLERK", "ACCOUNTANT", "HR_MANAGER"):
        assert "Retail" not in visible_for(person(org, code))[1], f"{code} can still open the till"
    for code in ("CASHIER", "PHARMACIST"):
        assert "Retail" in visible_for(person(org, code))[1], f"{code} cannot reach the till"


def test_a_driver_sees_deliveries_and_not_the_books(org) -> None:
    _, groups = visible_for(person(org, "DRIVER"))
    assert "Distribution" in groups
    for forbidden in ("Finance", "People", "Admin", "Retail"):
        assert forbidden not in groups


def test_a_branch_manager_oversees_without_becoming_a_pharmacist(org) -> None:
    """R1 — the whole point of the role. Oversight, not competence."""
    manager = person(org, "BRANCH_MANAGER")
    _, groups = visible_for(manager)
    assert {"Inventory", "Distribution", "Finance"} <= set(groups)
    assert not manager.has_permission("sale.dispense")
    assert not manager.has_permission("inventory.adjust")
    assert not manager.has_permission("catalog.manage")


def test_an_auditor_reads_everything_and_writes_nothing(org) -> None:
    auditor = person(org, "AUDITOR")
    _, groups = visible_for(auditor)
    assert {"Finance", "Inventory", "Distribution"} <= set(groups)
    for code in auditor.permission_codes():
        assert code.endswith(".view"), f"AUDITOR holds a non-read permission: {code}"


def test_nobody_but_an_admin_reaches_the_admin_console(org) -> None:
    for code in ("CASHIER", "PHARMACIST", "ACCOUNTANT", "BRANCH_MANAGER", "DRIVER"):
        assert "Admin" not in visible_for(person(org, code))[1]
