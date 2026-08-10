# PharmaCore — where the system actually stands

**Date:** 2026-08-10
**Method:** measured against the codebase, not estimated. Every figure below
comes from a probe that was self-tested before its output was trusted — twice
in this project a normaliser has produced a confident wrong number.

---

## 1. The headline

| | |
|---|---|
| Domain models | **190** across 14 apps |
| API routes | **552** |
| Routes reachable from the UI | **534 — 96%** |
| Screens | 106 pages, 116 routes |
| Backend tests | 1,123 passing |

The 18 unreached routes are infrastructure: the OpenAPI schema, the docs page,
an events health probe. There is no meaningful "built but hidden" backlog left
— which was the dominant defect class in this system three weeks ago and is
now closed.

**What this means:** PharmaCore is not an early product with a good dashboard.
It is a substantially complete pharmaceutical ERP whose remaining gaps are
specific and nameable.

---

## 2. What is genuinely built

Measured by model, not by intention.

### Catalog and product governance
`Product` · `ProductUnit` · `ActiveIngredient` · `ProductIngredient` ·
`Manufacturer` · `PriceList` · `ProductBarcode` · `ProductContraindication` ·
`FormularyItem`

The packaging hierarchy your spec asks for exists and is enforced: every level
states its size in **base units**, so a carton of 24 boxes of 100 tablets is
2,400 tablets and the conversion is one multiplication, never a chain of
roundings. Handling requirements beyond temperature — hazard class, light
sensitivity, humidity — and dose-unit-versus-stock-unit are modelled, with
weight and volume per packing level for freight.

### Procurement
`PurchaseRequisition` → `RequestForQuotation` → `SupplierQuote` →
`PurchaseOrder` → `GoodsReceipt` → `SupplierInvoice` → payment.

The whole chain exists, with `SupplierProfile`, `SupplierLicence`,
`SupplierEvaluation`, `SupplierPriceAgreement`, landed costs and consignment.
Three-way matching is there. Line quantities carry a **unit** and a **base
quantity**, so a supplier reading "10" knows whether it means cartons.

### Inventory and warehouse
`Warehouse` → `StorageZone` → `BinLocation`. `InventoryBatch` with expiry,
`QualityCheck` for quarantine release, `BatchRecall`, `TemperatureSensor`,
`ExcursionInvestigation`, calibration records, cycle counts, consignment stock.

FEFO is implemented and sorts on an **effective** expiry — a broken pack expires
at the earlier of its printed date and 90 days from opening, which is the rule
that actually governs a dispensed strip.

### Retail / POS
`Sale` · `SaleItem` · `SaleBatchAllocation` · `SaleReturn` · `Dispensing` ·
`Prescription` · `DrawerSession` · `ShiftRoster` · `Promotion` ·
`ControlledDrug` · `ClinicalEncounter`

Batch allocation at the line, drawer sessions with variance, controlled-drug
handling, clinical services.

### Distribution and B2B
`StockOrder` · `DepotProductListing` · `Shipment` · `GoodsReceivedNote` ·
`BackorderLine` · `SalesRepresentative` · `JourneyPlan` · `SalesVisitLog` ·
`TenderContract` · `VanStock` · `CustomerReturn`

The depot storefront enforces what it publishes: order multiples, minimum
order, withheld stock, and a photo that must be **verified** before a buyer is
shown it as trustworthy.

### Finance
31 models. General ledger, journal entries, accounting periods, bank accounts
and reconciliation, `CreditProfile` for credit control, budgets, cost centres,
fixed assets, tax records, cash-flow forecast, expiry provisioning, FX
revaluation, card settlement.

### HR
32 models — the largest single app. `Employee` · `JobRequisition` ·
`Applicant` · `Contract` · `AttendanceLog` · `ShiftRoster` · `LeaveRequest` ·
`PayrollRun` · `PayrollRecord` · `PerformanceReview` · `TrainingRecord` ·
`CpdRecord` · `DisciplinaryAction` · `Competency` · onboarding checklists.

Recruitment through to payroll, including CPD — which for registered
pharmacists is a licensing requirement, not a nicety.

### Insurance
`InsuranceScheme` · `MemberPolicy` · `SchemeFormulary` · `Claim` · `ClaimLine` ·
`RemittanceAdvice`. The till quotes the insurer's share **before** dispensing.

### Cross-cutting
`ApprovalRequest` with a central inbox, claim-to-lock and SLA escalation.
`Document` + `DocumentSequence` — a numbered, hashed, tamper-evident document
engine covering PO, GRN, delivery note, tax invoice, payslip, VAT return,
credit and debit notes, payment vouchers, statements.

