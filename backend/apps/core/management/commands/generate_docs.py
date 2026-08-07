"""Emit the data-model and API reference from the live code.

`docs/02-data-model.md` had drifted to roughly 145 of ~160 models missing, and
`docs/07-api-design.md` to about a hundred absent routes. Writing that back by
hand produces a document that is correct for a week: it goes stale the moment a
field is added, and nobody notices, because a stale document looks exactly like a
current one.

So the exhaustive reference is generated and the narrative stays hand-written.
This command reads the model registry and the DRF routers and emits two files
that are accurate by construction. Model and field docstrings/help_text carry the
reasoning, so the output reads as prose rather than a schema dump.

    python manage.py generate_docs            # write the reference
    python manage.py generate_docs --check    # fail if it is out of date (CI)
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any, cast

from django.apps import apps as django_apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.urls import URLPattern, URLResolver, get_resolver

# Only our own apps — third-party tables are not part of the domain model.
DOMAIN_APPS = [
    "approvals",
    "catalog",
    "core",
    "distribution",
    "documents",
    "events",
    "finance",
    "hr",
    "iam",
    "inventory",
    "procurement",
    "retail",
    "workspace",
]

APP_TITLES = {
    "approvals": "Approvals — the central inbox every gated action routes through",
    "catalog": "Catalog — products, ingredients, pricing and clinical data",
    "core": "Core — cross-cutting primitives",
    "distribution": "Distribution — depot-to-retail B2B trade and route-to-market",
    "documents": "Documents — the generated-document vault and its numbering",
    "events": "Events — the transactional outbox",
    "finance": "Finance — the general ledger and everything that posts to it",
    "hr": "People — employment, payroll, leave and competency",
    "iam": "Identity & access — tenancy, users, roles and audit",
    "inventory": "Inventory — batches, warehousing, cold chain and traceability",
    "procurement": "Procurement — supplier master, POs, imports and three-way match",
    "retail": "Retail — the point of sale, dispensing and clinical services",
    "workspace": "Workspace — collaboration on any record",
}

BANNER = (
    "<!-- GENERATED FILE — do not edit by hand.\n"
    "     Run `python manage.py generate_docs` after changing models or routes.\n"
    "     The narrative lives in docs/02-data-model.md and docs/07-api-design.md. -->\n"
)


def _clean(text: str | None) -> str:
    """Collapse a docstring to a single readable paragraph."""
    if not text:
        return ""
    lines = [ln.strip() for ln in text.strip().splitlines()]
    return " ".join(ln for ln in lines if ln)


def _first_sentence(text: str) -> str:
    cleaned = _clean(text)
    if not cleaned:
        return ""
    for stop in (". ", "? ", "! "):
        if stop in cleaned:
            return cleaned.split(stop)[0] + stop.strip()
    return cleaned


def _field_type(field: Any) -> str:
    name = type(field).__name__.replace("Field", "") or "Field"
    if isinstance(field, models.ForeignKey):
        return f"FK → {cast(Any, field.related_model)._meta.label}"
    if isinstance(field, models.OneToOneField):
        return f"one-to-one → {cast(Any, field.related_model)._meta.label}"
    if isinstance(field, models.ManyToManyField):
        return f"M2M → {cast(Any, field.related_model)._meta.label}"
    if isinstance(field, models.DecimalField):
        return f"Decimal({field.max_digits},{field.decimal_places})"
    if isinstance(field, models.CharField) and field.max_length:
        return f"Char({field.max_length})"
    return name


def _field_note(field: Any) -> str:
    """What is worth knowing about this field beyond its type."""
    bits: list[str] = []
    if getattr(field, "choices", None):
        values = [str(c[0]) for c in field.choices]
        shown = ", ".join(values[:6]) + (" …" if len(values) > 6 else "")
        bits.append(f"one of: {shown}")
    if getattr(field, "unique", False):
        bits.append("unique")
    if getattr(field, "null", False):
        bits.append("optional")
    on_delete = getattr(getattr(field, "remote_field", None), "on_delete", None)
    if on_delete is not None:
        bits.append(f"on delete: {on_delete.__name__.lower()}")
    help_text = _clean(str(getattr(field, "help_text", "") or ""))
    if help_text:
        bits.append(help_text)
    return " · ".join(bits)


def _constraints(meta: Any) -> list[str]:
    out: list[str] = []
    for constraint in getattr(meta, "constraints", []):
        name = getattr(constraint, "name", "")
        fields = getattr(constraint, "fields", None)
        condition = getattr(constraint, "condition", None)
        check = getattr(constraint, "check", None)
        if fields:
            text = f"unique on ({', '.join(fields)})"
            if condition is not None:
                text += f" where {condition}"
        elif check is not None:
            text = f"check {check}"
        else:
            text = "constraint"
        out.append(f"`{name}` — {text}")
    return out


def build_data_model() -> str:
    lines = [BANNER, "# Data model reference\n"]
    lines.append(
        "Every persisted entity in the system, generated from the Django model registry.\n"
        "For how a domain hangs together and which invariants matter, read\n"
        "[docs/02-data-model.md](../02-data-model.md).\n"
    )

    total = 0
    for label in DOMAIN_APPS:
        try:
            config = django_apps.get_app_config(label)
        except LookupError:
            continue
        model_list = sorted(config.get_models(), key=lambda m: m.__name__)
        if not model_list:
            continue
        lines.append(f"\n## {APP_TITLES.get(label, label)}\n")
        for model in model_list:
            total += 1
            meta = model._meta
            lines.append(f"\n### `{model.__name__}`\n")
            doc = _clean(model.__doc__)
            # Django supplies a useless default docstring for undocumented models.
            if doc and not doc.startswith(f"{model.__name__}("):
                lines.append(f"{doc}\n")
            lines.append(f"Table `{meta.db_table}`.\n")

            lines.append("\n| Field | Type | Notes |")
            lines.append("| --- | --- | --- |")
            for field in meta.get_fields():
                if not getattr(field, "concrete", False):
                    continue
                note = _field_note(field).replace("|", "\\|")
                lines.append(f"| `{field.name}` | {_field_type(field)} | {note} |")

            rules = _constraints(meta)
            if rules:
                lines.append("\n**Invariants**\n")
                for rule in rules:
                    lines.append(f"- {rule}")
            lines.append("")

    lines.insert(2, f"\n**{total} entities across {len(DOMAIN_APPS)} apps.**\n")
    return "\n".join(lines) + "\n"


def _walk(patterns: list[Any], prefix: str = "") -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    for entry in patterns:
        if isinstance(entry, URLResolver):
            found.extend(_walk(entry.url_patterns, prefix + str(entry.pattern)))
        elif isinstance(entry, URLPattern):
            found.append((prefix + str(entry.pattern), entry))
    return found


def build_api() -> str:
    lines = [BANNER, "# API reference\n"]
    lines.append(
        "Every route the project serves, generated from the URL resolver.\n"
        "For conventions — pagination, errors, auth, idempotency — read\n"
        "[docs/07-api-design.md](../07-api-design.md).\n"
    )

    routes = _walk(get_resolver().url_patterns)
    grouped: dict[str, list[tuple[str, Any]]] = {}
    for path, pattern in routes:
        if not path.startswith("api/"):
            continue
        parts = path.split("/")
        section = parts[1] if len(parts) > 1 else "api"
        grouped.setdefault(section, []).append((path, pattern))

    total = 0
    for section in sorted(grouped):
        lines.append(f"\n## `/api/{section}`\n")
        lines.append("\n| Path | Methods | View | Purpose |")
        lines.append("| --- | --- | --- | --- |")
        seen: set[str] = set()
        for path, pattern in sorted(grouped[section], key=lambda r: r[0]):
            callback = pattern.callback
            view = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
            actions = getattr(callback, "actions", {}) or {}
            methods = ",".join(sorted(m.upper() for m in actions)) if actions else "—"
            key = f"{path}:{methods}"
            if key in seen:
                continue
            seen.add(key)
            total += 1

            purpose = ""
            if view is not None:
                # A named action documents itself; otherwise fall back to the viewset.
                handler_name = next(iter(actions.values()), None) if actions else None
                handler = getattr(view, handler_name, None) if handler_name else None
                purpose = _first_sentence(getattr(handler, "__doc__", "") or view.__doc__ or "")
            lines.append(
                f"| `/{path}` | {methods} | "
                f"`{view.__name__ if view else '—'}` | {purpose.replace('|', chr(92) + '|')} |"
            )
        lines.append("")

    lines.insert(2, f"\n**{total} routes.**\n")
    return "\n".join(lines) + "\n"


class Command(BaseCommand):
    help = "Generate the data-model and API reference documents from the live code."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--check",
            action="store_true",
            help="Exit non-zero if the reference is out of date, without writing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        root = Path(__file__).resolve().parents[5] / "docs" / "reference"
        root.mkdir(parents=True, exist_ok=True)
        targets = {
            root / "data-model.md": build_data_model(),
            root / "api.md": build_api(),
        }

        stale: list[str] = []
        for path, content in targets.items():
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current == content:
                self.stdout.write(f"  unchanged  {path.name}")
                continue
            if options["check"]:
                stale.append(path.name)
                diff = difflib.unified_diff(
                    current.splitlines(),
                    content.splitlines(),
                    fromfile=f"{path.name} (committed)",
                    tofile=f"{path.name} (from code)",
                    lineterm="",
                    n=1,
                )
                for line in list(diff)[:40]:
                    self.stdout.write(line)
            else:
                path.write_text(content, encoding="utf-8")
                self.stdout.write(self.style.SUCCESS(f"  written    {path.name}"))

        if stale:
            raise CommandError(
                f"The generated reference is out of date: {', '.join(stale)}. "
                "Run `python manage.py generate_docs` and commit the result."
            )
