# Catalog redesign plan

**Status:** complete · **Date:** 2026-08-07

## The audit

Catalog is the furthest off standard of any subsystem so far, and unlike the
others the screens are the *smaller* problem.

### Screens: 1 of 11 on standard

| | |
|---|---|
| On `DataGrid` | **1** of 11 (Products) |
| On `RecordKit` | **0** of 11 |
| Raw `<table>` | **8** |
| `Modal` | **14** |

### Six of thirteen models govern nothing

Verified by grepping every app outside `apps/catalog`:

| Model | Referenced outside catalog |
|---|---|
| `ProductInteraction` | **nowhere** |
| `ProductContraindication` | **nowhere** |
| `PriceList` / `ProductPrice` | **nowhere** |
| `ProductSubstitute` | **nowhere** |
| `ProductUomConversion` | **nowhere** |
| `FormularyItem` | **nowhere** |

There is also **no `services.py` in the app at all** — thirteen models, and every
behaviour that exists lives in a view or a serializer.

## Defects

| # | Defect | Why it matters |
|---|--------|----------------|
| **C1** | **Drug interactions are never checked when dispensing.** `ProductInteraction` carries severity (minor/moderate/major), the clinical effect and management advice, and `ProductIngredient` links products to their actives — everything a check needs. Nothing calls it. Two majorly-interacting medicines can be sold in the same basket and the system says nothing. | The ROADMAP specifies "prospective DUR (interactions/duplicate/allergy alert **before dispense**)". It is modelled and inert. This is a patient-safety feature that exists only as data. |
| **C2** | **Contraindications are never surfaced.** Same shape: condition, ICD-10, SNOMED, severity up to CONTRAINDICATED — read by nothing. | A pharmacist gets no warning for a medicine contraindicated for a condition already on record. |
| **C3** | **Price lists govern no price.** The POS reads `PharmacyProduct.retail_price`; `PriceList` and `ProductPrice` are a parallel, decorative table. | Identical to the `DepotProductListing` defect fixed in Distribution — two competing "what does this cost" concepts, and selling uses the one the screen does not manage. |
| **C4** | **Substitutes are never offered.** `ProductSubstitute` exists; when a product is out of stock the till says so and stops. | The single most useful thing a catalog knows at an empty shelf is what else would do. |
| **C5** | **No service layer.** Thirteen models, no `services.py`; behaviour sits in views, against the convention this codebase states explicitly. | Nothing above is reachable from a management command or testable without HTTP. |
| **C6** | **Screens off standard** — see the table above. | |

## Phases

Logic before UI, as with the previous five subsystems.

* **C-A — `dur.py`**: `screen_basket()` returning interaction, duplicate-therapy
  and contraindication findings ranked by severity, checked *before* the sale
  completes. Wired into the counter so it cannot be skipped by accident.
* **C-B — `pricing.py`**: resolve a price through the price list that applies
  (customer/segment/date), falling back to `PharmacyProduct.retail_price` where
  no list covers it, so pharmacies that never adopted lists keep trading. The POS
  reads the resolved price.
* **C-C — substitutes**: offered at the till when stock is short, with what is
  actually on hand.
* **C-D — screens**: all 11 on `DataGrid` + `RecordKit`, and surface what the
  engine now knows (interaction warnings, effective price, substitute
  availability).

## Method

Audit against real code → name defects with evidence → build logic before UI →
test → live HTTP walkthrough.


## What was built

| Phase | Delivered |
|---|---|
| **C-A** `dur.py` | Interaction, duplicate-therapy and contraindication screening. Interactions match on **active ingredients**, so two brands of the same pair are caught and a single combination product is *not* mistaken for one. Findings are returned ranked by severity; a major one sets `requires_override` rather than hard-blocking, because a pharmacist may dispense knowingly — they must not dispense unknowingly. |
| **C-B** `pricing.py` | Price resolves through any list in force (type, dates, quantity break), lowest applicable price winning, falling back to `PharmacyProduct.retail_price` where no list covers the product. A pharmacy that never adopted lists keeps trading unchanged. |
| **C-C** `substitution.py` | Substitutes offered only when actually in stock and unexpired, with generic equivalents separated from therapeutic alternatives — the first is usually the pharmacist's call, the second the prescriber's. |
| **Counter** | The scan now returns the resolved price, its source, and — when the shelf is empty — what else would do. |
| **API** | `/api/catalog/screen/`, `/price/`, `/price/coverage/`, `/substitutes/`. |

17 tests. Full suite exit 0.

### Screens

| | Before | After |
|---|---|---|
| On `DataGrid` | 1 of 11 | **10 of 11** |
| On `RecordKit` | 0 | **8** |
| Raw `<table>` | 8 | **0** |
| `Modal` | 14 | **0** |

`CatalogHome` is the app home and correctly uses the shared `AppHome` primitives,
as every module home does.

**Expiry Forecast was rebuilt rather than converted.** It promised "batch
tracking" and showed two aggregate numbers from the dashboard. A count says
there is a problem; it does not say which shelf to walk to. It now lists every
batch expiring inside a selectable window, soonest first, with units and value at
risk, and calls out stock that has already expired and is still on the shelf.

## Still open

* **Nothing has been rendered in a browser** (no browser tool available).
