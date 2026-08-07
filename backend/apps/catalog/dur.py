"""Drug utilisation review: screening a basket before the medicine is handed over.

Everything this needs was already modelled and read by nothing.
``ProductInteraction`` carries severity, the clinical effect and the management
advice; ``ProductContraindication`` carries the condition, its ICD-10/SNOMED
codes and a severity up to CONTRAINDICATED; ``ProductIngredient`` links each
product to its actives. Two majorly-interacting medicines could be sold in one
basket and nothing said so.

Three checks, which is what "prospective DUR" means in practice:

* **Interactions** — between the active ingredients of everything being
  dispensed together, not between product names. Two brands of the same
  interacting pair must be caught, and only the ingredient link makes that
  possible.
* **Duplicate therapy** — the same active arriving twice under different
  products. The classic way a patient doubles their dose without anyone
  intending it.
* **Contraindications** — against conditions already recorded for the patient.

The screen never blocks by itself. A pharmacist may dispense an interacting pair
knowingly and often should; what they may not do is dispense it *unknowingly*.
So this returns findings, and the counter decides what to do with them —
recording an override rather than silently proceeding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from apps.catalog.models import (
    ActiveIngredient,
    Product,
    ProductContraindication,
    ProductIngredient,
    ProductInteraction,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

#: Ordered worst-first, so a basket's headline severity is just the max.
SEVERITY_RANK = {
    "CONTRAINDICATED": 4,
    "MAJOR": 3,
    "WARNING": 2,
    "MODERATE": 2,
    "PRECAUTION": 1,
    "MINOR": 1,
}


@dataclass
class Finding:
    """One thing the pharmacist should know before handing the medicine over."""

    kind: str  # INTERACTION | DUPLICATE | CONTRAINDICATION
    severity: str
    title: str
    detail: str
    management: str = ""
    products: list[int] = field(default_factory=list)
    product_names: list[str] = field(default_factory=list)

    @property
    def rank(self) -> int:
        return SEVERITY_RANK.get(self.severity, 0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "management": self.management,
            "products": self.products,
            "product_names": self.product_names,
        }


@dataclass
class Screening:
    """The verdict on a whole basket."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def worst(self) -> str:
        return max(self.findings, key=lambda f: f.rank).severity if self.findings else ""

    @property
    def is_clear(self) -> bool:
        return not self.findings

    @property
    def blocking(self) -> list[Finding]:
        """Findings serious enough that dispensing without a reason is indefensible.

        Still not a hard block — a pharmacist may have a good reason — but one
        that has to be given rather than assumed.
        """
        return [f for f in self.findings if f.rank >= 3]

    def as_dict(self) -> dict[str, Any]:
        ordered = sorted(self.findings, key=lambda f: -f.rank)
        return {
            "clear": self.is_clear,
            "worst_severity": self.worst,
            "requires_override": bool(self.blocking),
            "findings": [f.as_dict() for f in ordered],
        }


def _ingredients_for(product_ids: list[int]) -> dict[int, set[int]]:
    """Active ingredients per product, in one query."""
    mapping: dict[int, set[int]] = {pid: set() for pid in product_ids}
    for row in ProductIngredient.objects.filter(product_id__in=product_ids).values(
        "product_id", "ingredient_id"
    ):
        mapping.setdefault(row["product_id"], set()).add(row["ingredient_id"])
    return mapping


def screen_basket(*, product_ids: list[int], conditions: list[str] | None = None) -> Screening:
    """Screen everything being dispensed together.

    ``conditions`` are the patient's recorded conditions, matched against
    contraindications by name or ICD-10 code.
    """
    screening = Screening()
    ids = [int(p) for p in dict.fromkeys(product_ids)]  # de-duplicate, keep order
    if not ids:
        return screening

    products = {p.pk: p for p in Product.objects.filter(pk__in=ids)}
    by_product = _ingredients_for(ids)

    screening.findings.extend(_interactions(ids, products, by_product))
    screening.findings.extend(_duplicates(ids, products, by_product))
    screening.findings.extend(_contraindications(ids, products, conditions or []))
    return screening


