"""A migration must never import a models module.

A migration freezes a callable default by reference, so the module holding that
callable is imported by the migration loader — which runs before the app registry
has settled. Pointing it at a models module produced a real crash at server
start, and only on autoreload, which is the worst kind:

    AttributeError: module 'apps.hr.models_people' has no attribute
                    'current_cpd_year'

The function was there. The module was half-executed.
"""

from __future__ import annotations

import pathlib
import re

BACKEND = pathlib.Path(__file__).resolve().parent.parent


def test_no_migration_imports_a_models_module() -> None:
    offenders = []
    for path in (BACKEND / "apps").rglob("migrations/*.py"):
        if path.name == "__init__.py":
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.match(r"\s*(?:import|from)\s+apps\.\w+\.models", line):
                offenders.append(f"{path.relative_to(BACKEND)}: {line.strip()}")
    assert not offenders, (
        "A migration importing a models module creates an import cycle with the "
        "migration loader. Put callable defaults in a module that imports no "
        "models (see apps/hr/defaults.py):\n  " + "\n  ".join(offenders)
    )


def test_default_modules_import_no_models() -> None:
    """The invariant that makes the cycle impossible rather than unlikely."""
    for path in (BACKEND / "apps").rglob("defaults.py"):
        source = path.read_text(encoding="utf-8")
        bad = [
            line.strip()
            for line in source.splitlines()
            if re.match(r"\s*(?:from|import)\s+.*\bmodels\b", line)
        ]
        assert not bad, f"{path.relative_to(BACKEND)} imports models: {bad}"
