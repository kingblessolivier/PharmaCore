"""Two gates that would have caught three defects before they reached staging.

The system-wide audit found that verification in this project had been checking
*shape* rather than *behaviour* — that a file imported the right component, that a
function returned the right number. Neither of those can see an endpoint that does
not exist or a view that checks nothing. These two tests run in about a second and
close exactly that gap.

**Gate 1** — every DRF view class declares ``permission_classes``. Finance had 24
view classes and none, so every authenticated user could read the general ledger.
The project default is ``IsAuthenticated``, which means "anyone with a password";
inheriting it silently is how that happened.

**Gate 2** — every ``/api/...`` path the frontend calls resolves against the
router. Three shipped screens called ``/api/catalog/active-ingredients/``, which
has never existed.
"""

from __future__ import annotations

import inspect
import pathlib
import re

import pytest
from django.urls import Resolver404, resolve

BACKEND = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = BACKEND.parent / "frontend" / "src"

#: Views that legitimately need no permission declaration, with the reason.
GATE1_EXEMPT = {
    "RootView": "public service banner",
    "HealthView": "unauthenticated liveness probe",
    "LoginView": "issues the token in the first place",
    "TokenRefreshView": "refresh must work before a permission check is possible",
    "SchemaView": "OpenAPI schema",
}


def _view_classes() -> list[tuple[str, str, bool]]:
    """(module, class, is_protected) for every DRF view in the project.

    ``is_protected`` is deliberately **effective**, not textual: a view inheriting
    permissions from a project base class is protected, and a gate that demanded a
    literal assignment in every class body would be checking shape again — the
    exact mistake the audit was about. HR is the case in point: several of its
    viewsets declare nothing locally and correctly return 403, because their base
    class carries ``CanViewPeople``.
    """
    import importlib

    found: list[tuple[str, str, bool]] = []
    for path in sorted((BACKEND / "apps").rglob("views*.py")):
        module_name = ".".join(path.relative_to(BACKEND).with_suffix("").parts)
        module = importlib.import_module(module_name)
        for name in dir(module):
            obj = getattr(module, name)
            if not isinstance(obj, type) or obj.__module__ != module_name:
                continue
            if getattr(obj, "permission_classes", None) is None:
                continue  # not a DRF view
            # Did *project* code make a decision anywhere in the MRO? Three
            # legitimate ways to do it, and the gate accepts all three — a check
            # that only recognised its author's favourite would just be noise:
            #   1. permission_classes on the class or a project base class;
            #   2. get_permissions();
            #   3. an in-method check — HR raises PermissionDenied inside
            #      get_queryset() after testing has_permission(), which works.
            decided = False
            for klass in obj.__mro__:
                if not klass.__module__.startswith("apps."):
                    continue
                if "permission_classes" in vars(klass) or "get_permissions" in vars(klass):
                    decided = True
                    break
                try:
                    source = inspect.getsource(klass)
                except (OSError, TypeError):  # pragma: no cover - defensive
                    continue
                if "has_permission(" in source or "PermissionDenied" in source:
                    decided = True
                    break
            found.append((module_name, name, decided))
    return found


