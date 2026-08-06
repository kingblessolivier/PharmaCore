# PharmaCore — Product Roadmap (a workspace of subsystems)

**PharmaCore by Medlink is a pharmacy operations _workspace_** — not one app, but a
family of subsystems that share one identity and an **app‑switcher** ("waffle"),
the way Google Workspace, Microsoft 365, and Oracle ERP modules do: one tile
shape, one hue + glyph per subsystem, one login, one audit trail.

> **Mission:** replace the chaos and unprofessionalism in pharmacies with a
> disciplined, compliant, intelligent system — from the moment a medicine is
> imported to the moment it's dispensed, and every count, transfer, payment, claim,
> approval, and signature in between.

> **This roadmap is exhaustive on purpose.** It is the master checklist of
> *everything the platform must eventually do* — every subsystem, every operation,
> every document, every integration, every workspace tool, every report, every
> control. Status legend: ✅ done · 🚧 in progress · ⬜ planned. **We build in
> parallel (backend/API and frontend/UI together): a line is ✅ only when the API
> _and_ its page are both shipped, wired, and role‑verified** — API‑only or UI‑only
> stays 🚧 (see [Definition of Done](docs/development/definition-of-done.md)). If
> something a pharmacy does isn't here, it's a gap to add — not an omission by design. The
> **[docs](docs/README.md)** (esp. specs [12](docs/12-requirements-fields-documents-approvals.md)–[19](docs/19-platform-architecture-decisions.md)) carry the research and rationale behind each line.

---

## Who we serve (operator shapes, one platform)
1. **Depot / wholesaler** — imports & procures, warehouses (cold‑chain, zones,
   bins), and distributes to retail pharmacies.
2. **Single retail pharmacy** — over‑the‑counter + prescription dispensing.
3. **Retail chain** — a **headquarters + branches**: central catalog & pricing
   (with local override), inter‑branch transfers, consolidated finance and
   reporting, shared customers — while each branch runs its own counter.
4. **Hybrid / integrated group** — a company that is *both* a depot **and** runs
   retail branches (buy‑side + sell‑side under one roof, one consolidated book).

Every subsystem is **tenant‑scoped** and **branch‑aware**: HQ sees across branches;
a branch sees itself. This is the backbone that lets one deployment serve a solo
pharmacy and a 40‑branch chain from the same code.

---

## How pharmacies actually operate (the stages we build for)
Grounded in Good Distribution Practice (GDP), pharmacy ERP practice, and real
depot/retail/chain workflows (see *Research sources*). Each stage maps to a
subsystem below.

| # | Stage | What happens | Key risks it removes |
|---|---|---|---|
| 1 | **Source & import** | Buy from manufacturers/importers; proforma, bill of lading, customs/clearing, **landed cost**, supplier terms & currency | Wrong cost basis, unrecorded liabilities |
| 2 | **Receive & QA** | Inbound check, batch/expiry capture, cold‑chain verification, **quarantine hold** → QC → release/reject | Accepting damaged/temperature‑abused/counterfeit stock |
| 3 | **Warehouse** | Put‑away by storage condition; **zones** (ambient/2–8 °C/−20 °C/controlled), **bins/aisles**, temperature monitoring + excursion alerts, cycle counts | Spoilage, mis‑storage, lost/ghost stock |
| 4 | **Catalog & price** | Medicine master (FDA reg, ATC/INN, GTIN), **interactions/contraindications**, formulary, price lists (wholesale/retail), controlled/Rx flags | Selling unlisted/mis‑priced/unsafe items |
| 5 | **Distribute (B2B)** | Depot **chooses what/how much to offer** (offered ≠ on‑hand), price schemes/tiers/bonus; retail orders / branch↔branch transfers; approve → ship (**FEFO**) → **in‑transit** → receive; B2B **online ordering**; settlement | "Ghost stock", re‑keying, oversell, unpaid B2B debt, exposing true inventory |
| 6 | **Dispense (retail)** | OTC + prescription; pharmacist verification, **interaction/allergy check**, **controlled‑drug register**, cash drawer, receipts, **offline** at the counter | Selling expired/Rx without a pharmacist, unsafe combos, till chaos |
| 7 | **Sell online** | Patient storefront, prescription upload, click‑&‑collect / delivery, teleconsult hand‑off | Missed demand, manual phone orders |
| 8 | **Insurance & fiscal** | Eligibility, co‑pay split, claims queue + adjudication + reconciliation, **EBM** fiscal receipts (RRA) | Rejected claims, non‑compliant receipts |
| 9 | **Returns, recalls & disputes** | Customer returns (credit note), return‑to‑supplier, **batch recall** traceability, disposal/destruction; **receiving claims/deductions**, **defect/complaint & ADR reporting**, dispute resolution | Unrecoverable losses, unsafe stock on shelf, unresolved claims |
| 10 | **Finance & performance** | AP/AR + **customer credit**, ledgers, **aging/DSO**, closeout, banking/MoMo, tax; **invested capital, gross/net profit, ROI/GMROI** the owner can read | Cash leakage, blind margins, unpaid debts, not knowing if you're profitable |
| 11 | **People & training** | Recruit → onboard → licences & dispensing rights → **automated attendance/overtime/shifts/leave** → **gross→net payroll (PAYE/RSSB/CBHI)** → **SOP + competency** → performance → offboard; **PF‑number login** | Unlicensed dispensing, untrained staff, payroll errors, buddy‑punching |
| 12 | **Communicate & warn** | Messaging, announcements, tasks, shift notes; **operational alerts** (expiry, low‑stock, licence, temperature, overdue, controlled thresholds) | Things falling through the cracks |
| 13 | **Approve & authorise** | Any sensitive action routes to a **central approvals inbox**; claim‑to‑lock, no self‑approval, SLA timeout, escalation | Bottlenecks, unaccountable sign‑off, stalled approvals |
| 14 | **See everything** | Role dashboards, KPIs, **multi‑branch** analytics, exports, audit trail | Flying blind |

---

## The subsystem map (the workspace apps)
The app‑switcher. Each is one **PharmaCore {App}** tile (hue + glyph per the brand
family). The lists below are the **full intended scope** of each app — not just
what's shipped. Status marks each line.

### 1. Admin (IAM & tenancy)
- ✅ JWT auth (argon2), custom `User`, sessions/token refresh.
- ✅ **Staff / PF‑number login** — employees sign in with their **payroll‑file (PF) / staff number** (many counter staff have no email); PF number is the person's key across HR, attendance, payroll, dispensing log & audit.
- ✅ Organisation model (depot / retail / HQ) + parent link (HQ→branch), departments, **Rwanda location** hierarchy (province→district→sector→cell→village).
- ✅ Roles + deny‑by‑default RBAC; append‑only **audit log**.
- ✅ **Formal company ↔ branch split** — a first‑class `Company` above `Organization` (branches), with company CRUD, org attach/detach, and **HQ‑of‑company sees all its branches** scoping. Optional: an Organization may still stand alone with no company.
- ✅ **Permission matrix** — `permission = resource × action` catalogue (23 perms) + `Role.permissions` bundles (seeded for every role), `User.has_permission()` + `HasPermission.require()` DRF class + `can()` frontend helper, `/me` exposes the user's permission codes, and a **SYS_ADMIN‑editable matrix UI** (roles × permissions grid, audited). ⬜ Migrating each endpoint's check from role‑name to permission is incremental.
- 🚧 **User provisioning discipline** — ✅ users are **created only by HR / Admin / Org‑admin** (no self‑signup), ✅ **identity documents** captured & verified per user account (`UserDocument`: national ID / passport / professional licence / contract, admin‑gated, org‑scoped, audited). ⬜ hard‑requiring documents *before* activation is the remaining bit (see [User & pharmacy creation](docs/12-requirements-fields-documents-approvals.md)).
- ✅ **Pharmacy/organisation onboarding** — **compliance‑document capture** (Rwanda FDA / NPC / RDB / RRA / tax clearance) with **verify**, an **onboarding status** (draft → pending → active → suspended) and an **activation gate** (activate / suspend actions), admin‑gated, org‑scoped, audited.
- ✅ **Org settings, feature flags, plan & branding per tenant** — per‑organization **subscription plan** (Basic/Standard/Premium/Enterprise), **brand colour**, and **feature toggles** (online store, insurance, loyalty, B2B portal, offline POS), admin‑managed via the org **Settings** modal (audited).
- 🚧 **Password policy, credential, session & machine access** — ✅ admin **password reset** (forces a change via `must_change_password`), ✅ user **self‑service change**, ✅ **strength validation**, ✅ **force‑logout / session revocation** (token‑version), ✅ **API keys / service accounts** (an `X-API-Key` acts as a chosen user, hashed‑at‑rest, admin‑managed, revocable), all audited. ⬜ MFA (authenticator TOTP — needs the `pyotp` dep + a two‑step login flow), SSO (needs an external IdP).
- ✅ **Admin oversight & monitoring (super‑admin).** The admin can **see and do everything, across every branch and every user** — while RBAC still confines everyone else strictly to their own scope. *(Testing intent: you sign in only as admin, yet must verify each other role sees/does exactly what it should — no more, no less.)*
  - ✅ **View‑as / act‑as (impersonation)** — admin can **enter a specific user's session** and see **exactly what that user sees and can do** (for testing, training & support); every impersonation is **banner‑flagged and audited** (who acted as whom, when, and every action taken).
  - ✅ **Log monitoring** — **audit‑log explorer** (filter by user / action / entity / date + **per‑branch** filter), immutable; per‑user **activity** (recent trail + action counts + last login); **CSV export** of the filtered trail.
  - ✅ **Performance monitoring** — **per‑user & per‑branch KPIs** (sales rung, items dispensed, returns, voids, logins; branch headcount) so the admin can judge **how a person or a pharmacy is performing**.
  - ✅ **User management** — create / edit / suspend / reactivate users, assign roles & scope (PF number + org), **reset credentials** (force‑change), **force‑logout** (revoke all sessions), required‑document onboarding via [user documents].

### 2. Catalog (product master)
- ✅ Medicine master — FDA reg no., **ATC/INN**, GTIN/barcode, brand & generic name, form, strength, route, pack size & units, controlled schedule, cold‑chain temps, image/leaflet, **WHO DDD**, **EML essential flag**, **RxNorm ID**, **lifecycle status**.
- ✅ Manufacturers, suppliers, ingredients/actives, barcodes; **bulk CSV import**; margin visibility.
- ✅ **Drug‑safety data** — drug‑drug **interactions** (DrugBank severity), **contraindications** (ICD-10/SNOMED), caution alerts (feeds the dispensing safety review).
- ✅ **Formulary & coverage** — insurer formularies (RSSB/CBHI/MMI), reimbursable flags, max reimbursable pricing, co-pay % overrides, prior auth flags.
- ✅ **Price lists** — wholesale price list (depot→retail), retail price list, promotional/tiered pricing, effective‑dated pricing, volume break pricing (`min_quantity`).
- ✅ **Units of measure** — pack ↔ each conversions, OTC **increment pricing** (sell by strip/tablet), UoM conversion factors.
- ✅ Alternatives/substitutes (generic equivalents, therapeutic alternatives).
- ⬜ Label/shelf‑talker printing, catalog approval workflow.


### 3. Inventory & Warehouse
- ✅ Batch stock, immutable `stock_movements` ledger, **FEFO**, supplier intake (depot‑only), adjustments, wastage, **batch source** (recall traceability), expiry/low‑stock on dashboard, movement‑history screen.
- ✅ **Storage zones** (ambient / 2–8 °C / −20 °C / controlled/CD safe) + **bins/aisles/locations**; put‑away by storage condition (`StorageZone`, `BinLocation`).
- ✅ **Cold‑chain / temperature monitoring** — device logs, excursion detection + alerts (`NORMAL`, `WARNING`, `CRITICAL_BREACH`), quarantine on excursion (`TemperatureSensor`, `TemperatureLog`).
- ✅ **Quarantine & QC** — inbound hold, QC pass/fail (`pass_qc` releases batch to active stock, `fail_qc` quarantines), release/reject (`QualityCheck`).
- ✅ **Recalls** — batch recall by source, 1-click locate‑and‑freeze across branches (`execute_freeze`), recall notice, disposition (`BatchRecall`).
- ✅ **Stock counts** — cycle counts, full physical inventory, spot checks, variance approval (`approve_count` auto-generates stock movement adjustments) (`StockCount`, `StockCountItem`).
- ⬜ **Reorder management** — min/max/reorder points, par levels, suggested orders, ABC/XYZ analysis, slow/dead‑stock, near‑expiry action lists.
- ✅ **Disposal/destruction** — expired/damaged write‑off with dual witness sign‑off & destruction certificate (`confirm_destruction`) (`StockDisposal`).
- ⬜ **GS1 2D DataMatrix** scan & parse (GTIN + **batch + expiry + serial** in one code) at receipt/dispatch; per‑unit **serialisation & track‑&‑trace** (EPCIS‑ready export for regulated/export markets), aggregation (case→pallet).
- ⬜ **Cold‑chain rigour** — mean‑kinetic‑temperature, calibrated‑sensor register, excursion investigation & disposition record.
- ⬜ **Consignment / vendor‑managed inventory (VMI)** — stock physically held but **owned by the supplier until sold/used** (payment triggers on consumption); and our stock placed on consignment at a customer's site — ownership/liability tracked separately from on‑hand.
- ⬜ Multi‑warehouse per org, put‑away/pick strategies, wave/zone picking (warehouse scale).