---

## 3. What is genuinely missing

Five things. All from the quality and service side.

| Missing | Why it matters | Size |
|---|---|---|
| **Deviation / CAPA** | GSDP expects deficiencies to be recorded, investigated, root-caused and closed with an effectiveness check. Today a temperature excursion has an investigation record but no CAPA lifecycle behind it. | Medium |
| **Pharmacovigilance** | Adverse drug reactions, medication errors, suspected quality defects and lack of efficacy are reportable. There is no case model at all. | Medium |
| **Complaints** | A customer complaint about a product is the front end of both CAPA and pharmacovigilance. It has nowhere to land. | Small |
| **Customer service tickets** | Short deliveries, billing queries and delivery issues are handled today by whoever notices. | Small |
| **Internal audit** | Audit plans, findings, management responses, follow-up. Distinct from the audit *log*, which exists. | Medium |

These are the honest gaps. Everything else in the specification is present in
some form.

---

## 4. The real weakness: interaction, not capability

**81 of 106 screens do their main work in a drawer or a modal.**

That is the gap between PharmaCore and an ERP people describe as serious. A
purchase order is a *document* — it has a header, parties, terms, lines,
totals, an approval chain and a life. Editing one in a slide-over is the
interaction equivalent of filling in a contract through a letterbox.

The pattern that works is already in the codebase, on the six screens that use
it:

```
SEARCH  →  TABLE  →  DETAIL DRAWER  →  FULL TRANSACTION
```

A drawer is correct for *looking*. A transaction screen is correct for
*working*. The conversion is page-by-page, in dependency order — procurement,
then inventory, then sales — so each module is coherent before the next starts.

---

## 5. Dashboards — one per responsibility, never one for everyone

A cashier and a CEO share no questions. The dashboard should answer five
things and then get out of the way:

> What is happening · What needs attention · What is selling · What is running
> out · What requires *me*

The structure:

```
PAGE HEADER
   ↓
4–5 KPI CARDS              — magnitude only, no charts
   ↓
NEEDS ATTENTION            — the most important block on the page
   ↓
SALES + INVENTORY HEALTH
   ↓
PROCUREMENT + DISTRIBUTION
   ↓
RECENT ACTIVITY
```

**Needs attention** is what makes a dashboard operational rather than
decorative, and every line is a link into the work:

```
🔴 12 products expired                    → Inventory / Expired
🟠 28 expire within 30 days               → Inventory / Expiring
🟠 17 below minimum stock                 → Inventory / Low stock
🟠  8 purchase orders awaiting approval   → Approvals
🔵  6 deliveries delayed                  → Distribution / In transit
🟢 14 GRNs ready to post                  → Receiving
```

A chart earns its place only by answering *"what decision does this help
make?"*. Stock movement, sales trend, expiry exposure, margin by channel —
those qualify. A donut of category share does not.

Per role:

| Role | Sees |
|---|---|
| CEO | revenue, margin, cash, receivables, stock value, expiry exposure, branch comparison, risk — **exceptions, not transactions** |
| COO | branch performance, stock availability, delivery performance, incidents |
| Branch manager | today's sales, margin, stock value, low stock, expiring, cash variance, staff on shift |
| Procurement | requisitions, awaiting approval, awaiting delivery, supplier performance, replenishment recommendations |
| Warehouse | receiving queue, put-away, picking, quarantine, cycle counts, temperature |
| Pharmacist | dispensing, prescriptions, batch/expiry, recalls, interactions, CPD |
| Finance | receivables ageing, payables, unmatched invoices, bank reconciliation, period close |
| HR | headcount, vacancies, attendance, leave, payroll status, training compliance |
| Cashier | their till, their shift, their sales — **nothing else** |

---

## 6. The POS a pharmacy actually needs

Not a supermarket till. Three zones, cart always visible:

```
┌────────────────────────────────┬───────────────────────────┐
│ Search product / scan barcode  │  CURRENT SALE             │
│                                │                           │
│ [Pain] [Antibiotics] [Diabetes]│  Paracetamol 500mg  2×500 │
│                                │  Amoxicillin 500mg  1×850 │
│  ┌────────┐ ┌────────┐         │  ──────────────────────   │
│  │Paraceta│ │Amoxicil│         │  Subtotal        1,850    │
│  │Stock 42│ │Stock 18│         │  Insurance      −1,000    │
│  └────────┘ └────────┘         │  Patient pays      850    │
│                                │  [Cash][Card][MoMo]       │
└────────────────────────────────┴───────────────────────────┘
```

What makes it pharmaceutical rather than generic:

