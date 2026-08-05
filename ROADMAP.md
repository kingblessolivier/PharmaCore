# PharmaCore — Product Roadmap (a workspace of subsystems)

**PharmaCore by Medlink is a pharmacy operations _workspace_** — not one app, but a
family of subsystems that share one identity and an **app‑switcher** ("waffle"),
the way Google Workspace, Microsoft 365, and Oracle ERP modules do. See the
[Brand & Logo System](docs/design/02-brand-and-logo-system.md): one tile shape,
one hue + glyph per subsystem.

> **Mission:** replace the chaos and unprofessionalism in pharmacies with a
> disciplined, compliant, intelligent system — from the moment a medicine is
> imported to the moment it's dispensed, and every count, transfer, payment, and
> signature in between.

## Who we serve (three operator shapes, one platform)
1. **Depot / wholesaler** — imports & procures, warehouses (cold‑chain, zones,
   bins), and distributes to retail pharmacies.
2. **Single retail pharmacy** — over‑the‑counter + prescription dispensing.
3. **Retail chain** — a **headquarters + branches**: central catalog & pricing
   (with local override), inter‑branch transfers, consolidated finance and
   reporting, shared customers — while each branch runs its own counter.

Every subsystem is **tenant‑scoped** and **branch‑aware**: HQ sees across branches;
a branch sees itself. This is the backbone that lets one deployment serve a solo
pharmacy and a 40‑branch chain from the same code.

---

## How pharmacies actually operate (the stages we build for)
Grounded in Good Distribution Practice (GDP), pharmacy ERP practice, and real
depot/retail/chain workflows (see *Research sources* at the end). Each stage maps
to a subsystem below.

| # | Stage | What happens | Key risks it removes |
|---|---|---|---|
| 1 | **Source & import** | Buy from manufacturers/importers; bill of lading, customs, **landed cost**; supplier terms | Wrong cost basis, unrecorded liabilities |
| 2 | **Receive & QA** | Inbound check, cold‑chain verification, **quarantine hold** → release | Accepting damaged/temperature‑abused stock |
| 3 | **Warehouse** | Put‑away by storage condition; **zones** (ambient/2–8 °C/−20 °C), **bins/aisles**, temperature monitoring + excursion alerts | Spoilage, mis‑storage, lost stock |
| 4 | **Catalog & price** | Medicine master (FDA reg, ATC, GTIN), formulary, price lists (wholesale/retail), controlled/Rx flags | Selling unlisted/mis‑priced items |
| 5 | **Distribute (B2B)** | Retail orders from depot / branch↔branch transfers; approve → ship (**FEFO**) → **in‑transit** → receive; B2B **online ordering** | "Ghost stock", re‑keying, oversell |
| 6 | **Dispense (retail)** | OTC + prescription; pharmacist verification, **controlled‑drug register**, cash drawer, receipts, **offline** at the counter | Selling expired/Rx without a pharmacist, till chaos |
| 7 | **Sell online** | Patient storefront, prescription upload, click‑&‑collect / delivery | Missed demand, manual phone orders |
| 8 | **Insurance & fiscal** | Co‑pay split, claims queue + adjudication, **EBM** fiscal receipts (RRA) | Rejected claims, non‑compliant receipts |
| 9 | **Returns & recalls** | Customer returns (credit note), return‑to‑supplier, **batch recall** traceability | Unrecoverable losses, unsafe stock on shelf |
| 10 | **Finance** | AP (suppliers) / AR (buyers, insurers), ledgers, **aging**, EOD closeout, banking/MoMo, **consolidated HQ** books | Cash leakage, blind margins, unpaid debts |
| 11 | **People & training** | Employees, licences & dispensing rights, attendance/shifts/leave, **payroll (PAYE/RSSB)**, **SOP sign‑off + competency** re‑checks | Unlicensed dispensing, untrained staff |
| 12 | **Communicate & warn** | Messaging, announcements, tasks, shift notes; **operational alerts** (expiry, low‑stock, licence, temperature, overdue, controlled thresholds) | Things falling through the cracks |
| 13 | **See everything** | Role dashboards, KPIs, **multi‑branch** analytics, audit trail | Flying blind |