### 4. Procurement & imports
- ⬜ **Supplier POs** — raise/approve/send, terms, currency, expected delivery, partial receipt.
- ⬜ **Imports** — proforma, bill of lading, customs/clearing, duties, freight, insurance → **landed‑cost** allocation into unit cost.
- ⬜ **Goods receipt (GRN)** against PO — batch/expiry capture, over/under‑delivery, QC hand‑off to quarantine.
- ⬜ **Supplier invoices (AP)** — 3‑way match (PO↔GRN↔invoice), debit/credit notes, supplier statements & reconciliation.
- ⬜ Supplier master — licences, lead times, price agreements, performance scoring, preferred/blacklist.
- ⬜ Requisitions from branches → consolidated purchasing at HQ; drop‑ship; RFQ/quote comparison.

### 5. Distribution (B2B)
- ✅ Lean transfer flow (place → **approve = ship** → **receive = land**), FEFO allocation, **in‑transit ledger** (no ghost stock), auto‑list on receipt (no re‑keying), **branch↔branch** transfers, wholesale price auto‑pulled, **B2B settlement** (record‑payment, status roll‑up), documents (PO/DN/GRN/invoice), GRN records.
- ⬜ **Offered ≠ on‑hand (the depot decides what to expose).** A depot with 10 boxes may **list only 5**. `offered_qty` is a **published listing** per product, *separate from* physical `on_hand` — the retailer‑facing catalog shows **offered**, never raw stock. Depot can hold back stock (price is rising, reserve for contract customers, hedge), publish in tranches, and set per‑listing price. **Receiving stock does *not* auto‑publish it** — it lands in on‑hand; the depot chooses whether/how much to offer. *(This supersedes the earlier "auto‑list on receipt" behaviour.)*
- ⬜ **Listing controls** — publish/unpublish, offered quantity + **buffer**, effective‑dated **price per listing**, **re‑list on price change** (old offer closes, new price opens), per‑customer / per‑segment visibility, hide‑when‑below‑buffer.
- ⬜ **B2B online ordering portal** — retailers browse the depot's **offered** catalog + their price, place orders, track status, reorder.
- ⬜ **Credit control** — **party‑wise credit & bill limits**, terms, holds on overdue; backorders & **allocation on short/scarce stock**.
- ⬜ **Pricing schemes** — multiple price lists, trade/quantity schemes & discounts, contract/customer‑specific pricing, expiry/near‑expiry sale prompts at billing (see the [Commercial & trade engine](#commercial--trade-engine-the-buying--selling-tricks)).
- ⬜ **Controlled‑substance distribution controls** — **trading‑partner licence verification** (buyer is a licensed pharmacy), **suspicious‑order monitoring** (unusual quantity/frequency flags), **saleable‑returns verification** before restock (Rwanda FDA regime; DSCSA/EPCIS‑aligned for export markets).
- ⬜ **Route/dispatch & delivery** — picking lists, load/manifest, proof‑of‑delivery, driver hand‑off *(full logistics depth; deferred past the lean flow)*.
- ⬜ **Field sales / route‑to‑market** — **sales reps / medical reps**, **pre‑sales** (rep takes orders on a mobile visit) and **van sales** (sell‑from‑stock on the vehicle), **territories/beats + journey plans**, visit logging & call reports, rep **targets & commission/incentive** schemes.
- ⬜ **Institutional & B2G customers** — hospitals, health centres, clinics, NGOs, government; **tender/bid response** (quote to a tender, contract award, scheduled call‑off orders), contract pricing & delivery schedules.
- ⬜ Returns from retailers (return‑to‑depot), statements to customers.

### 6. Retail (POS)
- ✅ Sale core (search → FEFO → pay → change → **receipt**), split‑tender API, **void**, **partial customer returns + credit note**, **expired‑stock block**, **prescription/controlled dispensing gate** (pharmacist required + patient/prescriber capture) with a **dispensing log** screen.
- ⬜ **OTC increment pricing** — sell by strip/tablet/pack with live price as quantity changes; quick‑pick common OTC.
- ⬜ **Cash‑drawer / till sessions** — open/close, float, cash‑up, over/short, blind count, drawer handover, X/Z reports.
- ⬜ **Offline‑first** — encrypted local SQLite + outbox/idempotency sync, server FEFO re‑check on sync (never silently oversell); **Tauri desktop** wrapper.
- ⬜ **Peripherals** — thermal receipt printer, barcode scanner, cash drawer, label printer, customer display.
- ⬜ **Interaction/allergy/duplicate‑therapy safety review (DUR)** at dispense (registered patient), counselling notes.
- ⬜ **Prescription lifecycle** — script intake, **refills & refill‑due reminders**, partial fills, **patient medication history**, prescriber verification.
- ⬜ **Controlled‑drug register** — statutory running balance, witness, quarterly report, receipt‑to‑dispensing audit trail.
- ⬜ Patient/customer lookup, held/parked sales, price overrides (with approval), refunds, exchange.
- ⬜ **Promotions at POS** — apply **coupons / loyalty points / BOGO / bundles / seasonal** offers with **stacking rules + min‑margin floor** (Commercial & trade engine).
- ⬜ **Clinical / pharmacy services** — **vaccinations, injections, point‑of‑care testing/screening (BP, glucose, malaria…), consultations** as **billable services**: service catalog, **appointment scheduling**, consent, service record/notes, follow‑up, and their own receipts/claims.
- ⬜ POS calculators (dose, change, discount, unit price) and quick tools.

### 7. Online (e‑commerce)
- ⬜ Patient **storefront** — browse OTC, search, product info, stock/price by branch.
- ⬜ **Prescription upload** + pharmacist verification queue before Rx items ship.
- ⬜ **Fulfilment** — click‑&‑collect / delivery, address & zones, delivery fees, order tracking.
- ⬜ Patient accounts, order history, reorder, **auto‑refill / subscription**, saved medication profiles, personalised reminders.
- ⬜ **Live pharmacist chat / teleconsultation** hand‑off; diagnostic/appointment booking (future healthcare‑ecosystem hooks).
- ⬜ **Mobile apps** (Android/iOS) alongside the web storefront; push notifications.
- ⬜ Online payments (MoMo/Airtel/card), refunds, online→branch stock routing.
- ⬜ **Promotions & loyalty online** — promo codes, member‑only offers, points earn/redeem, seasonal campaigns (Commercial & trade engine).
- ⬜ Trilingual patient‑facing content (EN/RW/FR).

### 8. Insurance
- ⬜ **Schemes & policies** — `InsuranceProvider` (RSSB/CBHI, RSSB‑medical, MMI, private), policy/tier, **co‑pay %**, formulary, prior‑auth rules, reimbursement period.
- ⬜ **At POS** — capture member/card (scheme/member/group/BIN‑PCN‑style identifiers), **real‑time eligibility**, **prospective DUR** (interactions/duplicate/allergy alert before dispense), **co‑pay split** (patient pays co‑pay; insurer portion → claim), still issue **EBM** receipt.
- ⬜ **Claims queue** — build claims from insured sales via a **standard claim‑format abstraction** (NCPDP/RSSB‑aware); **adjudication** (accepted/declined/**reversed** — e.g. un‑collected script) with reason codes; **prior‑authorization** workflow; **coordination of benefits** (primary→secondary insurer); **resubmit** on rejection via the approval/return engine.
- ⬜ **Reconciliation** — monthly claim manifests per insurer, **remittance advice** posting (EOB to patient / EOP to provider, 835‑style), **aged insurer receivables**, payment matching, short‑pay/denial follow‑up.
- ⬜ Formulary/coverage upkeep (reform‑aware: CBHI category expansions, capitation nuance), scheme‑amount versioning.
- ⬜ Government integration hooks (RSSB digital system, IremboGov context) — mock first.

### 9. Finance
> **The owner/finance‑head must know: how much is invested, how the business is performing (gross & net profit + margins), who owes us and how old, and is cash safe.**
- ✅ B2B settlement, **aged receivables & payables** (per‑partner, bucketed).
- ⬜ **Chart of accounts**, double‑entry **journals** + auto‑posting from sales/purchases/stock/payroll, sub‑ledgers.
- ⬜ **AP** — supplier bills, 3‑way match, payment runs, **MoMo disbursements**, supplier statements/reconciliation, DPO.
- ⬜ **AR & customer credit management** — customer invoices (buyers + insurers), receipts, **credit application → credit scoring → credit limit**, **credit terms** (net 30/45, 2/10 net 30), **credit holds** on breach/overdue, **aging + DSO**, **statements of account**, **collections/dunning** ladder, write‑offs/bad‑debt provision.
- ⬜ **Banking & cash** — bank/MoMo/Airtel accounts, reconciliation, petty cash, cash‑book, cash‑flow forecast.
- ⬜ **Tax** — VAT (class B = 18%), **EBM fiscalisation** (OSDC), withholding, tax reports/returns.
- ⬜ **Investment & equity** — capital invested, owner's equity, drawings, retained earnings, capital‑vs‑expense classification, fixed‑asset register + depreciation.
- ⬜ **Business performance** — **gross profit / gross margin**, **net profit / net margin**, COGS, operating expenses, EBITDA, **ROI / ROE / GMROI**, **DSO/DPO**, break‑even, stock turns; a **performance cockpit** (period compare, per‑branch) the leader reads at a glance.
- ⬜ **Period close** — EOD/EOM closeout, trial balance, **P&L, balance sheet, cash‑flow**; **HQ consolidation** across branches.
- ⬜ **Inventory valuation & costing** — costing method (weighted‑average / FEFO‑lot cost), **lot‑level valuation**, stock valuation & COGS posting, revaluation, shrinkage/write‑off to GL.
- ⬜ **Budgets & costing** — budgets vs actual, cost centres, margin & profitability analysis.
- ⬜ **Finance documents** — invoices, credit/debit notes, receipts, statements, remittance, vouchers, EOD/EOM reports (see [Documents catalog](#documents-catalog)).
- ⬜ Multi‑currency (imports), fixed assets/depreciation (light).

#### 9.1 Finance — Design (global)

**Architecture:** a Django app `apps/finance/` over the shared PostgreSQL, double‑entry from day one. Every money‑moving domain event (sale finalised, supplier bill approved, payroll run approved, inventory adjustment, asset depreciation) emits a **journal entry** through a `JournalPostingService`. Posters are idempotent on `(source_doc, source_line)` so retries are safe.

**Core entities:**
`ChartOfAccounts`, `FiscalPeriod`, `PeriodClose`, `JournalEntry`, `JournalLine`, `JournalSource` (enum: `SALE / PURCHASE / PAYROLL / INVENTORY_ADJ / MANUAL / OPENING_BALANCE / FX / DEPRECIATION / BANK_RECON / STATUTORY_PAYMENT`), `Customer`, `Supplier` (financial extensions of distribution masters), `CustomerInvoice`, `SupplierInvoice`, `InvoiceLine`, `CreditProfile`, `Receipt`, `Payment`, `PaymentAllocation`, `BankAccount`, `BankStatement`, `BankReconciliation`, `MoMoTransaction`, `TaxRecord` (VAT / PAYE / WHT), `EBMReceipt`, `FixedAsset`, `DepreciationSchedule`, `Budget`, `CostCenter`, `NumberSequence` (per‑tenant invoice/PO/GRN/journal numbering), `OpeningBalance`.

**Seeded Rwanda‑appropriate CoA groups:** 1000 Assets (1100 Cash, 1200 Bank, 1300 MoMo, 1400 AR Trade, 1500 Inventory, 1700 Fixed Assets), 2000 Liabilities (2100 AP Trade, **2200 PAYE Payable, 2210 RSSB Pension Payable, 2220 RSSB Maternity Payable, 2230 CBHI Payable, 2240 Occupational Hazards Payable, 2250 RAMA Payable**, 2300 VAT Payable, 2400 EBM Liability, 2500 WHT Payable), 3000 Equity, 4000 Revenue (4100 Retail, 4200 Wholesale, 4300 Services), 5000 COGS, 6000 Expenses (**6100 Salaries, 6110 Employer RSSB Pension, 6120 Employer Maternity, 6130 Occupational Hazards Insurance, 6140 RAMA Employer**), 7000 Tax.

**Statutory sub‑ledgers as first‑class GL accounts** (not a side table): PAYE/RSSB/CBHI/Occ‑Hazards/RAMA/VAT/WHT are all `2200‑level` (or 2300 for VAT) accounts. Auto‑posting populates them; the **Statutory Due** dashboard reads balances directly and generates the RRA/RSSB return files.

**APRs & controls:**
- **3‑way match** — `SupplierInvoice` cannot be approved until `GRN` + `PurchaseOrder` reconcile (qty, unit price, totals); variance creates an **approval‑engine** item.
- **Payment runs** — batched, dual approval above threshold (Finance manager + Director), generates bank/MoMo disbursement files with idempotency keys.
- **Period close** — `FiscalPeriod.status` transitions `Open → Soft‑Closed → Hard‑Closed`; reopen requires an audit‑recorded reason.
- **HQ consolidation** — inter‑branch intercompany transactions generate elimination entries at EOM.

**Pages:** Chart of Accounts (tree + journal inspector), Journals (search/drill/posting source), AR (aging, statements, dunning queue), AP (bills, 3‑way match, payment runs), Invoices (list/detail/PDF), Payments (runs, MoMo/bank files, reconciliation), Statutory (PAYE/RSSB/VAT schedules + filings tracker), Banking (accounts, statement import, reconciliation), Fixed Assets, Period Close (EOD/EOM, trial balance, P&L, BS, CF, multi‑branch consolidation), Reports (standard + report builder).

#### 9.2 Finance — Dataflows

```
[SaleFinalised (POS)]
   └─► JournalPostingService.post('SALE', sale_id)
        Dr AR/Cash/MoMo  (split by tender)
        Cr 4100/4200 Sales Revenue
        Cr 2300 VAT Output         (18% class B)
        Dr 5100 COGS
        Cr 1500 Inventory          (lot‑level cost)

[SupplierBillApproved]
   └─► post('PURCHASE', bill_id)
        Dr 1500 Inventory / 6xxx Expense
        Dr 2300 VAT Input
        Cr 2100 AP Trade

[PaymentReceived]
   └─► post('PAYMENT', receipt_id) + allocate
        Dr 1200 Bank / 1300 MoMo
        Cr 1400 AR  (per allocation)

[PaymentMade]
   └─► post('PAYMENT', payment_id)
        Dr 2100 AP
        Cr 1200 Bank / 1300 MoMo

[PayrollRunApproved]               (← from People)
   └─► post('PAYROLL', payroll_run_id)   ← see 10.2 cross‑system flow

[InventoryAdjustment / Disposal]
   └─► post('INVENTORY_ADJ', source_doc)
        Dr 5900 Inventory Adjustments (or 6xxx Shrinkage)
        Cr 1500 Inventory

[StatutoryPayment (PAYE/RSSB/VAT)]
   └─► post('STATUTORY_PAYMENT', filing_id)
        Dr 2200/2300 Payable
        Cr 1200 Bank

[BankReconciliation]
   └─► post('BANK_RECON', recon_id) for matched lines
        Dr/Cr 1100 vs 1200 (eliminate timing diff)

[AssetDepreciation]
   └─► post('DEPRECIATION', schedule_id)
        Dr 6xxx Depreciation Expense
        Cr 1701 Accumulated Depreciation
```

### 10. People (HR & payroll)
> **Who works here, what they earn, how it's calculated & deducted, and are they present** — the leader must see all of it at a glance.
- ⬜ **Employee master** — PF/staff number, personal + next‑of‑kin, contract type, grade/step, department/branch, bank/MoMo, **RSSB number**, TIN, salary structure (base + allowances), start date, reporting line.
- ⬜ **Recruitment (external)** — requisition, job posting, applicants, shortlisting, interviews, offer → converts to onboarding.
- ⬜ **Onboarding** — contract, **documents** (ID, licences, certificates, CV, contract), asset/equipment issue, induction checklist.
- ⬜ **Licences & dispensing rights** — pharmacist/tech licences (NPC/board) + expiry tracking gating dispensing; **CPD/CE hour logging + renewal alerts**.
- ⬜ **Automated attendance** — **clock in/out** (biometric / PIN / **PF number** / device), auto‑build timesheets, lateness/absence flags, **overtime** auto‑calc from rostered vs worked hours, **shift premiums**, break rules; corrections via approval.
- ⬜ **Shifts & rostering** — shift patterns, **credential‑based scheduling** (only valid‑licence staff; every shift has a pharmacist on cover), coverage rules across branches, shift swaps, roster publish.
- ⬜ **Leave** — types & balances, accrual, requests→approval, calendar, carry‑over, encashment; feeds payroll.
- ⬜ **Payroll — gross → net engine.** **Gross** = base + allowances (incl. **transport allowance**, now in the contributory base) + **overtime** + bonus/commission + shift premium. **Deductions** = **PAYE** (bands 0/10/20/30%) + **RSSB pension 6% employee** + **maternity 0.3% employee** + **CBHI 0.5% of net** + loans/advances/salary‑advance + union/other; employer side (RSSB 6% + maternity 0.3%) computed for cost. **Net = gross − deductions.** Versioned, effective‑dated `statutory_rates`; **payslips**, bank/MoMo **pay run**, statutory **filings/returns**, payroll journal → Finance.
- ⬜ **Payroll controls** — payroll register, run approval (no self‑approval), reprocessing, arrears/back‑pay, proration for joiners/leavers, 13th‑cheque/bonus runs, **payroll calculator** (see [calculators](#c-workspace-tools-the-utility-belt)).
- ⬜ **Training & SOP** — SOP library, assign‑and‑acknowledge, training courses/records, **competency assessments** + periodic re‑checks, controlled‑drug competency.
- ⬜ **Performance** — reviews, goals, disciplinary, warnings, promotions/transfers, salary revisions (history).
- ⬜ **Offboarding** — resignation/termination, clearance checklist, **final settlement** (leave encashment, dues), de‑provision login, exit interview, certificate of service.
- ⬜ **HR documents** — contract, offer letter, payslip, leave approval, warning/disciplinary letter, training/competency certificate, clearance, certificate of service, ID/licence copies (in the document vault, retention‑policied).
- ⬜ **Self‑service & reporting** — employee portal (payslip/leave/attendance), org chart, headcount/turnover/attendance/leave‑liability reports.
- ⬜ **External HR touchpoints** — RSSB (registration, contribution filing), RRA (PAYE), NPC (pharmacist registration), labour‑law compliance.

#### 10.1 People — Design (global)

**Architecture:** Django app `apps/hr/` over the shared PostgreSQL. The **payroll engine is a pure function**: `payroll(employee_inputs × StatutoryRate effective on period_end) → Payslip`. Reproducible, re‑runnable, auditable. Rwanda compliance is **data, not code** — versioned, effective‑dated `StatutoryRate` rows; the engine never hardcodes bands or rates.

**Core entities:**
`Employee` (with `pf_number` as the cross‑system key), `EmploymentContract`, `SalaryStructure`, `SalaryComponent` (`code ∈ {basic, housing, transport, responsibility, other, contributory_to_pension}`, `flag`), `SalaryRevision`, `StatutoryRate` (see §C), `AttendanceLog`, `Timesheet`, `Shift`, `ShiftRoster`, `RosterAssignment` (with `coverage_role` for credential checks), `LeaveType`, `LeaveBalance`, `LeaveRequest`, `LeaveAccrual`, `LoanAdvance`, `LoanInstallment`, `PayrollRun`, `Payslip`, `PayslipLine` (itemised gross/deductions/net/employer_cost), `PayrollAdjustment` (retro/arrears), `StatutoryFiling`, `ProfessionalLicence`, `CPDRecord`, `TrainingRecord`, `CompetencyAssessment`, `DisciplinaryAction`, `PerformanceReview`, `EmployeeDocument`.

**Payroll run lifecycle:**
`Draft  →  Calculated  →  Approved (no self‑approval)  →  Paid (bank/MoMo file generated)  →  Locked (immutable)`. Locks freeze attendance, leave balances, loan schedules, and `StatutoryRate` resolution for the period; any later change requires a **payroll adjustment** in a future run.

**Cross‑system permissions on employees:** an employee cannot be terminated while an open payroll run references them; a run cannot be approved until all timesheets are approved; statutory filing cannot be marked filed unless the underlying GL sub‑ledger balance ties out.

**Pages:** Dashboard (headcount, today's attendance, pending approvals, payroll due, licence expiries, training compliance %), Employees (list/detail/contracts/documents/salary history), Attendance (live clock feed, exceptions, corrections), Shifts/Roster (week view, publish, swaps, credential check), Leave (calendar/requests/balances), Payroll (Run list, Run detail, Register, Calculator, Approve, Payslips), Loans/Advances, Training & Licences (expiry heat‑map, CPD tracker), Reports (headcount, turnover, leave liability, payroll cost), Employee self‑service (payslips, leave requests, attendance view, profile).

#### 10.2 People — Dataflows

```
[Biometric/PIN/PF device]
   └─► POST /api/attendance/clock  → AttendanceLog
                                       ↓
[Roster published]
   + Timesheet auto‑build (worked/overtime/late)  → Manager approves
                                                       ↓
[Leave approved]      ──┐
[Loan installment due] ──┤
                       ├─►  PayrollRun.Calculated (per employee)
[StatutoryRate resolved]│      payslips = pure fn(employee_inputs × rate)
[Salary revision freeze]│
                       │
[Manager / Finance / Director review & approve]  ──►  PayrollRun.Approved
                                                       │
                                                       ├─► Payslips published (employee self‑service)
                                                       ├─► Net pay → Bank/MoMo file (idempotency key)
                                                       ├─► PAYE + RSSB unified filing generated (due 15th next month)
                                                       └─►► EVENT: PayrollRunApproved
                                                                  │
                                                                  └─►► Finance.JournalPostingService.post('PAYROLL', run_id)
                                                                            (see §9.2)

[StatutoryPaymentConfirmed (PAYE / RSSB paid)]
   └─► EVENT: StatutoryPaid
          └─► Finance clears 2200‑level payable accounts
          └─► HR.StatutoryFiling.status = 'FILED_PAID'
          └─► Audit log entry

[Termination approved]
   └─► HR computes Final Settlement (leave encash + pro‑rata + dues)
   └─► Employee.user.is_active = False; de‑provision login
   └─► Finance posts termination accrual (if any) + Schedule of service document
```

#### 10.3 Gross‑to‑Net formula (Rwanda, versioned by `StatutoryRate`)

```
gross = basic + housing + transport + responsibility + other
      + overtime_pay + shift_premium + bonus − unpaid_leave_deduction

paye  = marginal_tax(gross − non_taxable, PAYE_BAND)        # 0/10/20/30% bands

rssb_pension_ee = gross_incl_transport × RSSB_PENSION_EE    # 6% (2025)
maternity_ee    = (gross − transport)      × RSSB_MATERNITY_EE   # 0.3%
cbhi_ee         = (gross − paye − rssb_pension − maternity)
                                                  × CBHI_EE  # 0.5% on net
rssb_pension_er = gross_incl_transport × RSSB_PENSION_ER    # 6%
maternity_er    = (gross − transport)      × RSSB_MATERNITY_ER   # 0.3%
occ_hazards_er  = gross                    × OCC_HAZ_ER     # 2%
rama_ee, rama_er (if opted in)              × RAMA_EE / RAMA_ER  # 7.5%+7.5% on basic

net = gross − paye − rssb_pension_ee − maternity_ee − cbhi_ee − other_deductions
```

The Labour Code (Law N° 66/2018, Art. 70) governs pay periods (daily/weekly/fortnightly/monthly). For formal‑sector monthly employees the **15th of the following month** is the practical deadline driven by PAYE/RSSB remittance rather than a calendar day stated in the Code (the 2009 7‑working‑day rule was removed in 2018). Statutory filing deadlines (PAYE / RSSB monthly: 15th; PIT annual: 31 March) are encoded on `StatutoryFiling.due_date` and surface on the Statutory Due dashboard.

### Cross‑cutting engines (added — referenced by HR + Finance + every subsystem)

These are first‑class subsystems that didn't previously exist as named sections. They are the backbone that the People (HR) and Finance subsystems — and every other sensitive action — depend on. See the original §A Approvals engine block below for the spec of (A).

#### C. Statutory rates engine (Rwanda‑first, versioned)

A single, **effective‑dated** table that owns every rate the system uses to compute or report compliance. Rwanda compliance is **data, not code** — so a new Finance Law, a phased pension rise, or an RSSB bulletin changes one row, not a code deploy.

- **Entity:** `StatutoryRate(code, valid_from, valid_to, params JSONB, source_url, published_by, status)`
- **Codes (seeded; expand as needed):**
  - `PAYE_BAND` — `params.bands = [[60000, 0.00], [100000, 0.10], [200000, 0.20], [null, 0.30]]`
  - `RSSB_PENSION_EE`, `RSSB_PENSION_ER`, `RSSB_PENSION_BASE` (gross_incl_transport)
  - `RSSB_MATERNITY_EE`, `RSSB_MATERNITY_ER`, `RSSB_MATERNITY_BASE` (gross_excl_transport)
  - `OCC_HAZARDS_ER`, `OCC_HAZARDS_BASE` (gross)
  - `CBHI_EE`, `CBHI_BASE` (net_after_paye_rssb_maternity)
  - `RAMA_EE`, `RAMA_ER`, `RAMA_BASE` (basic), `RAMA_MIN_HEADCOUNT` (7)
  - `VAT_CLASS_B` (0.18), `WHT_RATES`, `EBM_PROVIDER`
- **Resolution rule:** `(code, period_end_date)` → row where `valid_from ≤ period_end < valid_to`. The payroll engine, the statutory filing generator, and the Finance tax sub‑ledger all read from this resolver.
- **Auditability:** every published row stores `source_url` (RRA / RSSB / Official Gazette) and `published_by`. Publishing a new rate requires approval (Finance manager + Director).
- **Seed data (Rwanda 2025/26):** PAYE bands from Organic Law N° 026/2024 (effective fiscal year 2025); pension 6%+6% with scheduled rises in 2027/2028/2029/2030 (Presidential Order N° 086/01, gazetted 13 Dec 2024); maternity 0.3%+0.3% (Law N° 003/2016 amended by Law N° 049/2024); CBHI 0.5% on net (Prime Minister's Order N° 034/01 of 13/01/2020); occupational hazards 2% ER (Law N° 13/2009); RAMA 7.5%+7.5% on basic; VAT 18% class B.
- **Source‑of‑truth UI:** Admin → Statutory Rates (timeline view, diff between consecutive rows, "Publish rate" wizard that requires a source URL).

#### D. Domain event bus (the integration backbone)

A thin in‑process pub/sub with a Django Signals core and an outbox table for reliable cross‑subsystem delivery. Every money‑ or compliance‑relevant action publishes a domain event; consumers in HR, Finance, Distribution, Documents, Reporting subscribe.

- **Entity:** `OutboxEvent(id, event_type, payload JSONB, occurred_at, status [pending/published/failed], retries)`
- **Pattern:** producers `transaction.on_commit(lambda: outbox.publish(...))`; consumers register `subscribe(event_type, handler)`; a worker dispatches pending events, retries with backoff, marks published.
- **First‑class events (seeded; new ones added per subsystem):**
  - `SaleFinalised`, `SaleReturned`, `EBMReceiptIssued`
  - `PurchaseOrderApproved`, `GoodsReceivedNotePosted`, `SupplierBillApproved`
  - `InventoryAdjusted`, `BatchQuarantined`, `BatchRecalled`, `StockDisposed`
  - `EmployeeHired`, `EmployeeTerminated`, `TimesheetApproved`, `PayrollRunApproved`, `PayslipPublished`, `StatutoryFilingGenerated`, `StatutoryPaymentConfirmed`
  - `CustomerInvoiceIssued`, `PaymentReceived`, `PaymentMade`, `CreditLimitChanged`, `CreditHoldEngaged`
  - `FiscalPeriodOpened`, `FiscalPeriodClosed`, `PeriodReopened`, `EODCloseFinalised`, `EOMCloseFinalised`
  - `ApprovalRequested`, `ApprovalClaimed`, `ApprovalGranted`, `ApprovalRejected`, `ApprovalEscalated`, `ApprovalSLABreached`
- **Idempotency:** consumers must be idempotent on `(event_type, source_doc_id, source_line_id)`. The outbox guarantees at‑least‑once delivery; consumers tolerate duplicates.
- **Why:** removes tight Django imports between apps, makes HR ↔ Finance ↔ Distribution integration testable in isolation, gives Finance a reliable stream to post journals from, and gives Reporting a real‑time feed.

#### E. Numbers, periods & opening balances (cross‑cutting infrastructure)

Previously scattered; now first‑class.

- `NumberSequence` — per‑tenant, per‑type (Invoice/PO/GRN/Payroll/Journal/Document). Gapless, monotonic, transactional; the document engine calls `next_number(tenant, 'INVOICE')` under `SELECT … FOR UPDATE`.
- `FiscalPeriod` — calendar (month) + custom (4‑4‑5 retail). `Open → SoftClosed → HardClosed`. Reopening requires approval + audit reason.
- `OpeningBalance` — opening stock (batches + qty + valuation), opening AR/AP (with aging preserved), opening GL trial balance, opening employee/leave balances. Migration wizard validates that the sum ties out before committing.
- `TenantSettings` (already partially via Admin) — `costing_method ∈ {wac, fefo_lot}`, `currency`, `fx_provider`, `default_country='RW'`, `pay_period ∈ {monthly, fortnightly, weekly}`, `statutory_remittance_day=15`, `pit_filing_deadline_month=3, day=31`.

### Subsystem integration & event flows (People ↔ Finance ↔ the rest)

The single source of integration truth — read this when implementing or reviewing any cross‑app change.

```
                        ┌──────────────────────────────────────────┐
                        │          OutboxEvent / Domain Bus        │
                        │  (Django Signals + outbox table, §D)     │
                        └──────────────────────────────────────────┘
                                    ▲      ▲      ▲      ▲
                                    │      │      │      │
                  People(HR)        │      │      │      │     Finance
                  ──────────        │      │      │      │     ────────
                  PayrollRunApproved─►    │      │      │
                  StatutoryFilingGen──►    │      │      │
                  StatutoryPaymentCnf─►   │      │      │
                  EmployeeHired ──────────►│      │      │
                  EmployeeTerminated ─────►│      │      │
                                            │      │      │
                  Inventory                │      │      │
                  ──────────               │      │      │
                  BatchQuarantined ─────────►│      │      │
                  StockDisposed ────────────►│      │      │
                  InventoryAdjusted ────────►│      │      │
                                            │      │      │
                  Distribution              │      │      │
                  ─────────────             │      │      │
                  PurchaseOrderApproved ─────►│      │      │
                  GoodsReceivedNotePosted ──►│      │      │
                                            │      │      │
                  Retail                    │      │      │
                  ──────                    │      │      │
                  SaleFinalised ─────────────►│      │      │
                  PaymentReceived ───────────►│      │      │
                  PaymentMade ───────────────►│      │      │
                                            │      │      │
                                            ▼      ▼      ▼
                                  ┌──────────────────────────┐
                                  │ Finance JournalPostingSvc│
                                  │   (idempotent on src_doc) │
                                  └──────────────────────────┘
                                            │
                                            ▼
                                  ChartOfAccounts (1000‑7000)
                                  Statutory sub‑ledgers (2200‑level)
                                  PeriodClose → Reports
```

**Key end‑to‑end flows (numbered for traceability):**

1. **Payroll → GL → Statutory payment**
   `PayrollRunApproved` → `post('PAYROLL')` (Dr Salaries/ER costs, Cr PAYE/RSSB/CBHI/Occ‑Hazards/Cash) → `StatutoryFilingGenerated` (due 15th) → on pay‑day `StatutoryPaymentConfirmed` → `post('STATUTORY_PAYMENT')` (Dr payable, Cr Bank).

2. **Sale → GL → EBM**
   `SaleFinalised` → `post('SALE')` (Dr Cash/MoMo/AR, Cr Sales + VAT) → COGS posting (Dr COGS, Cr Inventory at lot cost) → async `EBMReceiptIssued` → `EBMReceipt` stored with SDC signature + QR.

3. **Supplier goods receipt → 3‑way match → GL**
   `GoodsReceivedNotePosted` → when matching `SupplierBillApproved` → `post('PURCHASE')` (Dr Inventory/Expense + VAT Input, Cr AP). Variance → approval engine.

4. **Inventory adjustment / disposal → GL**
   `InventoryAdjusted` / `StockDisposed` → `post('INVENTORY_ADJ')` (Dr Shrinkage / Write‑off, Cr Inventory). Always approval‑gated.

5. **Credit control**
   `CustomerInvoiceIssued` → updates `CreditProfile.outstanding`; if `> credit_limit` or `> terms.days_overdue` → `CreditHoldEngaged` → Distribution rejects new orders for that customer.

6. **Period close**
   `EODCloseFinalised` → trial balance snapshot. `FiscalPeriodClosed` (EOM) → P&L/BS/CF reports generated; HQ consolidation runs elimination entries for inter‑branch transactions.

7. **Approval lifecycle** (used by every flow above)
   `ApprovalRequested → ApprovalClaimed (lock) → ApprovalGranted | ApprovalRejected`. SLA timer auto‑escalates per the [approval rules](docs/02-architecture.md); no self‑approval; supervisor‑of / senior oversight (see [approvals block](#a-approvals-engine-the-reusable-authorisation-backbone)).

**Validation invariants (cross‑system integrity):**
- A payroll run cannot be approved while any timesheet is pending.
- A statutory filing cannot be marked `FILED_PAID` unless the GL sub‑ledger balance equals the filing amount.
- An employee cannot be terminated while referenced by an open payroll run.
- A `FiscalPeriod` in `HardClosed` rejects all postings except reversal entries (audit‑recorded).
- A `CreditProfile.on_hold = True` blocks new B2B orders in Distribution.

### 11. Connect (workspace & communication)
- ✅ Contextual comments + @mentions, **operational notifications** (order lifecycle, payments) + **daily alert scheduler** (expiry/expired/low‑stock/overdue), notification centre (bell).
- ⬜ **Messaging** — direct & group/branch chat, threads, attachments.
- ⬜ **Announcements** — org/branch broadcasts, acknowledgement tracking.
- ⬜ **Tasks** — assignable to‑dos, due dates, checklists, recurring tasks, per‑subsystem task hooks.
- ⬜ **Shift notes / handover log** — end‑of‑shift notes, read‑receipts.
- ⬜ **Notification pipeline** — rules & user preferences, **channels** (in‑app, email, **SMS**, desktop), digest vs real‑time, escalation.
- ⬜ Knowledge base / help centre, pinned SOPs.

### 12. Insights (analytics & reporting)
- ✅ Operational **dashboard** (sales today, to‑approve/receive, in‑transit, low‑stock, expiring, expired, money in/out, licences), **role‑scoped navigation**.
- ⬜ **Report builder** + scheduled/exported reports (PDF/CSV/Excel).
- ⬜ **KPI charts** (validated colour‑blind‑safe palette) — sales, margin, stock turns, expiry exposure, aging, claims, footfall.
- ⬜ **Multi‑branch consolidation** & comparison, drill‑down, period compare.
- ⬜ Per‑role dashboards (cashier, pharmacist, branch manager, HQ exec, finance, HR).
- ⬜ **Admin monitoring cockpit** — cross‑tenant/branch **activity feed**, **per‑user & per‑branch performance**, session + **audit‑log explorer** (the analytics face of [Admin oversight](#1-admin-iam--tenancy)).
- ⬜ Data warehouse/exports, forecasting (demand), anomaly flags.

### Cross‑cutting apps (present in every subsystem)

#### A. Approvals engine (the reusable authorisation backbone)
Any sensitive action (price override, write‑off, discount beyond threshold, PO,
payroll run, claim resubmit, stock adjustment, user creation, disposal…) routes here.
- ⬜ **Central approvals inbox** — every pending approval across subsystems in one queue.
- ⬜ **Claim‑to‑lock** — an approver *claims* an item; it's then hidden/locked from others (no double‑work).
- ⬜ **No self‑approval** — the requester can never approve their own item; supervisor / senior can.
- ⬜ **SLA timers** — each approval has a deadline; on timeout it **returns** (needs resend) and re‑enters the queue — *nothing is ever silently stuck*.
- ⬜ **Escalation & oversight** — a senior leader sees **all** pending approvals and can **forward/reassign**; supervisor‑of‑X can approve for X.
- ⬜ **Multi‑step / parallel** approval chains, delegation while away, full **e‑signed** audit (actor + timestamp + immutable trail).

#### B. Documents & authenticity
- 🚧 Document engine for B2B (PO/DN/GRN/invoice).
- ⬜ **Every legal/finance/HR/clinical document** as a template (see [Documents catalog](#documents-catalog)); tamper‑evidence (QR/hash/signature), multi‑company logos, retention policy per type, e‑signature, PDF vault + versioning.

#### C. Workspace tools (the "utility belt")
- ⬜ **To‑do lists** (personal + assigned via Connect), **calendar** (shifts, expiries, licence renewals, deliveries, paydays), **notes**, **document‑templates** picker, quick search/command palette.
- ⬜ **Internal calculators** — **payroll gross→net** (PAYE + RSSB pension + maternity + CBHI + loans), **overtime**, **margin/markup**, **VAT** (inclusive/exclusive), **GMROI / ROI / ROE**, **DSO/DPO**, **landed‑cost**, **reorder‑point/par**, **discount & change**, **unit‑price / OTC increment**, **dose**. Each pulls live config (statutory rates, tax class) so results match the books.

#### D. Platform (non‑functional, every app)
- **Design system & brand**, **Security & audit**, **RBAC & tenant/branch scoping**, **Compliance (GDP/RRA/FDA/Data‑Protection)**, **Testing**, **Offline/sync**, **Notifications** — detailed in [Platform & non‑functional](#platform--non-functional-must-hold-across-every-subsystem).

---

## Commercial & trade engine (the buying & selling "tricks")
Real depots and pharmacies don't just move stock at one price — they run a
commercial game. The system must **model these tactics as first‑class**, not force
operators to fake them in spreadsheets. (Researched & cited below.)

### Selling side (depot → retailer, and retail → patient)
- ⬜ **Offered vs on‑hand** — publish fewer units than you hold; hold stock back against a **price rise**, reserve for contract customers, or release in **tranches** (the core model above).
- ⬜ **Effective‑dated pricing & re‑list on price change** — price changes open a new listing; old offers close. Full **price history** for audit and margin analysis.
- ⬜ **Tiered / volume discounts** — cheaper unit price at higher quantities; **cumulative (retroactive) discounts** — "buy X over 6 months → rebate/credit."
- ⬜ **Free goods / bonus schemes** — "buy 10 get 1 free", bonus quantity, sample packs (stock‑ and margin‑accurate, not a hidden price cut).
- ⬜ **Minimum order quantity (MOQ)** & **case‑pack / multiples** rules; waive MOQ for a first order.
- ⬜ **Trade / contract / per‑customer price lists** — different prices for different buyers/segments; promotional pricing windows.
- ⬜ **Payment‑terms levers** — **early‑payment discount** (e.g. 2/10 net 30), **credit terms** (net 30/45) as a closing tool, party‑wise **credit & bill limits**, holds on overdue.
- ⬜ **Short‑dated & slow‑mover tactics** — discount **near‑expiry** stock to push turnover; **bundle** slow movers with fast movers (auto‑bundler suggestions); near‑expiry **action lists**; expiry prompts at billing.
- ⬜ **Allocation on scarcity** — when stock is short, ration across buyers by rule (fair‑share / priority customer).
- ⬜ **Returns levers** — accept near‑expiry returns within a **window** (e.g. 90–120 days before expiry) where credit recovery beats a markdown.

### Buying side (import / procurement)
- ⬜ **Forward / investment buying** — buy ahead of an expected **price increase**; **deal buying** on supplier promotions (track the deal, its expiry exposure, and the true landed cost).
- ⬜ **Volume & framework contracts** — bulk/multi‑year commitments for a better rate; **volume‑price contracts**; **pooled/joint purchasing** for bargaining power.
- ⬜ **Tendering & sourcing** — open / restricted / direct / negotiated / shopping; **scenario & break‑even** analysis; supplier quote comparison (RFQ).
- ⬜ **Rebates & chargebacks** — supplier rebates, **contract‑price vs list (WAC‑style) chargebacks**, **gross‑to‑net** tracking so true cost is known.
- ⬜ **Price‑protection clauses** — credit when a supplier's price drops after purchase.
- ⬜ **Parallel / alternative sourcing** — genuine cross‑border/alternate‑supplier buys for margin (where legal); track provenance.
- ⬜ **Generic‑substitution economics** — surface the **generic vs brand margin spread** so the counter can substitute profitably & compliantly.
- ⬜ **Delivery acceptance discipline** — check expiry on every inbound; **refuse short‑dated** stock you can't clear; log deal vs quality trade‑offs.

### Promotions & marketing
A **campaign engine** that plans, runs, and measures promotions — with rules so a
promo can't break margin, expiry, or compliance guardrails.
- ⬜ **Promotion types** — % or amount **discount**, **BOGO / buy‑X‑get‑Y**, **bundle** deals, threshold ("spend N, save M"), **free‑goods/sample**, price‑drop/clearance, **seasonal** offers.
- ⬜ **Coupons & promo codes** — single/multi‑use, digital + printed, per‑customer targeting, **stacking rules** (which promos combine), start/end dates, budget caps, redemption tracking.
- ⬜ **Loyalty programme** — points (earn per spend, redeem for discount/free product), **tiers**, member‑only offers, birthday/anniversary, wallet/card, points ledger.
- ⬜ **Trade promotions (B2B)** — retailer‑facing schemes: promotional price windows, volume/bonus deals, co‑op/display allowances, **promotion accrual** & settlement (ties to rebates/deductions).
- ⬜ **Targeting & channels** — segment by history/category; push via **SMS / email / in‑app / online storefront** (Connect pipeline); campaign calendar.
- ⬜ **Guardrails & measurement** — **min‑margin floor** & expiry/compliance checks (no promoting Rx/controlled unlawfully), **approval‑gated** above a threshold, and **uplift/ROI reporting** (redemptions, margin impact, cannibalisation).

> These are **levers the operator controls**, always inside the guardrails: every
> discount/scheme/holdback is **audited**, margin‑aware, and (where sensitive)
> **approval‑gated** — the system enables the trade game *without* enabling fraud.

---

## Defects, complaints & dispute resolution
When goods or money don't match expectations, there must be a **structured claim →
evidence → resolution** path — not phone calls and lost credits. Routes through the
[Approvals engine](#a-approvals-engine-the-reusable-authorisation-backbone) and posts
to Finance as credits/deductions.

### B2B receiving disputes & deductions (buyer ↔ depot/supplier)
- ⬜ **Raise a claim at receipt** — types: **short‑ship** (fewer than invoiced), **damaged/broken**, **wrong item**, **near/short‑dated**, **price discrepancy**, **quality/seal‑tamper**, **not ordered / over‑ship**.
- ⬜ **Evidence capture** — photos, **proof‑of‑delivery** noting condition, batch/qty, invoice line reference.
- ⬜ **Trade vs non‑trade deductions** — pre‑agreed (rebate/promo/volume) vs unanticipated (shortage/damage/return); auto‑match to the invoice line.
- ⬜ **Resolution outcomes** — **credit note**, replacement/re‑ship, partial accept, refuse & return, or reject claim (with reason); SLA‑timed via the approval engine so nothing stalls.
- ⬜ **Deduction/short‑pay management** — buyer pays invoice minus disputed amount; track the open deduction to closure; reconcile to the credit note.

### Product‑quality defects & pharmacovigilance
- ⬜ **Defect / complaint report** — contamination, packaging/labeling defect, therapeutic failure, **suspected counterfeit/falsified**, **adverse drug reaction (ADR)** — with batch/source link.
- ⬜ **Quarantine & recall link** — a confirmed defect **freezes the batch** across branches and can trigger a **recall**; disposition (return‑to‑supplier / destroy).
- ⬜ **Regulatory reporting hooks** — notify manufacturer/supplier and **Rwanda FDA** (quality defect / pharmacovigilance / falsified‑product reporting); keep the report + outcome in the document vault.

### Customer & service complaints (retail/online)
- ⬜ **Complaint log** — product, service, billing, delivery; assignment, resolution, root‑cause, response to patient; feeds quality trends.
- ⬜ **Escalation & oversight** — unresolved/overdue complaints escalate to a manager/senior (same claim‑lock/SLA/escalation rules as approvals).

### Internal & supplier disputes
- ⬜ **Supplier chargebacks/claims** — our deductions against a supplier (defective/short/price), statement reconciliation, dispute status.
- ⬜ **Inter‑branch disputes** — transfer discrepancies between branches (sent ≠ received) with variance approval.

---

## Quality Management System (QMS / GDP)
A depot that wants to pass a **GDP inspection** needs more than a defect log — it
needs a formal QMS. (Most common inspection findings: temperature‑oversight gaps,
supplier‑governance failures, ineffective CAPA, documentation‑integrity issues.)
- ⬜ **Deviation management** — log any departure from procedure/spec, classify, investigate **root cause**.
- ⬜ **CAPA** — corrective & preventive actions: plan → implement → **verify effectiveness** → close, with due dates & owners (via the approvals engine).
- ⬜ **Change control** — controlled review/approval of process/system/supplier changes.
- ⬜ **Self‑inspection / internal audit** — scheduled audits, findings, follow‑up to closure.
- ⬜ **Supplier & customer qualification** — approve/qualify trading partners (licences, GDP status), periodic re‑qualification.
- ⬜ **Equipment calibration & maintenance** — fridges/sensors/scales: calibration schedule, maintenance log, out‑of‑calibration handling.
- ⬜ **Document & SOP control** — versioned SOPs, controlled distribution, training‑to‑SOP linkage, **retention**.
- ⬜ **Risk management** — risk register + risk‑based prioritisation feeding inspections and CAPA.

## Supporting modules (smaller but required)
- ⬜ **Contract & agreement management** — supplier/customer/tenant contracts & price agreements, renewal alerts, linked to pricing & credit.
- ⬜ **Expense management** — staff expense claims & **advances/floats**, approval, reimbursement (MoMo), posting to Finance.
- ⬜ **Asset & equipment register** — fridges, shelving, IT, **vehicles** (light fleet: assignment, service/fuel log, insurance/roadworthiness expiry) — full GPS telematics stays out of scope.
- ⬜ **Accounting export / interoperability** — export to an external accountant / accounting package (Sage/QuickBooks‑style) + standard data export.
- ⬜ **Help & support** — in‑app help, guided tours, support/issue tickets, feedback.

---

## Go‑live, onboarding & configuration
Nothing works on day one without **bringing the business's existing reality in** —
a real gap that sinks ERP rollouts if ignored.
- ⬜ **Tenant onboarding wizard** — org/licence capture, branches, users/roles, departments, locations, settings.
- ⬜ **Opening balances** — **opening stock** (batches, qty, valuation) reconciled to the GL, **opening AR/AP** (open invoices with aging preserved), **opening GL / trial balance**, cash/bank, **employee & leave balances**. Summary‑balance approach first; transaction‑level optional.
- ⬜ **Data migration** — import catalog, customers/suppliers, patients, price lists from spreadsheets/legacy (CSV + mapping + validation + dry‑run).
- ⬜ **Configuration** — **document/number sequences** (invoice/PO/GRN numbering) per tenant, **fiscal calendar/periods**, tax classes, statutory‑rate seed, rounding/currency, approval thresholds, notification rules.
- ⬜ **Go‑live reconciliation & validation** — trial balance ties to legacy, AR/AP aging matches, stock valuation matches physical count; post‑go‑live checklist & hypercare.

---

## Master data & core entities (what must exist)
The first‑class records the whole platform hangs on. Missing ones are gaps to build.
- ✅ User, Organization (depot/retail/HQ + parent), Department, Location (Rwanda), Role, AuditLog.
- ✅ Product/Medicine, Manufacturer, Supplier, Ingredient, Barcode, Batch, StockMovement, PharmacyProduct.
- ✅ Order/Transfer, OrderItem, InTransitStock, OrderPayment, GRN; Sale, SaleItem, SaleBatchAllocation, Payment, Dispensing, SaleReturn.
- ⬜ **Customer / Patient** — identity, DOB, gender, contact, **allergies**, **chronic conditions**, **insurer + member no. + tier**, loyalty, **consent**. *(Walk‑in stays anonymous; registered unlocks safety checks & claims.)*
- ⬜ **Prescriber / Doctor** — name, **professional licence + council**, facility, contact.
- ⬜ **Prescription / PrescriptionFill (Refill)** — patient + prescriber + items + image/upload + verification status + fills/refills‑remaining + patient medication history.
- ⬜ **DrugInteraction / Contraindication / AllergyClass / DuplicateTherapyGroup** — the DUR knowledge base the safety review runs against.
- ⬜ **StorageZone / Bin / TemperatureLog** — warehouse structure + cold‑chain.
- ⬜ **InsuranceProvider / Policy / Claim / EOB‑EOP**.
- ⬜ **Employee (PF/staff no.) / EmploymentContract / SalaryStructure / SalaryComponent / SalaryRevision / AttendanceLog / Timesheet / Shift / ShiftRoster / RosterAssignment / LeaveType / LeaveBalance / LeaveRequest / LeaveAccrual / LoanAdvance / LoanInstallment / PayrollRun / Payslip / PayslipLine / PayrollAdjustment / StatutoryFiling / ProfessionalLicence / CPDRecord / TrainingRecord / CompetencyAssessment / DisciplinaryAction / PerformanceReview** — the full People model.
- ⬜ **PurchaseOrder / SupplierInvoice / LandedCost**.
- ⬜ **ChartOfAccounts / FiscalPeriod / PeriodClose / JournalEntry / JournalLine / JournalSource / CustomerInvoice / SupplierInvoice / InvoiceLine / Payment / PaymentAllocation / BankAccount / BankStatement / BankReconciliation / MoMoTransaction / TaxRecord (VAT / PAYE / WHT) / EBMReceipt / FixedAsset / DepreciationSchedule / Budget / CostCenter** — the full Finance model.
- ⬜ **CreditProfile** (application, scoring, limit, terms, hold), **DunningNotice**, **StatementOfAccount**, **WriteOff** — AR + credit control.
- ⬜ **ApprovalRequest / ApprovalStep / ApprovalDecision / ApprovalDelegation / ApprovalSLATimer** (approval engine — see §A; first‑class data so the inbox is queryable).
- ⬜ **OutboxEvent / EventSubscription** — domain event bus (§D). First‑class so it survives a worker restart and is auditable.
- ⬜ **StatutoryRate** (versioned, effective‑dated) — PAYE bands, RSSB pension EE/ER, maternity EE/ER, CBHI EE, occupational hazards ER, RAMA EE/ER, VAT, WHT, EBM provider — with `source_url` + `published_by` (§C).
- ⬜ **OrganizationDocument / UserDocument / EmployeeDocument** (+ Rwanda required sets).
- ⬜ **ProductListing / Offer** — `offered_qty`, listing price, buffer, visibility scope, effective dates (on‑hand ≠ offered).
- ⬜ **PriceScheme / DiscountTier / BonusScheme / Rebate / Chargeback** — the commercial‑engine levers; **CreditTerms / CreditLimit** per customer.
- ⬜ **Claim / Deduction / Dispute** — receiving disputes, short‑pays, resolutions + evidence; **Complaint**; **DefectReport / AdverseEvent** (pharmacovigilance).
- ⬜ **Promotion / Campaign / Coupon / LoyaltyAccount / PointsLedger** — the promotions & marketing engine.
- ⬜ **SalesRep / Territory / JourneyPlan / Visit / CommissionScheme** — field sales / route‑to‑market.
- ⬜ **InstitutionalCustomer / Tender / Bid / Contract** — B2G/institutional selling & agreements.
- ⬜ **ConsignmentStock** — supplier‑ or self‑owned consignment (ownership ≠ location).
- ⬜ **ClinicalService / ServiceAppointment / ServiceRecord** — billable pharmacy services.
- ⬜ **Deviation / CAPA / ChangeControl / SelfInspection / RiskItem / CalibrationRecord** — QMS/GDP.
- ⬜ **ExpenseClaim / Advance / Asset / Vehicle** — supporting modules.
- ⬜ **OpeningBalance / NumberSequence / FiscalPeriod / TenantSettings** — go‑live & configuration (costing method, pay period, statutory remittance day, FX provider).
- ⬜ **ImpersonationSession / ActivityEvent / UserSession** — admin oversight, view‑as, activity & performance monitoring (on top of the immutable audit log).

---

## Documents catalog (every document the system produces)
Each is a template in the document engine (tamper‑evident, retention‑policied, e‑signable).
- **Procurement/Inventory:** Purchase Order, Proforma, GRN, Quarantine/QC report, Stock‑count sheet & variance report, Adjustment/Write‑off voucher, Disposal/Destruction certificate, Recall notice, Temperature‑excursion report.
- **Distribution:** Sales/Transfer Order, Delivery Note, Dispatch manifest, Proof of delivery, B2B Invoice, Customer statement.
- **Retail:** Sale receipt (**EBM fiscal**), Credit note (return), Cash‑up / X‑Z report, Controlled‑drug register export, Dispensing/counselling record.
- **Insurance:** Claim form, Claim manifest per insurer, EOB (patient), EOP (provider), Prior‑authorization request.
- **Finance:** AP/AR invoices, Debit/Credit notes, Receipts, Payment vouchers, Remittance advice, Supplier/Customer statements, Trial balance, P&L, Balance sheet, Cash‑flow, EOD/EOM close, VAT/Tax return, Bank reconciliation.
- **HR:** Employment contract, Offer letter, Payslip, Leave approval, Training/competency certificate, Warning/disciplinary letter, Clearance/exit.
- **Trade & disputes:** Price‑list / scheme sheet, Quotation/offer, Rebate/credit note, Deduction/short‑pay advice, **Claim form + evidence pack** (photos/PoD), Dispute resolution record, **Defect/complaint report**, ADR/pharmacovigilance report, Recall notice.
- **Compliance/Admin:** Organisation licence pack, SOP documents, Audit export, Consent record, Approval decision (e‑signed).

### The buying ↔ selling document flow (who issues what, in order)
`Enquiry → Quotation/RFQ → Purchase Order (LPO) → Order Acknowledgement → Proforma
Invoice → Advice/Dispatch Note → Delivery Note / Waybill / Consignment Note → Goods
Receipt Note (GRN) → (Tax) Invoice → Debit Note / Credit Note → Statement of Account
→ Remittance Advice → Receipt.` Each is a template in the document engine; the same
chain runs **inbound** (we buy from suppliers) and **outbound** (we sell to retailers).

### Trade terminology glossary (the words operators use)
The system speaks the trade's language so the UI and reports feel native.
- **Order/pricing:** Enquiry · Quotation/RFQ · Purchase Order (PO/LPO) · Proforma invoice · MOQ (minimum order qty) · case pack · **list price / trade price / net price** · WAC (wholesale acquisition cost) · markup vs **margin** · landed cost · COGS.
- **Discounts/terms:** **trade discount** · **cash/settlement discount** (e.g. **2/10 net 30**) · quantity/volume discount · **bonus / free goods** · rebate · chargeback · gross‑to‑net · **net 30/45**, **EOM**, **prox./ult.** · **COD** (cash on delivery) · **CWO/CIA** (cash with order / in advance) · credit limit · **DSO/DPO** · aging.
- **Delivery/logistics:** advice note · delivery note · **waybill / consignment note** · proof of delivery (PoD) · backorder · short‑ship · **Incoterms** (EXW, FOB, CIF, DDP) · carriage paid/forward · FEFO/FIFO.
- **Billing/settlement:** (tax) invoice · **debit note** (increase what's owed) · **credit note** (reduce/refund) · statement of account · remittance advice · receipt · **E&OE** (errors & omissions excepted) · deduction/short‑pay.
- **Stock/finance:** on‑hand vs **offered** vs reserved/allocated · par/reorder point · stock turns · **GMROI** · gross/net profit & margin · ROI/ROE.

---

## Integrations catalog (external systems)
- ⬜ **RRA EBM (fiscalisation)** — `EbmProvider` abstraction; **MockEbmProvider** first → **OSDC (cloud)**; store fiscal receipt no. + SDC signature + QR; async + retry.
- ⬜ **Mobile Money** — MTN MoMo + Airtel; `PaymentProvider` abstraction; **Collections** (POS/online) + **Disbursements** (payroll/refunds); idempotency + callback verification.
- ⬜ **Card gateway** (POS/online), **SMS gateway** (OTP, alerts, patient notices), **email**.
- ⬜ **RSSB / insurance** — manual claim manifests + reconciliation first; API hook when public.
- ⬜ **IremboGov** (context), **Rwanda FDA** (licensing/controlled reports), **NCSA/DPO** (data‑protection registration).
- ⬜ **Rwanda locations** dataset (seeded), **Rwanda FDA registered‑products + ATC** seed for catalog.
- ⬜ **Drug‑knowledge data** — interactions/contraindications/allergy source (DrugBank‑style severity) for the DUR engine.
- ⬜ **GS1** — GTIN/GLN registration, 2D DataMatrix/EPCIS for serialisation & traceability (regulated/export scope).
- ⬜ **EHR/EMR / e‑prescription** hooks (future) — accept electronic prescriptions, share dispensing back.
- ⬜ Peripheral/hardware: receipt & label printers, barcode scanners, cash drawers, temperature‑log devices, customer display.

---

## Notifications & alerts catalog
- ✅ Order lifecycle, payment events, @mentions; **daily scheduler** for expiry/expired/low‑stock/overdue.
- ⬜ Licence/registration expiry, **temperature excursion**, controlled‑drug threshold, stock‑count due, near‑expiry action, reorder point hit, claim rejected, approval SLA breach/escalation, payday/statutory‑filing due, delivery due, backorder filled.
- ⬜ **Channels & rules** — in‑app + email + **SMS** + desktop; per‑user preferences, digests, quiet hours, escalation ladders.

---

## Reports & analytics catalog
Sales & margin, stock valuation & turns, expiry exposure & wastage, FEFO compliance,
AR/AP aging, insurer claims status & reconciliation, cash‑up/EOD, VAT/tax, purchasing
& supplier performance, dispensing & controlled‑drug, payroll & attendance, training/
competency compliance, licence‑expiry, **promotion uplift/ROI & loyalty**, **dispute/
deduction & defect/complaint trends**, offered‑vs‑sold & price‑change history,
multi‑branch comparison & HQ consolidation, audit trail, KPI dashboards per role —
all exportable (PDF/CSV/Excel), schedulable.

---

## Leadership & management operations (the management cockpit)
The system isn't only for cashiers and storekeepers — it must make **leaders'
daily jobs** easier: know the numbers, spot problems, decide, approve, and steer.
Each leader gets a **role cockpit** (dashboard + tasks + approvals + reports).

| Leader | What they do every day | How PharmaCore helps |
|---|---|---|
| **Owner / Director** | Is the business healthy? Am I making money? Is my capital safe? | Performance cockpit — **invested capital, gross/net profit & margin, ROI/GMROI, cash position, top approvals**; per‑branch compare |
| **Pharmacy / Branch manager** | Staffing & rosters, stock health, sales vs target, complaints, compliance | Branch dashboard — sales today, low/expiring stock, to‑approve/receive, attendance, open complaints/disputes; **claim‑&‑approve** inbox |
| **HQ executive (chain)** | Compare branches, consolidate, set policy/pricing, high‑level approvals | Multi‑branch consolidation, central catalog/price control, exception alerts, senior **oversight of all approvals** (forward/reassign) |
| **Finance manager / accountant** | AP/AR, cash, close the books, tax/EBM, performance | Ledgers + auto‑posting, **aging + DSO/DPO**, bank/MoMo reconciliation, EOM close, **P&L/BS/cash‑flow**, VAT/EBM, finance calculators |
| **HR manager** | Who's on today, leave, payroll, licences, training | Employee master, **automated attendance & overtime**, leave calendar, **gross→net payroll run**, licence/CPD expiry alerts, training/competency status |
| **Procurement / purchasing manager** | What to buy, from whom, at what price/terms | Reorder suggestions, supplier compare/RFQ, **PO → GRN → invoice** 3‑way match, landed cost, rebates/chargebacks, forward/deal‑buy tracking |
| **Warehouse / store manager** | Put‑away, cold chain, counts, quarantine, dispatch | Zones/bins, **temperature + excursion alerts**, cycle counts + variance, quarantine/recall, pick/dispatch, FEFO discipline |
| **Superintendent pharmacist (compliance)** | Legal, safe dispensing; controlled‑drug assurance | Dispensing gate + **DUR safety review**, **controlled‑drug register** + quarterly report, licence tracking, defect/ADR reporting, audit trail |

> Common thread for every leader: a **single place to see the truth** (real numbers,
> not guesses), a **claim‑to‑lock approvals inbox** (nothing stalls, no self‑approval,
> senior oversight), and **role‑scoped documents & reports** on demand.

---

## Roles & the permission matrix
Target model: **`permission = resource × action`**, roles are permission bundles,
checks are per‑permission (least privilege). Indicative roles → scope:

| Role | Can (summary) |
|---|---|
| **Cashier** | POS sell/return, own drawer; no pricing, no admin |
| **Pharmacist** | + dispense Rx/controlled, safety review, verify online Rx, counsel, catalog view |
| **Pharmacy technician** | + stock counts, intake support (depot), receive |
| **Warehouse / Storekeeper** | put‑away, picking, transfers, quarantine, counts |
| **Procurement officer** | supplier POs, imports, supplier invoices |
| **Finance officer** | AP/AR, payments, reconciliation, reports; no dispensing |
| **HR officer** | employees, payroll, leave, training; no stock/finance |
| **Branch manager** | approvals for their branch, branch dashboards |
| **HQ executive** | all branches (read + high‑level approvals), consolidation |
| **System / Org admin** | **everything, everywhere** — tenant config, users/roles, **view‑as any user**, monitor all activity/performance/logs across every branch |

Feeds the **approvals engine** (who may approve what) and the **no‑self‑approval /
supervisor‑of / senior‑oversight** rules.

---

## Platform & non‑functional (must hold across every subsystem)
- **Multi‑tenancy** — shared‑schema + **`tenant_id` on every row**; ✅ app‑layer scoping (`organizations_visible_to`); ⬜ **PostgreSQL RLS** safety net; silo DB option for very large chains.
- **Offline‑first (POS)** — ⬜ local encrypted SQLite + **outbox + idempotency‑key** sync, **LWW** conflict resolution, server re‑runs FEFO on sync; append‑only money/stock = replay‑safe.
- **Security** — deny‑by‑default RBAC, tenant + branch scoping, **append‑only audit & stock ledger**, rate limiting, encryption (transit/at‑rest/field/device), MFA, secrets management; **admin oversight & view‑as impersonation are themselves audited** (super‑admin power is logged, never invisible).
- **Compliance** — **GDP** (immutability/traceability/cold‑chain), **RRA** (EBM/VAT), **Rwanda FDA** (licences, controlled reports), **Data Protection Law 058/2021** (consent, **data residency in Rwanda** or NCSA offshore cert, data‑subject rights).
- **Localisation** — **UI English**; **patient‑facing** (receipts, SMS, online) in **Kinyarwanda + French**; whole‑RWF rounding customer‑facing, 2‑dp internal cost.
- **Retention & e‑signatures** — per‑document retention (fiscal/GDP ≥ 5–10 yrs); approvals e‑signed; legally‑binding external signatures via document engine.
- **Interaction model** — subsystems are separate **pages**, but each job **completes on one page** (search → pick → act in place via command palette, master–detail, and inline reveals); no multi‑page wizards for a single transaction. Modeled on mature ERP/workspace UIs. See [design/05 single‑page workflow](docs/design/05-single-page-workflow.md).
- **Ways of working** — **parallel backend + frontend**, ✅ only when both ship & are role‑verified ([Definition of Done](docs/development/definition-of-done.md)).
- **Reliability & ops** — backups + **restore drill**, observability/logging/metrics, error tracking, health checks, migrations discipline, CI/CD gates, a11y (≥ 4.5:1, keyboard, reduced‑motion), performance budgets, load/e2e tests.
- **Assets & prerequisites (procure, not code)** — brand SVGs per subsystem, EBM/MoMo/SMS/card/RSSB onboarding (build against **mocks** meanwhile), pilot partner (one depot + one chain), catalog seed data.

---

## What's already built (delivered to `staging`)
Legend: ✅ done · 🚧 in progress · ⬜ planned. **Under the parallel rule, ✅ means the
API *and* its page are both live and role‑verified;** where a backend exists but its
UI (or role‑scoping) is still catching up, it's honestly marked 🚧.

### Foundations ✅
- **Admin/IAM** — JWT/argon2, custom `User`, roles/RBAC (deny‑by‑default), org (depot/retail/HQ) + department + **Rwanda location** hierarchy, licences, append‑only **audit log**. *(Companies↔branches remains a single `Organization` with a parent link — a deliberate call; a true split is optional.)*
- **Admin oversight** ✅ — **PF/staff‑number login**, **view‑as / impersonation** (banner + audited, scope‑guarded), **user management** (create/manage, roles, PF, org; suspend/activate), **audit‑log explorer** + **per‑user activity**.
- **Catalog** ✅ — medicine master (FDA reg, ATC, GTIN, route, units/pack, controlled schedule, cold‑chain temps, image/leaflet), manufacturers, suppliers, ingredients, barcodes, **bulk CSV import**, margin visibility.

### Inventory 🚧
- ✅ Batch stock, immutable `stock_movements` ledger, **FEFO**, supplier intake (depot‑only), adjustments, wastage, **batch source** (recall traceability), expiry/low‑stock on dashboard, **movement‑history** screen.
- ⬜ Storage **zones & bins**, **temperature + excursion**, **quarantine/recall**, physical **counts**, reorder management, disposal.

### Distribution ✅ (core)
- ✅ Lean transfer flow (place → **approve = ship** → **receive = land**), FEFO allocation, **in‑transit ledger** (no ghost stock), receipt auto‑lands into on‑hand (no re‑keying), **branch↔branch** transfers, wholesale price auto‑pulled, **B2B settlement**, documents (PO/DN/GRN/invoice), GRN records. ⬜ **Offered‑quantity listing model** (depot chooses what/how much to publish — replaces auto‑publish), B2B **online ordering portal**, credit control, dispatch/PoD.

### Retail POS 🚧
- ✅ Sale core (search → FEFO → pay → change → **receipt**), split‑tender API, **void**, **partial returns + credit note**, **expired‑stock block**, **Rx/controlled dispensing gate** (pharmacist + patient/prescriber capture) with a **dispensing log**.
- ⬜ Cash‑drawer sessions, **offline‑first**, **Tauri desktop** + encrypted SQLite, peripherals, OTC increment pricing, interaction safety review, controlled register, calculators.

### Finance 🚧 (started)
- ✅ B2B settlement, **aged receivables & payables** (per‑partner, bucketed).
- ⬜ Chart of accounts, journals + auto‑posting, EOD/EOM close, banking/MoMo, **EBM**, tax, HQ consolidation, finance documents.

### Connect 🚧
- ✅ Contextual comments + @mentions, **operational notifications** + **daily alert scheduler**, notification centre.
- ⬜ Messaging, announcements, tasks, shift notes, notification pipeline + channels, knowledge base.

### Insights 🚧
- ✅ Operational **dashboard**, **role‑scoped navigation**.
- ⬜ Report builder, KPI charts, **multi‑branch consolidation**, per‑role dashboards.

**Tally so far:** Foundations + Catalog + Distribution core + **Admin oversight**
shipped; Retail, Finance, Connect, Inventory each partially built. ~50+ PRs merged;
116 backend tests green.

---

## Delivery phases (module‑oriented, foundation‑first)
Each phase makes one or more subsystems materially more complete, end‑to‑end
(backend + UI + design + tests + docs).

> **▶ Current position: finishing Phase 3.** We build **straight through, in order**
> (Phase 3 → 11), no cherry‑picking; each phase ships as vertical slices (API + page +
> tests, role‑verified). Phases 0–2 are done; Admin oversight (a foundations
> capability) also shipped ahead of sequence. *Dependency note:* Phase 3's **remaining**
> items (cash‑drawer, OTC increments, calculators, offline/Tauri) don't need later
> phases; the **DUR safety review** on the dispensing gate is intentionally deferred to
> Phase 6 (Patient/Prescriber + drug‑interaction data), then wired back in.

- **Phase 0 — Foundations** ✅ — Admin/IAM, audit, CI, scaffolds.
- **Phase 1 — Core data + design system** ✅ — Catalog, Inventory core, org/branch model.
- **Phase 2 — Distribution & Documents** ✅ — the B2B cycle + document engine.
- **Phase 3 — Retail counter** 🚧 (~70%) — POS sale, dispensing gate, returns done; **remaining: cash‑drawer, offline‑first sync, Tauri desktop, OTC increment pricing, peripherals, POS calculators.**
- **Phase 4 — Warehouse depth & QMS** ⬜ — storage **zones/bins**, **temperature + excursion**, **quarantine/recall**, stock counts, reorder, disposal, **consignment/VMI**; the **Quality Management System** (deviations, CAPA, change control, self‑inspection, supplier qualification, equipment calibration) for GDP. *(Inventory → true WMS.)*
- **Phase 5 — Procurement, imports, commercial engine & field sales** ⬜ — supplier POs, **import + landed‑cost**, goods receipt, supplier invoices (AP), 3‑way match; **buying tactics** (forward/deal buying, tenders, volume/framework contracts, rebates/chargebacks, gross‑to‑net); the **selling‑side trade engine** (offered‑quantity listing, price schemes/tiers, bonus/free‑goods, MOQ, payment terms), **field sales / route‑to‑market** (reps, van/pre‑sales, territories, commissions), **institutional/B2G + tenders**, and **receiving disputes/deductions + defect/complaint handling**. *(Closes the buy side and makes the depot's commercial game real.)*
- **Phase 6 — Approvals engine + safety data + master data** ⬜ — the **central approvals inbox** (claim‑lock/SLA/escalation/senior oversight), **Customer/Patient + Prescriber + Prescription** entities, **drug interactions/contraindications/allergy** data, **permission matrix**. *(Unblocks safe dispensing, insurance, and every sensitive action.)*
- **Phase 7 — Insurance, EBM & the notification pipeline** ⬜ — eligibility + co‑pay split at POS, claims + adjudication + reconciliation, **RRA EBM** fiscal receipts, rules‑based notifications + channels (incl. SMS).
- **Phase 8 — Finance, credit & performance** ⬜ — sub‑phases, built in this order (see §9.1/9.2):
  1. **Foundations** — CoA, FiscalPeriod, JournalEntry/Line, NumberSequence, **Domain Event Bus (OutboxEvent)**, StatutoryRates seed (Rwanda 2025/26), basic Reporting shell, period‑close primitives.
  2. **Auto‑posting core** — `JournalPostingService` + per‑source `PostingHandler` (SALE/PURCHASE/INVENTORY_ADJ/PAYROLL/MANUAL/DEPRECIATION/STATUTORY_PAYMENT); idempotency; reversal entries.
  3. **AR + credit** — CustomerInvoice, Receipt, allocation, **CreditProfile** (application → scoring → limit/terms → hold), aging + DSO, statements, **dunning ladder**, write‑off (approval‑gated).
  4. **AP + payments** — SupplierInvoice, **3‑way match** (PO ↔ GRN ↔ Invoice), Payment runs, **MoMo disbursement** (mock first, real later), supplier statements, DPO.
  5. **Banking** — BankAccount, statement import, **BankReconciliation**, payment matching; petty cash.
  6. **Statutory schedules** — PAYE/RSSB/VAT/WHT schedules auto‑generated from journals; **Statutory Due** dashboard; payment of statutory bodies with file output (RRA/RSSB upload‑ready CSV/JSON).
  7. **Inventory ↔ GL** — lot‑level costing (WAC or FEFO‑lot), COGS posting on SaleFinalised, revaluation, shrinkage/write‑off to GL.
  8. **Period close + reports** — EOD/EOM, trial balance, **P&L / Balance Sheet / Cash Flow**, **HQ consolidation** (eliminations), Insights report builder + multi‑branch dashboards, role cockpits.
  9. **Investment / equity + assets** — capital, drawings, retained earnings, FixedAsset register + depreciation schedule (straight‑line / reducing‑balance), performance cockpit (gross/net profit, **ROI / ROE / GMROI / DSO / DPO**).
  10. **Finance documents** — invoices/credit notes/receipts/statements/remittance/vouchers/EOD‑EOM/PIT summary via the documents engine (tamper‑evident, retention‑policied).
- **Phase 9 — People, payroll, training & SOP** ⬜ — sub‑phases, built in this order (see §10.1/10.2):
  1. **Foundations** — Employee master (PF/staff no. as cross‑system key), EmploymentContract, SalaryStructure + Components + Revisions, EmployeeDocument, **StatutoryRates seed for HR** (already in Phase 8.1 — verify linkage), PF‑number login (already in Admin), professional licence tracking.
  2. **Recruitment → onboarding** — requisitions, applicants, offer → contract, induction checklist, asset/equipment issue.
  3. **Attendance** — AttendanceLog (biometric/PIN/PF/Mobile), Timesheet auto‑build, overtime/lateness/absence, manager approval.
  4. **Shifts & rostering** — Shift patterns, Roster publish, **credential‑based scheduling** (no pharmacist on duty → block), shift swaps, coverage rules across branches.
  5. **Leave** — types/balances/accrual, requests→approval, calendar, carry‑over, encashment feeds into PayrollRun.
  6. **Payroll engine** — pure‑function `Payslip = f(employee_inputs × StatutoryRate(period_end))`; supports monthly/fortnightly/weekly/daily per Labour Code Art. 70; payslip PDF.
  7. **Payroll run lifecycle** — Draft → Calculated → Approved (no self‑approval) → Paid (bank/MoMo file with idempotency key) → Locked (immutable); payroll register, proration for joiners/leavers, arrears/back‑pay via `PayrollAdjustment`, 13th‑cheque.
  8. **Statutory filings** — PAYE monthly + RSSB unified (pension + maternity + CBHI + occ‑hazards + RAMA) + year‑end PIT schedule; auto‑generation, due dates, **filing tracker**, payments from Finance.
  9. **Loans & advances** — loan application, amortization schedule, per‑month installment into payroll deductions, balance reporting.
  10. **Performance + disciplinary + offboarding** — reviews, goals, warnings, salary revisions (history), termination with final settlement (leave encash + pro‑rata + dues), certificate of service, de‑provision login.
  11. **Training & SOP** — SOP library, assign & acknowledge, TrainingRecord, **CompetencyAssessment** + periodic re‑checks, **controlled‑drug competency**, **CPD/CE hour logging + renewal alerts** for NPC/Rwanda FDA licences.
  12. **HR documents & self‑service** — contract, offer, payslip, leave approval, warning, training/competency certificate, clearance, certificate of service via the documents engine; employee self‑service portal (payslips, leave requests, attendance, profile); org chart; HR reports (headcount, turnover, attendance, leave liability, payroll cost).
  13. **HR ↔ Finance integration tests** — every People event (`PayrollRunApproved`, `StatutoryFilingGenerated`, `StatutoryPaymentConfirmed`, `EmployeeHired`, `EmployeeTerminated`) end‑to‑end through the outbox bus into Finance journals, with reconciliation checks.
- **Phase 10 — Online, services & Connect (full)** ⬜ — patient **e‑commerce** + prescription upload + delivery/click‑&‑collect; **clinical/pharmacy services** (vaccination/testing/consults) + **appointment scheduling**; full **messaging, announcements, tasks, shift notes, knowledge base**, workspace tools (todo/calendar/calculators/templates).
- **Phase 11 — Onboarding, hardening, certification & launch** ⬜ — **go‑live tooling** (tenant onboarding wizard, **opening balances**, data migration, number sequences/fiscal periods, reconciliation & hypercare); real EBM adapter + **RRA CIS certification**, real insurer/MoMo/SMS adapters, **Postgres RLS**, observability, backups + restore drill, a11y audit, load/e2e, data‑protection registration, **pilot** at one depot + one chain.

> Sequencing rationale: finish the **counter** (3) — a pharmacy that can't sell isn't
> usable; make the **warehouse** and **buy side** real (4–5) so depots run end‑to‑end;
> stand up the **approvals engine + safety/master data** (6) that everything sensitive
> depends on; then **money‑ and compliance‑critical** Insurance/EBM/Finance (7–8);
> then **people/training** and **online/collaboration** (9–10); then **certify and
> launch** (11).

---

## Cross‑cutting workstreams (every phase, part of "done")
- **Design system & brand** — subsystem logo family + app‑switcher; no hardcoded colours/spacing; light/dark; a11y. *(Note: a full visual redesign is planned — treat current design docs as provisional.)*
- **Security & compliance** — deny‑by‑default RBAC, tenant + branch scoping, append‑only audit & stock ledger, rate limiting, encryption, **GDP / RRA / FDA / Data‑Protection**.
- **Testing** — unit → integration → e2e; compliance tests (immutability/audit); coverage gate.
- **Docs** — keep architecture, data model, API, and this roadmap current.

## Explicitly out of scope (v1)
Manufacturing/production (GMP shop‑floor), courier GPS hardware, external chat
federation, full accounting‑suite depth beyond pharmacy needs, and AI clinical
decision support beyond interaction/duplication/allergy checks.

---

### Research sources (pharmacy & ERP operations)
- Good Distribution Practice (GDP) — [Pharmaguideline](https://www.pharmaguideline.com/2022/08/good-distribution-practices.html), [PharmaSource GDP guide](https://pharmasource.global/content/guides/category-guide/good-distribution-practice-gdp-a-comprehensive-guide/)
- Pharmaceutical warehousing & cold chain / FEFO — [Inbound Logistics](https://www.inboundlogistics.com/articles/pharmaceutical-warehousing/), [ASC Software FEFO guide](https://ascsoftware.com/blog/fefo-inventory-management-guide/), [Olimp cold chain](https://olimpwarehousing.com/pharmaceutical-cold-chain-logistics/)
- Pharmacy ERP modules (NetSuite/SAP) — [IntuitionLabs NetSuite in pharma](https://intuitionlabs.ai/articles/netsuite-usage-in-pharma-industry), [ERP Research – SAP for pharma](https://www.erpresearch.com/en-us/sap-for-pharmaceuticals)
- Multi‑branch / chain operations — [LogicERP multi‑store guide](https://www.logicerp.com/blog/how-to-manage-multi-store-pharmacy-chains-with-pharma-retail-erp-software-a-complete-guide/), [Auto‑Star multi‑store POS](https://www.auto-star.com/2025/09/12/how-a-pharmacy-pos-system-can-support-multi-store-operations/)
- Retail dispensing workflow & staff roles — [PBA Health workflow](https://www.pbahealth.com/elements/improve-pharmacy-workflow/), [CCI pharmacy technician day](https://ccitraining.edu/blog/a-day-in-the-life-of-a-pharmacy-technician-all-you-need-to-know/)
- Training, SOPs & controlled‑drug register — [Example SOPs](https://examplesops.com/sops-for-a-pharmacy/), [Pharmaguideline training SOP](https://www.pharmaguideline.com/2014/09/sop-for-training-of-employees.html), [NHS Grampian CD guidance](https://www.nhsgrampian.org/globalassets/services/medicines-management/policies/guide_cd_check.pdf)
- Wholesale distribution features / traceability / SOM / saleable returns — [LOGIC ERP pharma distribution](https://www.logicerp.com/blog/top-10-features-of-logic-erp-pharma-distribution-software/), [Ximple pharma wholesale ERP (DSCSA/EPCIS)](https://www.ximplesolution.com/industries/pharma-wholesale-software-erp/), [BlueLink traceability](https://www.bluelinkerp.com/medical-pharmaceutical-traceability-software/)
- Pharmacy WMS / GS1 DataMatrix / serialisation / cold chain — [ASC Software WMS](https://ascsoftware.com/blog/critical-elements-of-a-successful-pharmaceutical-warehouse-management-system-6/), [Datex life‑science WMS](https://datexcorp.com/wms-solutions/industry-solutions/life-science-pharmaceutical-warehouse-management-system), [Balloon One pharma WMS](https://balloonone.com/resources/wms-for-the-pharmaceutical-industry-2/)
- Pharmacy POS / PMS / dispensing / refills — [Tech.co pharmacy POS](https://tech.co/pos-system/best-pharmacy-pos-system), [Langate inventory features](https://langate.com/news-and-blog/10-main-features-of-a-pharmacy-inventory-management-system/), [CISePOS pharmacy POS](https://cisepos.com/pharmacy-pos-systems-manage-prescriptions-inventory-easily/)
- Insurance adjudication / NCPDP / DUR / COB / remittance — [Smart Data Solutions – adjudication basics](https://sdata.us/2022/11/08/the-basics-of-pharmacy-claims-adjudication/), [NCPDP standards](https://www.ncpdp.org/), [eMedNY ProDUR/ECCA manual](https://www.emedny.org/ProviderManuals/Pharmacy/ProDUR-ECCA_Standards_Manual/1_33/ProDUR-ECCA%20Standards.pdf)
- Pharmacy HR / credential‑based scheduling / CE tracking — [Shifton pharmacy scheduling](https://shifton.com/industries/pharmacy-shift-scheduling/), [Everhour pharmacy scheduling](https://everhour.com/blog/pharmacy-scheduling-software/), [NABP CPE Monitor](https://nabp.pharmacy/programs/cpe-monitor/)
- Online pharmacy e‑commerce / refills / teleconsult / delivery — [Digital Pharmacy – ecommerce features](https://digitalpharmacy.io/features-in-your-pharmacy-ecommerce-platform/), [CoverMyMeds digital pharmacy/telemedicine](https://www.covermymeds.health/who-we-serve/pharmacy/digital-pharmacy-and-telemedicine)
- Finance / ERP finance module / inventory valuation — [SoftwareConnect ERP finance modules](https://softwareconnect.com/learn/erp-finance-modules/), [NetSuite ERP finance module](https://www.netsuite.com/portal/resource/articles/erp/erp-finance-module.shtml), [Juleb pharmacy GL](https://juleb.com/blog/pharma-general-ledger-solutions/en)
- Offered vs on‑hand / reserved / buffer stock — [Stockpilot – available vs offered stock](https://stockpilot.com/blog/inventory-management-depth-available-offered-stock), [ERPAG – on‑hand/reserved/committed](https://learn.erpag.com/project/create-new-product-1/untitled-4/on-hand-reserved-committed-and-awaiting-quantity), [Xoro – inventory reservation](https://xorosoft.com/inventory-reservation-prevent-overselling/)
- Trade tactics — discounts / MOQ / free goods / payment terms — [Ordercircle – wholesale sales strategies](https://ordercircle.com/blog/7-strategies-to-increase-b2b-wholesale-sales/), [b2bridge – volume discounts](https://b2bridge.io/blog/b2b-volume-discounts/), [BuyersIntelligence – 2/10 net 30](https://blog.buyersintelligence.ai/early-payment-discounts-b2b-2-10-net-30/), [QuickBooks – MOQ](https://quickbooks.intuit.com/r/wholesale-trade/how-minimum-order-quantity-terms-can-earn-you-big-bucks/)
- Short‑dated / slow‑mover / bundling / rebates‑chargebacks / gross‑to‑net — [StockMeds – short‑dated meds](https://stockmeds.com/short-dated-medications-risk-or-opportunity-for-pharmacies/), [Happy Cabbage – slow‑moving SKUs](https://www.happycabbage.io/post/tactics-to-reduce-slow-moving-skus-at-your-dispensary), [EisnerAmper – gross‑to‑net/WAC](https://www.eisneramper.com/insights/technology/pricing-adjustment-gross-to-net-cat-0318/), [IMA360 – distributor chargebacks](https://ima360.com/reference/chargebacks/what-is-a-distributor-chargeback/)
- Procurement / tendering / volume contracts / parallel import / generic margins — [Procurement Tactics – pharma procurement](https://procurementtactics.com/pharmaceutical-procurement/), [WHO – tendering & negotiation](https://www.ncbi.nlm.nih.gov/books/NBK570136/bin/webannexb-et6.pdf), [ScienceDirect – generic substitution margins](https://www.sciencedirect.com/science/article/abs/pii/S0014292113000299)
- Disputes / deductions / defect & complaint handling — [Go Autonomous – B2B claims & disputes](https://goautonomous.io/blogs/b2b-claims-and-dispute-processing-how-autonomous-commerce-resolves-returns-and-credits-without-escalation/), [Tekst – deduction management](https://www.tekst.com/blogs/deduction-management), [Inymbus – retail deductions guide](https://blog.inymbus.com/common-deductions-from-major-retailers-suppliers-guide)
- Promotions / loyalty / coupons / seasonal & trade promotion — [Antavo – pharmacy loyalty](https://antavo.com/blog/pharmacy-loyalty-programs/), [Xoxoday – pharmacy loyalty guide](https://blog.xoxoday.com/loyalife/pharmacy-loyalty-program/), [DiversifyRx – seasonal promotions](https://diversifyrx.com/pharmacy-profit-seasonal-promotions-for-the-win/), [BlueCart – wholesale discounts & marketing](https://www.bluecart.com/blog/wholesale-discounts-marketing)
- Pharmacy leadership / manager duties & KPIs — [APOS – pharmacy manager role](https://careers.apos-society.org/career/pharmacy-manager), [Council on Pharmacy Standards – KPIs](https://pharmacystandards.org/cpom/section-5-1-key-performance-indicators-kpis-for-pharmacy-operations/), [DosePacker – pharmacy KPIs](https://dosepacker.com/blog/pharmacy-kpis)
- HR / payroll gross→net / deductions / attendance — [Asanify – gross‑to‑net](https://asanify.com/glossary/gross-to-net-calculation/), [AIHR – statutory deductions](https://www.aihr.com/hr-glossary/statutory-deductions/), [Keka – payroll in HR](https://academy.keka.com/blog/what-is-payroll-in-hr/), [Softhealer – attendance & leave](https://softhealer.com/blog/articals-11/attendance-leave-management-a-key-hrms-function-12711)
- Finance performance / profit / ROI / GMROI — [RxConnexion – pharmacy KPIs](https://www.rxconnexion.com/post/top-kpis-for-a-successful-pharmacy-business-what-to-track-for-growth-and-profitability), [Fleming Advisors – profitability & margins](https://www.fleming-advisors.com/post/the-pharmacy-profitability-playbook-understanding-key-metrics-and-margins), [Alchemy – ROI vs ROE](https://www.alchemyhealth.com/articles/a-comprehensive-guide-how-to-measure-the-roi-for-your-on-site-pharmacy-understanding-the-difference-between-roe-and-roi)
- Customer credit / AR / DSO / collections — [OpenStax – receivables management](https://openstax.org/books/principles-of-finance-2e/pages/19-4-receivables-management), [Intrum – AR management](https://www.intrum.com/insights/guides-and-articles/what-is-accounts-receivable-management-and-why-does-it-matter/), [Harding Group – DSO/terms/credit policy](https://www.thehardinggroup.biz/blog/speeding-up-collections-dso-terms-and-credit-policies/)
- Buying/selling documents & trade terminology — [Artsyl – proforma vs PO](https://www.artsyltech.com/proforma-invoice-vs-purchase-order), [Cleverence – purchase terminology](https://www.cleverence.com/articles/for-business/purchase-terminology-7049/), [Wikipedia – debit note](https://en.wikipedia.org/wiki/Debit_note), [Billdu – document types](https://faq.billdu.com/en/articles/3001362-document-types-and-differences)
- Field sales / sales‑force management (reps, territories) — [CloudApper – manage pharma sales force](https://www.cloudapper.ai/sales-force-management/manage-pharmaceutical-sales-force/), [PharmExec – sales‑force effectiveness](https://www.pharmexec.com/view/reinventing-pharma-sales-force-effectiveness)
- QMS / GDP / deviations / CAPA / change control — [Scilife – QMS in pharma](https://www.scilife.io/blog/qms-in-pharma-guide), [IntuitionLabs – deviations/CAPA/change control](https://intuitionlabs.ai/articles/deviations-capa-change-control), [Zamann – GDP audit & compliance 2026](https://zamann-pharma.com/2026/03/26/good-distribution-practice-gdp-audit-and-compliance-in-year/)
- Clinical/pharmacy services & appointment scheduling — [EnlivenHealth – pharmacy scheduling](https://enlivenhealth.co/clinical-experience/pharmacy-scheduling-software), [NCPA – vaccination toolkit](https://ncpa.org/no-excuses-vaccination-toolkit)
- Consignment / VMI & institutional tenders — [Identi – consignment inventory FAQ](https://identimedical.com/faqs/how-to-manage-consignment-inventory/), [Solistica – consignment to hospitals](https://blog.solistica.com/en/the-supply-chain-and-the-consignment-of-goods-to-hospitals)
- ERP go‑live / data migration / opening balances — [Wiss – ERP implementation roadmap](https://wiss.com/erp-implementation-roadmap-from-selection-to-go-live/), [CAI – ERP go‑live checklist](https://caisoft.com/resources/erp-go-live-checklist/), [Openetech – financial data migration](https://erp.openetech.com/blog/erp/financial-data-migration-in-erp)
- Rwanda specifics (EBM, MoMo, statutory, insurance, data protection) — see [docs 13, 17, 18](docs/README.md) for the full cited source lists.
</content>
</invoke>
