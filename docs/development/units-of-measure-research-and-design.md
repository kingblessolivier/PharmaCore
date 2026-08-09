# Units of measure: how medicines are actually counted, and what PharmaCore does instead

**Status:** research + design. Nothing here is implemented yet.
**Date:** 2026-08-09
**Why this exists:** a direct question — *"medicines are measured in different types; a pack may
contain multiple tablets, a tablet may be split in half; wholesale measures one way and the
pharmacy another. How have we solved this?"*

The honest answer, established by measurement below, is **we have not solved it at all**. This
document proves that, then sets out how the domain really works and what the model has to become.

---

## 1. What the code does today — measured, not assumed

Four probes against the live models and the dev database.

### 1.1 No quantity anywhere carries a unit

Every line that holds a quantity was checked for a companion unit field:

| Model | Unit field |
|---|---|
| `retail.SaleItem` | **none** |
| `procurement.PurchaseOrderLine` | **none** |
| `distribution.OrderItem` | **none** |
| `inventory.InventoryBatch` | **none** |
| `inventory.StockMovement` | **none** |

(The `unit_price`, `price_per_unit` and `landed_unit_cost` fields are money-per-something; none
of them says what the something *is*.)

**Consequence.** `quantity = 10` is dimensionless everywhere in the system. When a depot ships
"10" and a pharmacy receives "10", the two agree on a number and not on a fact. If the depot
meant 10 boxes of 100 and the pharmacy books 10 tablets, stock is wrong by 1000× and **nothing in
the system can detect it** — both sides are internally consistent.

This is the single most serious defect found in the project so far. It is not a missing feature;
it is a missing dimension on a number that the whole business is denominated in.

### 1.2 A half tablet cannot be represented

```
retail.SaleItem.quantity                PositiveIntegerField
inventory.InventoryBatch.quantity_available   PositiveIntegerField
procurement.PurchaseOrderLine.quantity_ordered  PositiveIntegerField
procurement.PurchaseOrderLine.quantity_received PositiveIntegerField
```

Every quantity is a **positive integer**. Splitting a tablet — routine for paediatric doses, for
warfarin titration, and for any patient who cannot afford a full pack — is unrepresentable. There
is no rounding bug to fix here; the value simply has nowhere to go.

### 1.3 The conversion table exists and nothing reads it

`catalog.ProductUomConversion` has exactly the right shape:

```python
product, unit_name, conversion_factor, price_per_unit, is_default_dispensing
```

Its readers, in full: a serializer, a viewset, a router entry. **No pricing path, no POS path, no
receiving path, no stock movement, no order line reads it.** It is a table an administrator can
fill in, which then governs nothing — the same "modelled, enforced, unreachable" pattern found in
depot listings, price lists and `reports_to`.

Row count in the dev database: **0**.

### 1.4 The fields that do exist are empty

Across all 7 products in the dev database:

```
unit_of_measure:  {'': 7}     # every product blank
pack_size:        {'': 7}     # every product blank
units_per_pack:   {1: 7}      # every product 1
```

`units_per_pack = 1` is the default, not a measurement. So even the one field that could carry a
pack factor says "a pack is one of whatever this is" for every product in the system.

**Summary.** The question "how have we solved this?" has the answer: there is a table for it that
nothing reads, a field for it that is blank on every row, and no quantity in the system records
which unit it counts. The bugs in POS, distribution and catalog are downstream of this.

---

## 2. How medicines are actually measured

The packaging hierarchy is real and physical, and it differs by dosage form. Getting this right
matters because **each level is the level at which some part of the business transacts**.

### 2.1 The general shape

```
 SHIPPER / CARTON      ← how it is imported and freighted
   └─ CASE / OUTER     ← how a depot stores and picks
        └─ PACK / BOX  ← how a pharmacy buys and shelves
             └─ STRIP / BLISTER   ← how a pharmacy often sells
                  └─ EACH (tablet, capsule)   ← how a patient consumes
                       └─ FRACTION (½, ¼ tablet)  ← how a dose is sometimes given
```

Not every product has every level. The rule is that **a product has an ordered chain of units, each
with an integer factor to the one below**, and the base unit is the smallest thing that can leave
the building.

### 2.2 By dosage form