---

## The subsystem map (the workspace apps)
The app‑switcher. Each is one **PharmaCore {App}** tile (hue + glyph per the brand
family). Status reflects what's shipped to `staging` today.

| App | Purpose | Heaviest for | Status |
|---|---|---|---|
| **Admin** (IAM) | Company → HQ → branches; users, roles, licences, settings, tenant scoping | All | ✅ core (companies/branches split pending) |
| **Catalog** | Medicine master, suppliers, manufacturers, price lists, CSV import | All | ✅ done |
| **Inventory & Warehouse** | Batches, storage zones, bins, cold‑chain + excursion, FEFO, counts, quarantine, recalls, expiry alerts | Depot | 🚧 batches/FEFO/expiry done; **zones/bins/temperature/quarantine** planned |
| **Procurement** | Supplier POs, **imports + landed cost**, goods receipt, supplier invoices (AP) | Depot | ⬜ planned (intake exists; formal procurement/import not) |
| **Distribution** | B2B transfers (depot→retail + branch↔branch), approve→ship→in‑transit→receive, B2B **online ordering portal**, settlement | Depot / chain | ✅ core; online ordering portal ⬜ |
| **Retail** (POS) | OTC + Rx dispensing, cash drawer, returns, **offline‑first desktop**, controlled‑drug register | Retail | 🚧 sale core + dispensing gate + returns done; **cash drawer, offline, Tauri** ⬜ |
| **Online** (e‑commerce) | Patient storefront, prescription upload, delivery / click‑&‑collect | Retail / chain | ⬜ planned |
| **Insurance** | Schemes, policies, co‑pay split, claims queue, adjudication, reconciliation | Retail | ⬜ planned |
| **Finance** | AP/AR, chart of accounts, journals, **aging** (built), EOD closeout, banking/MoMo, **EBM fiscal**, consolidated HQ books | HQ / all | 🚧 settlement + aging done; ledgers/EBM/closeout ⬜ |
| **People** | Employees, licences/dispensing rights, attendance/shifts/leave, **payroll**, **training/SOP + competency** | All | ⬜ planned (licence tracking exists) |
| **Connect** (workspace) | Messaging, announcements, tasks, shift notes, comments, **notifications & alerts pipeline** | All | 🚧 comments + @mentions + operational + alert notifications done; full messaging/announcements ⬜ |
| **Insights** | Role dashboards, KPIs, multi‑branch consolidation, analytics, exports | HQ / managers | 🚧 operational dashboard + aging done; report builder/charts ⬜ |

Cross‑cutting (not a tile, present in every app): **Design system**, **Security & audit**,
**Documents/authenticity**, **RBAC & tenant scoping**, **Testing**, **Compliance (GDP/RRA/FDA)**.

---

## What's already built (delivered to `staging`)
Legend: ✅ done · 🚧 in progress · ⬜ planned.

### Foundations ✅
- **Admin/IAM** — JWT auth, argon2, custom `User`, roles/RBAC (deny‑by‑default),
  org (depot/retail/HQ) + department + **Rwanda location** hierarchy, licences,
  append‑only **audit log**. *(Companies↔branches remains a single `Organization`
  with a parent link — a deliberate call; a true companies/branches split is optional.)*
- **Catalog** ✅ — medicine master (FDA reg, ATC, GTIN, route, units/pack,
  controlled schedule, cold‑chain temps, image/leaflet), manufacturers, suppliers,
  ingredients, barcodes, **bulk CSV import**, margin visibility.
- **Design system** ✅ — tokens (light/dark), brand + **subsystem logo family**,
  iconography, components, dashboards spec.

### Inventory 🚧
- ✅ Batch stock, immutable `stock_movements` ledger, **FEFO**, supplier intake
  (depot‑only), adjustments, wastage, **batch source** (recall traceability),
  expiry/low‑stock surfaced on the dashboard, **movement‑history** screen.