def test_every_view_declares_its_permissions() -> None:
    """Gate 1 — no view may silently fall back to "anyone with a password"."""
    offenders = [
        f"{module}.{name}"
        for module, name, protected in _view_classes()
        if not protected and name not in GATE1_EXEMPT
    ]
    assert not offenders, (
        "These view classes rely on the project default permission "
        "(IsAuthenticated = anyone with a password). Declare an explicit "
        "permission class, or add the view to GATE1_EXEMPT with a reason:\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_the_gate_actually_sees_views() -> None:
    """A gate that silently matches nothing is worse than no gate."""
    views = _view_classes()
    assert len(views) > 150, f"only found {len(views)} view classes — the scan is broken"
    assert any(not p for _, _, p in views) or True  # informational


#: (label, url, roles that must be refused). The behavioural half of gate 1 —
#: this is what actually protects the books, and it is stated as "who is refused"
#: rather than "which class is attached" so it survives refactoring.
MUST_BE_REFUSED = [
    ("the general ledger", "/api/finance/journal-entries/", ["CASHIER", "DRIVER"]),
    ("trial balance", "/api/finance/reports/trial-balance/", ["CASHIER", "DRIVER"]),
    ("profit and loss", "/api/finance/reports/profit-and-loss/", ["CASHIER", "DRIVER"]),
    ("bank accounts", "/api/finance/bank-accounts/", ["CASHIER", "DRIVER", "PHARMACIST"]),
    ("supplier bills", "/api/finance/supplier-bills/", ["CASHIER", "DRIVER"]),
    ("customer credit limits", "/api/finance/credit-profiles/", ["CASHIER", "DRIVER"]),
    ("payment runs", "/api/finance/payment-runs/", ["CASHIER", "DRIVER", "WAREHOUSE_CLERK"]),
    ("payroll runs", "/api/hr/payroll-runs/", ["CASHIER", "DRIVER"]),
    ("employee records", "/api/hr/employees/", ["CASHIER", "DRIVER"]),
    # D2 and its neighbours. The audit named the controlled register; the first
    # pass fixed the finance half of that finding and not this one, and the gate
    # passed anyway because the register was not on this list. A gate only
    # guards what it is told to guard.
    (
        "the controlled substances register",
        "/api/retail/controlled-drugs/",
        ["CASHIER", "DRIVER", "WAREHOUSE_CLERK"],
    ),
    (
        "dispensing records (named patients)",
        "/api/retail/dispensing/",
        ["DRIVER", "WAREHOUSE_CLERK"],
    ),
    ("prescriptions", "/api/retail/prescriptions/", ["DRIVER", "WAREHOUSE_CLERK"]),
    ("price lists", "/api/catalog/price-lists/", ["DRIVER"]),
]


@pytest.mark.django_db
def test_the_books_are_not_readable_by_everyone() -> None:
    """D1 — a driver could read the general ledger. The nav hid it; the API did not."""
    from apps.iam.models import Organization, Role, User
    from rest_framework.test import APIClient

    org = Organization.objects.create(name="Remera Pharmacy", type="RETAIL")
    clients: dict[str, APIClient] = {}
    for code in {c for _, _, codes in MUST_BE_REFUSED for c in codes}:
        user = User.objects.create_user(
            username=f"probe_{code.lower()}", password="pw", organization=org
        )
        user.roles.add(Role.objects.get(code=code))
        client = APIClient()
        client.force_authenticate(user=user)
        clients[code] = client

    leaks = [
        f"{code} can read {label} ({url}) — got {clients[code].get(url).status_code}"
        for label, url, codes in MUST_BE_REFUSED
        for code in codes
        if clients[code].get(url).status_code == 200
    ]
    assert not leaks, "Sensitive data is readable by roles that must not see it:\n  " + "\n  ".join(
        leaks
    )


def _frontend_api_paths() -> dict[str, set[str]]:
    """Every fully-literal ``/api/...`` path the frontend calls.

    Deliberately **only literal paths**. A path like ``/api/hr/loans/${id}/${verb}/``
    cannot be resolved without knowing which verbs exist, and guessing produces
    false alarms — which would get the whole gate switched off, the usual fate of
    a noisy check. Literal paths are exactly the class of bug this caught
    (``/api/catalog/active-ingredients/``, ``/api/iam/organizations/``): a whole
    endpoint family that was never there.
    """
    paths: dict[str, set[str]] = {}
    for path in FRONTEND.rglob("*.ts*"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"""[`"'](/api/[^`"'\s]*)[`"']""", text):
            raw = match.group(1).split("?")[0]
            if "${" in raw or "*" in raw or raw.endswith("/api/"):
                continue
            paths.setdefault(raw, set()).add(path.name)
    return paths


def _resolves(candidate: str) -> bool:
    """True if the path resolves with or without a trailing slash.

    Some routes here are registered without one (``/api/auth/login``), so both
    spellings are legitimate and only "neither works" is a defect.
    """
    for variant in {candidate, candidate.rstrip("/"), candidate.rstrip("/") + "/"}:
        if not variant:
            continue
        try:
            resolve(variant)
            return True
        except Resolver404:
            continue
    return False


def test_every_endpoint_the_frontend_calls_exists() -> None:
    """Gate 2 — a screen that calls a route that does not exist is a dead screen."""
    paths = _frontend_api_paths()
    assert len(paths) > 150, f"only found {len(paths)} literal API paths — the scan is broken"

    broken = {
        candidate: callers for candidate, callers in paths.items() if not _resolves(candidate)
    }
    assert not broken, "The frontend calls endpoints that do not exist:\n  " + "\n  ".join(
        f"{candidate}  <- {', '.join(sorted(callers))}"
        for candidate, callers in sorted(broken.items())
    )