| Form | Base unit | Typical chain | Divisible? | Notes |
|---|---|---|---|---|
| **Tablet** | tablet | carton → box → strip(10) → tablet | **Yes** — scored tablets halve/quarter | Only *scored* tablets may be split. Enteric-coated, film-coated modified-release and cytotoxic tablets **must not** be. |
| **Capsule** | capsule | carton → box → strip(10) → capsule | **No** | A capsule cannot be split. Opening one changes the dose form. |
| **Syrup / suspension** | bottle | carton → bottle (60/100/200 mL) | Sold whole; **dosed** in mL | The pharmacy sells a bottle; the patient measures 5 mL. Stock is bottles, dose is mL. |
| **Injection (ampoule/vial)** | ampoule/vial | carton → tray → ampoule | Vial may be **multi-dose** | A 10 mL vial giving 5×2 mL doses is one stock unit, five administrations. |
| **Ointment / cream** | tube | carton → tube (15/30 g) | No | Stocked and sold whole. |
| **Drops** | bottle | carton → bottle (10 mL) | No | Dosed in drops; not divisible as stock. |
| **Inhaler** | device | carton → device (200 actuations) | No | Actuations matter clinically, not for stock. |
| **Sachet / powder** | sachet | carton → box → sachet | No | |
| **IV fluid** | bag | carton → bag (500 mL) | No | Bulky; the case level dominates warehouse planning. |
| **Suppository** | each | carton → box → strip | Rarely | |

Two distinctions this table forces, which the current model collapses:

1. **Stock unit vs dose unit.** Syrup is *stocked* in bottles and *dosed* in millilitres. These are
   different scales and cannot be the same field. A prescription of "5 mL three times daily for 7
   days" consumes 105 mL, which is 2 bottles of 60 mL — the system must be able to do that
   arithmetic and today it cannot even express it.
2. **Divisibility is a property of the product, not the transaction.** Whether the counter may
   sell half depends on whether the tablet is scored. That is a catalog fact and must be enforced,
   not left to the cashier.

### 2.3 The fraction problem specifically

Splitting is legitimate and common in Rwanda, but it is not "quantity can be a decimal". Three
rules govern it:

- **Only where permitted.** A scored, immediate-release tablet may be halved. A modified-release
  or enteric-coated tablet may not — splitting it converts a 24-hour dose into an immediate one,
  which is a clinical harm, not an inventory rounding.
- **The remainder is real.** Selling half a tablet leaves half a tablet. Either it is sold to the
  next patient or it is waste; either way stock must account for it. An integer field cannot.
- **The pack cannot be un-split.** Once a strip is broken, that pack cannot be returned to the
  supplier or transferred as a sealed pack. Broken packs are a distinct stock state.

The right representation is a **rational quantity in base units** — store `quantity` as a decimal
with enough places (3 is sufficient: halves, quarters, thirds round-trip acceptably) plus an
explicit `divisibility` on the product (`1` = whole only, `2` = halves, `4` = quarters).

---

## 3. How each part of the business transacts, and in which unit

This is why one unit for the whole system cannot work — each party genuinely uses a different one.

| Party | Buys in | Stores in | Sells / issues in | Counts stock in |
|---|---|---|---|---|
| **Importer / manufacturer** | shipper | pallet, shipper | carton | carton |
| **Depot / wholesaler** | carton | case on a pallet | **case or pack** | base unit (for valuation) |
| **Retail pharmacy** | pack | pack on a shelf | **pack, strip, or each** | base unit |
| **Patient** | — | — | each, or a dose in mL | — |

### 3.1 Importing

An import line is negotiated per carton or per 1,000 units, priced in USD/EUR, and freighted by
volume and weight. Landed cost allocation (freight, duty, insurance, clearing) must push cost down
to the **base unit**, because that is the unit stock is valued in. If the purchase line is in
cartons and the batch is in tablets, the conversion has to happen exactly once, at receipt, and be
recorded — otherwise landed unit cost is wrong by the pack factor and every margin figure derived
from it is wrong too.

PharmaCore already allocates landed cost (`ImportsPage`, `landed_unit_cost`). Because there is no
unit on the line, **that allocation is currently dividing by a quantity whose unit is unknown.**

### 3.2 Warehousing

A warehouse does not pick in tablets. It picks in cases and packs, because that is what fits a bin
and what a picker can count without opening cartons. Storage is planned by **volume and weight per
case**, not by base units. The existing `StorageZone` / `BinLocation` / `PickWave` models are
sound, but a pick task that says "pick 500" is unusable — the picker needs "pick 5 boxes of 100".

Cold-chain adds a constraint: a vaccine carton has a fixed volume in a cold room, and cold-room
capacity is planned in litres of carton, never in doses.

### 3.3 Wholesale selling

A depot sells by pack or case and usually enforces a **minimum order quantity** and an **order
multiple** (you may buy 5 or 10 cases, not 7). Both are per product and per customer tier. Neither
exists in the model today.

### 3.4 Retail dispensing

The counter needs to sell in whichever unit the customer asks for, priced correctly for that unit:

- a full pack (cheapest per tablet),
- a strip,
- loose tablets (most expensive per tablet, because the pack is now broken),
- occasionally half a tablet.

Price is therefore **per unit level**, not per product. `ProductUomConversion.price_per_unit`
anticipated exactly this and is unused.

---

## 4. What the model has to become

### 4.1 A unit chain per product