- ⬜ Storage **zones & bins**, **temperature monitoring + excursion alerts**,
  formal **quarantine/recall** workflow, physical **stock‑count** sessions.

### Distribution ✅ (core)
- ✅ Lean transfer flow (place → **approve = ship** → **receive = land**),
  FEFO allocation, **in‑transit ledger** (no ghost stock), auto‑list on receipt
  (no re‑keying), **branch↔branch** transfers, wholesale price auto‑pulled,
  **B2B settlement** (record‑payment, status roll‑up), documents (PO/DN/GRN/invoice),
  GRN records. ⬜ B2B **online ordering portal**.

### Retail POS 🚧
- ✅ Sale core (search → FEFO → pay → change → **receipt**), split‑tender API,
  **void**, **partial customer returns + credit note**, **expired‑stock block**,
  **prescription/controlled dispensing gate** (pharmacist required + patient/
  prescriber capture) with a **dispensing log** screen.
- ⬜ Cash‑drawer sessions, **offline‑first** sync, **Tauri desktop** + encrypted
  local SQLite, thermal‑printer, POS calculators.

### Finance 🚧 (started)
- ✅ B2B settlement, **aged receivables & payables** report (per‑partner, bucketed).
- ⬜ Chart of accounts, balanced journals + auto‑posting, EOD closeout, banking/MoMo,
  **EBM fiscalization**, consolidated HQ financials.

### Connect 🚧
- ✅ Contextual comments + @mentions, **operational notifications** (order
  lifecycle, payments) + **daily alert scheduler** (expiry/expired/low‑stock/
  overdue), notification centre (bell).
- ⬜ Direct/branch **messaging**, **announcements**, **tasks**, **shift notes**,
  a rules/preferences **notification pipeline**, email/SMS/desktop channels.

### Insights 🚧
- ✅ Operational **dashboard** (sales today, to‑approve/receive, in‑transit,
  low‑stock, expiring, expired, money in/out, licences), **role‑scoped navigation**.
- ⬜ Report builder, KPI charts (validated palette), **multi‑branch consolidation**.

**Tally so far:** Foundations + Catalog + Distribution core shipped; Retail,
Finance, Connect, Inventory each partially built. ~44 PRs merged; ~105 backend
tests green.

---

## Delivery phases (module‑oriented, foundation‑first)
Each phase makes one or more subsystems materially more complete, end‑to‑end
(backend + UI + design + tests + docs).

- **Phase 0 — Foundations** ✅ — Admin/IAM, audit, CI, scaffolds.
- **Phase 1 — Core data + design system** ✅ — Catalog, Inventory core, org/branch model.
- **Phase 2 — Distribution & Documents** ✅ — the B2B cycle + document engine.
- **Phase 3 — Retail counter** 🚧 (~70%) — POS sale, dispensing gate, returns done;
  **remaining: cash‑drawer, offline‑first sync, Tauri desktop, POS calculators.**
- **Phase 4 — Warehouse depth** ⬜ — storage **zones/bins**, **temperature +
  excursion** monitoring, **quarantine/recall** workflow, stock counts. *(Makes
  Inventory a true WMS for real depots.)*
