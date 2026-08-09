# From factory to patient: how a medicine actually travels, and what the system must record

**Status:** research. Companion to [units-of-measure-research-and-design.md](units-of-measure-research-and-design.md).
**Date:** 2026-08-09
**Scope:** deliberately **global**, not Rwanda-only. PharmaCore is a product, and the chain below is
governed by international standards (GS1, WHO GDP, ICH) that hold in every market. Country rules
sit *on top* of this as extra documents and extra checks, never as a different shape.

---

## 0. Why trace the whole chain

The unit problem is not a catalog problem. The same physical goods change unit **four times**
between the factory and the patient, and each change is a place the count can silently go wrong.
Tracing the chain shows exactly where the conversion must happen and what has to be recorded at
each hand-off.

```
manufacturer → import → warehouse receipt → storage → distribution → pharmacy → patient
   carton         carton        carton          case        pack        pack     each / dose
                             ↑ convert to base            ↑ MOQ          ↑ break pack
```

---

## 1. Manufacture and packaging

A medicine is packed in nested levels, and **each level is a separately identified trade item**.

> GS1 assigns GTINs to all levels of a trade item hierarchy, including unit of use/single unit,
> each, inner pack, case, and pallet. Each different packaging level must be assigned a different
> GTIN. Most commonly GTIN-14 is used for case and pallet level packaging, and GTIN-13 for the
> consumer unit.

Two consequences for the model:

1. **A barcode belongs to a unit level, not to a product.** Scanning a case and scanning a pack
   must yield different answers — that is the entire point of separate GTINs. Our `ProductBarcode`
   is currently attached to the product, so a scanner cannot tell a case from the pack inside it.
   `ProductUnit.barcode` is where this now lives.
2. **A level exists because it is transacted.** GS1's own rule is that a level gets a GTIN when it
   "may be priced, ordered, or invoiced". That is the test for whether a product needs a `CASE`
   row at all: not "does it physically exist" but "does anybody buy it that way".

## 2. Import

The importing step is where a shipment becomes stock, and it carries the documents the rest of the
chain depends on:

- **Proforma / commercial invoice** — priced in the supplier's unit (per carton, per 1,000).
- **Certificate of Analysis (CoA)** — per batch. This is why batch is not optional metadata.
- **GMP certificate / manufacturer compliance** for the manufacturing site.
- **Import permit or authorisation** from the national regulator. In Rwanda this is Rwanda FDA via
  the IRIMS platform, and *all imported products are subject to physical inspection at the port of
  entry, or at the client's premises where the consignment is released under seal*.
- **Bill of lading, customs declaration, clearing** — and the costs attached to each.

**Shelf-life on arrival.** Regulators commonly refuse consignments arriving with too little life
left (a "% of shelf life remaining" rule at import). Whatever the local threshold, the system must
be able to *evaluate* it, which means expiry has to be known at the receipt line, not discovered
later.

**Landed cost.** Freight, duty, insurance and clearing are incurred per shipment and must be pushed
down to the **base unit**, because that is the unit stock is valued in. PharmaCore already allocates
landed cost — but with no unit on the line, it is currently dividing by a quantity whose unit is
undefined, so `landed_unit_cost` is wrong by the pack factor whenever the line was not entered in
base units.

## 3. Receipt into the warehouse

WHO Good Distribution Practice is explicit about what happens at the door:

> Adequate areas for reception, quarantine, storage, order preparation and dispatch should be
> maintained with flows that avoid mixing, contamination or confusion. Verification at reception
> includes integrity of seals, damage inspection, and matching with documents … verification of
> document matching, quarantine segregation and FEFO control/proper rotation.

So receipt is: **count → verify against the document → quarantine → release or reject**. The count
is in the *supplier's* unit and the stock record is in *base* units, which is the first mandatory
conversion in the chain, and the one that must be recorded rather than done in someone's head.

PharmaCore already models quarantine, QC release and cold-chain excursion. What it lacks is the
unit on the receipt line, so the conversion is unrecorded.

## 4. Storage

> A quarantine area is for storing goods that have not yet been inspected or tested … warehouses
> storing time and temperature-sensitive pharmaceuticals should contain a quarantine area for
> rejected, faulty and recalled products. Products should be placed in quarantine status when
> deviations from storage conditions occur.

Storage is planned in **cases**, not in tablets: a bin holds a number of cases, and a cold room
holds a volume of cartons. Capacity, picking and replenishment are all case-level activities. A
pick task that reads "pick 500" is unusable — the picker needs "5 boxes of 100", which the system
can only produce if it knows the chain.

Cold chain adds that the excursion applies to a **batch in a location**, and a temperature
deviation moves that batch to quarantine regardless of how many units it holds.

## 5. Distribution to the pharmacy

The depot sells in packs or cases, and constrains the order:

- **Minimum order quantity** — below which the trade is not worth picking.
- **Order multiple** — you may buy 5 or 10 cases, not 7, because a case is not opened to fill an
  order.

Neither exists in our model, which is why a pharmacy can currently order a quantity a depot cannot
actually ship, and both sides only discover it at delivery.