Replace the free-text `unit_of_measure` / `pack_size` / `units_per_pack` triple with an ordered
chain, one row per level:

```python
class ProductUnit(models.Model):
    product          = FK(Product, related_name="units")
    code             = Char       # CARTON, CASE, PACK, STRIP, EACH, ML, G
    name             = Char       # "Box of 100", "Strip of 10"
    factor_to_base   = Decimal    # how many BASE units this level contains
    level            = Positive   # 0 = base, ascending outward
    is_base          = Bool       # exactly one per product
    is_purchase_default   = Bool  # what procurement orders in
    is_sale_default       = Bool  # what the counter sells in
    barcode          = Char       # each level has its own GTIN in GS1
```

Invariants worth enforcing in the database, not just in code:

- exactly one `is_base` per product, with `factor_to_base = 1`;
- `factor_to_base` strictly increasing with `level`;
- every non-base factor is an exact integer multiple of the level below (a case holds a whole
  number of packs — half a pack in a case is not a thing).

### 4.2 Every quantity gains a unit and a base amount

Each line that carries a quantity gains **three** columns, not one:

```python
quantity          = Decimal(max_digits=14, decimal_places=3)  # as entered, in `unit`
unit              = FK(ProductUnit)                           # what the number means
quantity_base     = Decimal(max_digits=16, decimal_places=3)  # denormalised, always in base
```

`quantity_base` is redundant and should exist anyway: every report, valuation, FEFO allocation and
stock check runs on it, and computing it on read means every one of those paths can get the
conversion subtly wrong in its own way. Compute once on write, in one place.

The pair `(quantity, unit)` is what a human entered and must be preserved for the document — an
invoice that said "5 cartons" must still say "5 cartons" a year later even if the pack factor is
later corrected.

### 4.3 Divisibility on the product

```python
divisibility = PositiveSmallInteger(default=1)   # 1 whole only, 2 halves, 4 quarters
split_warning = Char                             # why not, when 1
```

The counter refuses a fractional quantity unless `divisibility > 1`, and refuses one that is not a
multiple of `1/divisibility`. Enteric-coated and modified-release products get `1` and a reason,
so the refusal explains itself rather than looking like a bug.

### 4.4 Broken-pack state

An `InventoryBatch` gains `is_broken_pack`. A batch that has been opened for loose sale cannot be
returned to the supplier or transferred as sealed stock, and FEFO should prefer to exhaust it
before opening another — the opposite of what pure FEFO would do, and the reason a real pharmacy
keeps one opened box at the front of the shelf.

### 4.5 Price per unit level

`ProductUomConversion.price_per_unit` becomes `ProductUnit.price`, and `pricing.resolve()` — which
already exists and works — gains a `unit` argument. This is a small change to an engine that is
already the single source of price, which is why it is worth routing everything through it.

---

## 5. Migration path

The data is empty, which is the one piece of good news: `units_per_pack = 1` everywhere and zero
conversion rows means **there is no wrong data to migrate**, only absent data.

1. Add `ProductUnit`; back-fill one base unit per product from `dosage_form`
   (tablet → EACH, syrup → BOTTLE, …). Every existing quantity is then correct by definition,
   because it is already implicitly in base units.
2. Add `unit` + `quantity_base` to the line models, defaulting `unit` to the product's base unit
   and `quantity_base = quantity`. This is a no-op for existing rows — nothing changes value.
3. Widen the quantity columns to `Decimal(14,3)`. Widening an integer to a decimal is lossless.
4. Route pricing, FEFO allocation and receipt through the conversion. This is where the behaviour
   actually changes and where the tests go.
5. Only then expose pack/strip/each selling in the POS and pack/case ordering in procurement.

Steps 1–3 are safe and mechanical. Step 4 is the real work and needs the 85% coverage gate.

---

## 6. What this means for the reported bugs

The POS, distribution and catalog bugs are not independent:

- **POS** cannot offer "sell one strip" because no strip exists in the model.
- **Distribution** cannot state a minimum order or an order multiple, so depot and pharmacy agree
  on a dimensionless number and discover the disagreement physically, at delivery.
- **Catalog** has three fields for packaging that are blank on every product and a conversion table
  with no rows, so nothing downstream *can* be right.

Fixing them separately would mean three different guesses about what a quantity means. They need
this foundation first.

---

## 7. Open questions for the pharmacist

These are business decisions, not engineering ones, and I should not invent answers:

1. **Which products may be split in practice?** The scored/unscored distinction is on the physical
   tablet; is that data available from Rwanda FDA registration, or must it be captured per product
   at catalog entry?
2. **Is loose-tablet selling priced at a premium**, and if so is it a fixed uplift or a per-product
   price?
3. **Do depots here trade in cases, or in packs?** The model supports both; the default matters for
   how the ordering screen should behave.
4. **How is a broken pack's remainder handled at stock count** — counted as loose units, or written
   off at month end?