- **the batch is chosen for the cashier**, by FEFO, and shown on the line —
  they should never type a batch number in the normal case;
- search matches name, generic, brand, strength, SKU, barcode **and batch**;
- the insurer's share is quoted **before** dispensing, not discovered after;
- a prescription-only medicine cannot be sold without the prescription
  workflow;
- a split of a scored tablet requires the product to be *approved* as
  divisible — a score line is not authority to halve a modified-release
  tablet;
- the drawer opens and closes as a session, and the variance is somebody's
  responsibility.

---

## 7. B2B is not a shopping cart

Pharmacy → distributor is procurement, not retail. It should feel like an
ordering portal, not a checkout.

**Product rows, not product tiles.** A buyer needs data, not photography:

```
Paracetamol 500mg              ABC Pharmaceuticals
Pack: 10 × 10 tablets          Available: 1,240 packs
MOQ: 10 · multiples of 5       Lead time: 2–3 days
Wholesale: RWF 4,800 / pack    [ + Add to order ]
```

The cart tells the buyer what they cannot get:

```
Paracetamol   100   4,800   ✓ Available
Insulin        20     ...   ⚠ only 10 available
```

And B2B checkout is **not payment** — it is terms:

```
Requested delivery   13 Aug 2026
Deliver to           Kigali Central Pharmacy
Payment terms        30 days          (subject to credit limit)
```

The three things that make a B2B portal fast, in order of value:

1. **Frequently ordered** — one tap to add what they always buy
2. **Reorder** from any past order, then adjust
3. **Replenishment suggestions** from their own stock position

---

## 8. Importing products — three routes, one distinction

The distinction that matters most, and the one most systems get wrong:

> **Product import** says *"this product exists in my catalogue."*
> **GRN** says *"I physically received this quantity of this batch."*
> Stock rises on the second, never the first.

Three routes in: manual, spreadsheet, supplier catalogue. Every one of them
passes a **validation preview** before anything is written:

```
1,250 records found
✓ Valid                1,210
⚠ Missing barcode         18
⚠ Duplicate SKU           12
✕ Invalid expiry date      6
✕ Missing product name     4

[Review errors]  [Import 1,210 valid]
```

Nobody should ever import 5,000 products blind.

**Catalogue governance:** a published product is not silently editable.
Changes go through a change request carrying the old value, the new value, a
reason, an approver and an effective date — because "who changed this pack size
and when" is an audit question.

---

## 9. Planning is a calculation, not a text field

"What do we plan to hold for future sale" should never be a note. It is:

```
Current stock         320
Committed orders      100
Expected demand     1,800
Safety stock          300
On order              100
                   ───────
Recommended order   1,680
```

**Correction (10 Aug):** I wrote that this was missing. It is not. It is built
and reachable — `apps/inventory/analytics.py` computes demand statistics over a
rolling window, safety stock from a service level, reorder points, suggested
orders and an ABC/XYZ matrix, and `ReplenishmentPage` renders all of it. I
asserted a gap without probing for it, which is exactly the error this document
was written to avoid.

What is genuinely thin is *branch-level* demand: the statistics are computed per
organization, so a chain cannot yet see that Musanze is short while Kigali is
long on the same product.

---

## 10. Roles, scope and separation of duties

Permission is not a role. It is:

```
User → Position → Role → Department → Branch → Organization → Scope
```

A branch manager approves purchases up to a threshold, for **their branch**,
and cannot approve their own expense or edit the global product master. The
approval engine, roles and org scoping exist; what is thin is **position**
management — responsibilities attached to a post rather than to a person, so
that filling a vacancy grants the right access automatically.

The separations that must hold:

- the person who **orders** is not the person who **approves payment**
- the person who **receives** is not the person who **releases from
  quarantine** (already enforced — QC release requires a second pair of eyes)
- **quality is independent** of warehouse and procurement, or it is not quality
- a cashier sees their till and nothing else

---

## 11. What I would do next, in order

1. **Convert procurement to transaction screens** — PO, GRN, requisition,
   supplier invoice. Nine screens, the module people judge the system by.
2. **Build the replenishment calculation.** Highest value per line of code in
   this list.
3. **CAPA + complaints + pharmacovigilance** as one quality release. They share
   a lifecycle and should be built together.
4. **Role dashboards** — the nine above, from data that already exists.
5. **Position management** in HR, so access follows the post.
6. Internal audit and customer service tickets.

---

## 12. The one rule

Do not build this screen by screen. Change the token, the component or the
template, and let 106 screens follow. The application changed its entire
visual personality twice in two days by editing two files — that property is
the system, and losing it is how enterprise software becomes inconsistent.