- **Phase 5 — Procurement & imports** ⬜ — supplier POs, **import + landed‑cost**
  engine, goods receipt, supplier invoices (AP). *(Closes the depot's buy side.)*
- **Phase 6 — Insurance, EBM & the notification pipeline** ⬜ — co‑pay split at POS,
  claims + adjudication + reconciliation, **RRA EBM** fiscal receipts, rules‑based
  notifications + channels.
- **Phase 7 — Finance & consolidation** ⬜ — chart of accounts, journals +
  auto‑posting, EOD closeout, banking/MoMo, **HQ consolidated** books, Insights
  report builder & multi‑branch dashboards.
- **Phase 8 — People, training & SOP** ⬜ — employees, licences/dispensing rights,
  attendance/shifts/leave, **payroll (PAYE/RSSB)**, **SOP library + training +
  competency** sign‑off, controlled‑drug assurance checks.
- **Phase 9 — Online selling & Connect (full)** ⬜ — patient **e‑commerce**
  storefront + prescription upload + delivery/click‑&‑collect; full **messaging,
  announcements, tasks, shift notes, knowledge base**.
- **Phase 10 — Hardening, certification & launch** ⬜ — real EBM adapter + **RRA
  CIS certification**, real insurer integrations, SMS/MoMo adapters, observability,
  backups + restore drill, a11y audit, load/e2e tests, **pilot** at one depot +
  one chain.

> Sequencing rationale: finish the **counter** (Phase 3) because a pharmacy that
> can't sell isn't usable; then make the **warehouse** and **buy side** real
> (4–5) so depots run end‑to‑end; then the **money‑ and compliance‑critical**
> Insurance/EBM/Finance (6–7); then **people/training** and **online/collaboration**
> (8–9); then **certify and launch** (10).

---

## Cross‑cutting workstreams (every phase, part of "done")
- **Design system & brand:** apply the subsystem logo family + app‑switcher; no
  hardcoded colours/spacing; light/dark; a11y (contrast ≥ 4.5:1, keyboard, reduced‑motion).
- **Security & compliance:** deny‑by‑default RBAC, tenant + branch scoping, append‑only
  audit & stock ledger, rate limiting, encryption (transit/at‑rest/field/device),
  **GDP** (immutability/traceability/cold‑chain), **RRA** (EBM/VAT), **Rwanda FDA** licence tracking.
- **Testing:** unit → integration → e2e; compliance tests (immutability/audit); coverage gate.
- **Docs:** keep architecture, data model, API, design, and this roadmap current.

## Explicitly out of scope (v1)
Manufacturing/production (GMP shop‑floor), courier GPS hardware, external chat
federation, and AI clinical decision support beyond basic interaction/duplication checks.

---

### Research sources (pharmacy & ERP operations)
- Good Distribution Practice (GDP) — [Pharmaguideline](https://www.pharmaguideline.com/2022/08/good-distribution-practices.html), [PharmaSource GDP guide](https://pharmasource.global/content/guides/category-guide/good-distribution-practice-gdp-a-comprehensive-guide/)
- Pharmaceutical warehousing & cold chain / FEFO — [Inbound Logistics](https://www.inboundlogistics.com/articles/pharmaceutical-warehousing/), [ASC Software FEFO guide](https://ascsoftware.com/blog/fefo-inventory-management-guide/), [Olimp cold chain](https://olimpwarehousing.com/pharmaceutical-cold-chain-logistics/)
- Pharmacy ERP modules (NetSuite/SAP) — [IntuitionLabs NetSuite in pharma](https://intuitionlabs.ai/articles/netsuite-usage-in-pharma-industry), [ERP Research – SAP for pharma](https://www.erpresearch.com/en-us/sap-for-pharmaceuticals)
- Multi‑branch / chain operations — [LogicERP multi‑store guide](https://www.logicerp.com/blog/how-to-manage-multi-store-pharmacy-chains-with-pharma-retail-erp-software-a-complete-guide/), [Auto‑Star multi‑store POS](https://www.auto-star.com/2025/09/12/how-a-pharmacy-pos-system-can-support-multi-store-operations/)
- Retail dispensing workflow & staff roles — [PBA Health workflow](https://www.pbahealth.com/elements/improve-pharmacy-workflow/), [CCI pharmacy technician day](https://ccitraining.edu/blog/a-day-in-the-life-of-a-pharmacy-technician-all-you-need-to-know/)
- Training, SOPs & controlled‑drug register — [Example SOPs](https://examplesops.com/sops-for-a-pharmacy/), [Pharmaguideline training SOP](https://www.pharmaguideline.com/2014/09/sop-for-training-of-employees.html), [NHS Grampian CD guidance](https://www.nhsgrampian.org/globalassets/services/medicines-management/policies/guide_cd_check.pdf)
</content>