def _interactions(
    ids: list[int], products: dict[int, Product], by_product: dict[int, set[int]]
) -> list[Finding]:
    """Interactions between the actives of any two products in the basket.

    Matched on ingredients rather than products, so two different brands of the
    same interacting pair are still caught.
    """
    all_ingredients = {i for s in by_product.values() for i in s}
    if len(all_ingredients) < 2:
        return []

    pairs = ProductInteraction.objects.filter(
        ingredient_a_id__in=all_ingredients, ingredient_b_id__in=all_ingredients
    ).select_related("ingredient_a", "ingredient_b")

    findings: list[Finding] = []
    seen: set[tuple[int, int]] = set()
    for pair in pairs:
        a, b = pair.ingredient_a_id, pair.ingredient_b_id
        if a == b:
            continue
        key = (min(a, b), max(a, b))
        if key in seen:
            continue

        holders_a = [pid for pid in ids if a in by_product.get(pid, set())]
        holders_b = [pid for pid in ids if b in by_product.get(pid, set())]
        # Both sides must be present, and not only because one product happens to
        # contain both actives — that is a formulation, not an interaction.
        involved = sorted({*holders_a, *holders_b})
        if not holders_a or not holders_b or len(involved) < 2:
            continue
        seen.add(key)

        findings.append(
            Finding(
                kind="INTERACTION",
                severity=pair.severity,
                title=(f"{pair.ingredient_a.name} interacts with {pair.ingredient_b.name}"),
                detail=pair.effect or "No effect recorded for this pair.",
                management=pair.management,
                products=involved,
                product_names=[str(products[pid]) for pid in involved if pid in products],
            )
        )
    return findings


def _duplicates(
    ids: list[int], products: dict[int, Product], by_product: dict[int, set[int]]
) -> list[Finding]:
    """The same active ingredient arriving under two different products.

    The classic way a patient doubles a dose without anyone intending it — two
    brands, one active, and nobody looked at the ingredients.
    """
    holders: dict[int, list[int]] = {}
    for pid in ids:
        for ingredient in by_product.get(pid, set()):
            holders.setdefault(ingredient, []).append(pid)

    names = {
        i.pk: i.name
        for i in ActiveIngredient.objects.filter(
            pk__in=[i for i, p in holders.items() if len(p) > 1]
        )
    }

    findings: list[Finding] = []
    for ingredient, pids in holders.items():
        if len(pids) < 2:
            continue
        findings.append(
            Finding(
                kind="DUPLICATE",
                severity="MAJOR",
                title=f"Duplicate therapy: {names.get(ingredient, 'same active ingredient')}",
                detail=(
                    f"{len(pids)} products in this basket contain the same active. "
                    "Dispensing both doubles the dose unless that is intended."
                ),
                management="Confirm the combined daily dose, or dispense only one.",
                products=sorted(pids),
                product_names=[str(products[p]) for p in sorted(pids) if p in products],
            )
        )
    return findings


def _contraindications(
    ids: list[int], products: dict[int, Product], conditions: list[str]
) -> list[Finding]:
    """Contraindications against the patient's recorded conditions."""
    if not conditions:
        return []

    wanted = {c.strip().lower() for c in conditions if c.strip()}
    if not wanted:
        return []

    findings: list[Finding] = []
    for row in ProductContraindication.objects.filter(product_id__in=ids).select_related("product"):
        condition = row.condition.strip().lower()
        code = row.icd10_code.strip().lower()
        # Substring either way: "type 2 diabetes" on file should match a
        # contraindication recorded as "diabetes".
        if not any(w in condition or condition in w or (code and w == code) for w in wanted):
            continue
        findings.append(
            Finding(
                kind="CONTRAINDICATION",
                severity=row.severity,
                title=f"{row.product} is contraindicated: {row.condition}",
                detail=row.message or row.condition,
                management="",
                products=[row.product_id],
                product_names=[str(row.product)],
            )
        )
    return findings


def summary(*, product_ids: list[int], conditions: list[str] | None = None) -> dict[str, Any]:
    """Screen a basket and return it in wire form."""
    return screen_basket(product_ids=product_ids, conditions=conditions).as_dict()