The goods then move **in transit** — owned by neither side's on-hand until a GRN lands them. That
is already modelled correctly and is the one part of this chain PharmaCore gets right today.

## 6. The pharmacy shelf

The pharmacy receives packs, shelves packs, and sells in whichever unit the patient asks for. Price
is per unit level and is **not** linear: a full pack is cheaper per tablet than loose tablets,
because selling loose breaks a pack that can then never be returned or transferred sealed.

## 7. The patient

This is where the two hardest facts live.

### 7.1 Stock unit is not dose unit

A syrup is *stocked* in bottles and *dosed* in millilitres. "5 mL three times daily for 7 days" is
105 mL, which is two 60 mL bottles. The system must hold both scales and convert between them, or
it cannot check that a prescription can actually be filled.

### 7.2 Splitting is permitted per product, never per transaction

The research is unambiguous, and it corrected an assumption I had made:

> Extended-release preparations — modified-release, prolonged-release, controlled-release or
> slow-release — should not be split. Enteric coated (gastro-resistant) tablets should also not be
> split … roughly **10% of split tablets are not suitable for splitting** because they lack score
> lines or because enteric or modified release coating precludes safe breaking, and such medication
> errors might reduce the effectiveness of drug treatment or promote adverse events.

And critically:

> **A score line does not always mean splitting is FDA-approved.**

**Design consequence.** I had intended to derive divisibility from whether a tablet is scored. That
is wrong: the presence of a score is not authority to split. `Product.divisibility` must therefore
be an **explicit, opt-in approval** defaulting to "whole only", with a `split_note` explaining a
refusal — which is what the model now does.

### 7.3 A split tablet has a shorter life than the pack it came from

> The split tablet should meet established stability requirements for **90 days** at 25 ± 2 °C and
> 60% ± 5% relative humidity when stored in standard high-density polyethylene pharmacy bottles.

This is a finding the earlier design missed. A broken pack does not simply keep the batch's printed
expiry — the loose remainder has its own, shorter, effective life. So `is_broken_pack` is not enough;
a broken batch needs an `effective_expiry = min(batch expiry, opened_at + stability window)`, and
FEFO must sort on the *effective* date. Otherwise the system will happily dispense a loose tablet
that is inside the batch's expiry and outside its own.

---

## 8. What the chain demands of the model

| Chain step | What must be recorded | Have we? |
|---|---|---|
| Packaging | a GTIN **per level** | ✗ barcode is on the product |
| Import | batch, expiry, CoA, permit; cost per **base** unit | partly — no unit on the line |
| Receipt | the supplier's unit **and** the base conversion | ✗ |
| Quarantine / QC | batch state, excursion, release | ✓ |
| Storage | case-level capacity and picking | ✗ picks are dimensionless |
| Distribution | MOQ, order multiple, in-transit ownership | in-transit ✓, rest ✗ |
| Dispensing | unit sold, price per that unit | ✗ |
| Splitting | per-product approval + shorter effective expiry | ✗ |

Everything marked ✗ resolves to the same missing thing: **a unit on the quantity**, and a chain to
convert it through.

---

## 9. Build order

1. `ProductUnit` chain + `divisibility` — *in progress*
2. Conversion service; every path routes through it rather than multiplying inline
3. `unit` + `quantity_base` on the line models; quantities widened to decimal
4. Receipt conversion, then landed cost per base unit
5. Retail: sell by pack/strip/each, permitted fractions, broken-pack effective expiry
6. Distribution: MOQ and order multiple
7. Barcode per unit level, so a scanner distinguishes a case from a pack

---

## Sources

- [GS1 Healthcare GTIN Allocation Rules Standard](https://www.gs1.org/standards/gs1-healthcare-gtin-allocation-rules-standard/current-standard)
- [GTIN Packaging Hierarchy Explained: Each, Case, Pallet](https://www.lspedia.com/blog/gtin-packaging-hierarchy-explained-each-case-pallet-and-why-data-accuracy-matters)
- [Packaging Levels — GS1 New Zealand](https://support.gs1nz.org/hc/en-us/articles/360053015452-Packaging-Levels)
- [GDP: Good Distribution Practices in the Pharmaceutical Industry](https://acrosslogistics.com/blog/en/gdp-good-distribution-practices-pharma-industry)
- [USP <1079> Good Storage and Shipping Practices](http://ftp.uspbpep.com/v29240/usp29nf24s0_c1079.html)
- [Royal Pharmaceutical Society — Pharmaceutical Issues when Crushing, Opening or Splitting Oral Dosage Forms](https://www.rpharms.com/Portals/0/RPS%20document%20library/Open%20access/Support/toolkit/pharmaceuticalissuesdosageforms-(2).pdf)
- [FDA Guidance for Industry — Tablet Scoring: Nomenclature, Labeling, and Data for Evaluation](https://www.fda.gov/media/81626/download)
- [Substantial reduction of inappropriate tablet splitting with computerised decision support](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2702268/)
- [Rwanda FDA — Import and Export Requirements](https://rwandafda.gov.rw/import-and-export-requirements/) (one worked example of a national layer)
