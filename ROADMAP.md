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
> control. Status legend: ✅ done · 🚧 in progress · ⬜ planned. If something a
> pharmacy does isn't here, it's a gap to add — not an omission by design. The
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
| 10 | **Finance** | AP (suppliers) / AR (buyers, insurers), ledgers, **aging**, EOD closeout, banking/MoMo, tax, **consolidated HQ** books | Cash leakage, blind margins, unpaid debts |
| 11 | **People & training** | Recruit → onboard → licences & dispensing rights → attendance/shifts/leave → **payroll (PAYE/RSSB)** → **SOP + competency** → performance → offboard | Unlicensed dispensing, untrained staff |
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
- ✅ Organisation model (depot / retail / HQ) + parent link (HQ→branch), departments, **Rwanda location** hierarchy (province→district→sector→cell→village).
- ✅ Roles + deny‑by‑default RBAC; append‑only **audit log**.
- ⬜ **Formal company ↔ branch split** (a first‑class `Company` above `Organization`) for large chains that demand it.
- ⬜ **Permission matrix** — `permission = resource × action`; roles as permission bundles; per‑permission checks (see [Roles & permissions](#roles--the-permission-matrix)).
- ⬜ **User provisioning discipline** — users are **created only by HR / Admin / Org‑admin**, never self‑signup; mandatory identity documents on creation (see [User & pharmacy creation](docs/12-requirements-fields-documents-approvals.md)).
- ⬜ **Pharmacy/organisation onboarding** — licence & document capture (Rwanda FDA, NPC, RDB, RRA), verification, activation gate.
- ⬜ Org settings, feature flags per tenant, subscription/plan, branding per tenant.
- ⬜ Password policy, MFA, session controls, API keys/service accounts, SSO (future).
- ⬜ Delegation & "act‑on‑behalf", account suspension/reactivation, leaver de‑provisioning.

### 2. Catalog (product master)
- ✅ Medicine master — FDA reg no., **ATC/INN**, GTIN/barcode, brand & generic name, form, strength, route, pack size & units, controlled schedule, cold‑chain temps, image/leaflet.
- ✅ Manufacturers, suppliers, ingredients/actives, barcodes; **bulk CSV import**; margin visibility.
- ⬜ **Drug‑safety data** — drug‑drug **interactions** (DrugBank severity), **contraindications**, allergy/cross‑allergy classes, pregnancy/lactation category, max dose, duplicate‑therapy groups (feeds the dispensing safety review).
- ⬜ **Formulary & coverage** — insurer formularies, reimbursable flags, therapeutic categories.
- ⬜ **Price lists** — wholesale price list (depot→retail), retail price list, promotional/tiered pricing, price history, effective‑dated pricing, per‑customer/contract pricing.
- ⬜ **Units of measure** — pack ↔ each conversions, OTC **increment pricing** (sell by strip/tablet), UoM rounding.
- ⬜ Alternatives/substitutes (generic equivalents), kit/bundle products, non‑drug/consumables/OTC goods.
- ⬜ Label/shelf‑talker printing, catalog approval workflow, discontinue/obsolete lifecycle.

### 3. Inventory & Warehouse
- ✅ Batch stock, immutable `stock_movements` ledger, **FEFO**, supplier intake (depot‑only), adjustments, wastage, **batch source** (recall traceability), expiry/low‑stock on dashboard, movement‑history screen.
- ⬜ **Storage zones** (ambient / 2–8 °C / −20 °C / controlled/CD safe) + **bins/aisles/locations**; put‑away by storage condition.
- ⬜ **Cold‑chain / temperature monitoring** — device logs, excursion detection + alerts, mean‑kinetic‑temperature, quarantine on excursion.
- ⬜ **Quarantine & QC** — inbound hold, QC pass/fail, release/reject, blocked‑stock states.
- ⬜ **Recalls** — batch recall by source, locate‑and‑freeze across branches, recall notice, disposition.
- ⬜ **Stock counts** — cycle counts, full physical inventory, blind counts, variance approval, count freeze.
- ⬜ **Reorder management** — min/max/reorder points, par levels, suggested orders, ABC/XYZ analysis, slow/dead‑stock, near‑expiry action lists.
- ⬜ **Disposal/destruction** — expired/damaged write‑off with witness sign‑off & certificate (esp. controlled).
- ⬜ **GS1 2D DataMatrix** scan & parse (GTIN + **batch + expiry + serial** in one code) at receipt/dispatch; per‑unit **serialisation & track‑&‑trace** (EPCIS‑ready export for regulated/export markets), aggregation (case→pallet).
- ⬜ **Cold‑chain rigour** — mean‑kinetic‑temperature, calibrated‑sensor register, excursion investigation & disposition record.
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
- ✅ B2B settlement, **aged receivables & payables** (per‑partner, bucketed).
- ⬜ **Chart of accounts**, double‑entry **journals** + auto‑posting from sales/purchases/stock/payroll, sub‑ledgers.
- ⬜ **AP** (supplier bills, payment runs, MoMo disbursements) / **AR** (customer & insurer invoices, receipts, dunning).
- ⬜ **Banking & cash** — bank/MoMo/Airtel accounts, reconciliation, petty cash, cash‑book.
- ⬜ **Tax** — VAT (class B = 18%), **EBM fiscalisation** (OSDC), withholding, tax reports/returns.
- ⬜ **Period close** — EOD/EOM closeout, trial balance, P&L, balance sheet, cash‑flow; **HQ consolidation** across branches.
- ⬜ **Inventory valuation & costing** — costing method (weighted‑average / FEFO‑lot cost), **lot‑level valuation**, stock valuation & COGS posting, revaluation, shrinkage/write‑off to GL.
- ⬜ **Budgets & costing** — budgets vs actual, cost centres, margin & profitability analysis.
- ⬜ **Finance documents** — invoices, credit/debit notes, receipts, statements, remittance, vouchers, EOD/EOM reports (see [Documents catalog](#documents-catalog)).
- ⬜ Multi‑currency (imports), fixed assets/depreciation (light).

### 10. People (HR & payroll)
- ⬜ **Recruitment** — requisition, job posting, applicants, interviews, offer.
- ⬜ **Onboarding** — employee master, contract, documents (ID, licences, certificates), asset/equipment issue, checklist.
- ⬜ **Licences & dispensing rights** — pharmacist/tech licences (NPC/board) + expiry tracking gating dispensing; **CPD/CE hour logging + renewal alerts**.
- ⬜ **Time & attendance** — **credential‑based scheduling** (auto‑assign shifts only to staff with a valid licence; ensure each shift has a pharmacist on cover), shifts/rosters across branches, clock in/out, leave (types, balances, requests→approval), overtime, absence.
- ⬜ **Payroll** — PAYE bands, **RSSB pension 12%**, maternity 0.6%, **CBHI 0.5% net**, transport allowance in base, payslips, bank/MoMo pay run, statutory filings; versioned `statutory_rates`.
- ⬜ **Training & SOP** — SOP library, assign‑and‑acknowledge, training courses/records, **competency assessments** + periodic re‑checks, controlled‑drug competency.
- ⬜ **Performance** — reviews, goals, disciplinary, warnings.
- ⬜ **Offboarding** — clearance, final pay, de‑provision, exit.
- ⬜ Org chart, self‑service portal (payslips/leave), headcount reports.

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
- ⬜ **To‑do lists** (personal + assigned via Connect), **calendar** (shifts, expiries, licence renewals, deliveries, paydays), **calculators** (dose, markup/margin, VAT, change, unit‑price, payroll), **notes**, **document templates** picker, quick search/command palette.

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
- ⬜ **Employee / Contract / Licence / Attendance / LeaveRequest / Payslip / TrainingRecord / Competency**.
- ⬜ **PurchaseOrder / SupplierInvoice / LandedCost**.
- ⬜ **Account / Journal / JournalLine / TaxRecord / BankAccount / FiscalReceipt (EBM)**.
- ⬜ **ApprovalRequest / ApprovalStep / ApprovalDecision** (approval engine).
- ⬜ **OrganizationDocument / UserDocument / EmployeeDocument** (+ Rwanda required sets).
- ⬜ **StatutoryRate** (versioned, effective‑dated) — PAYE/RSSB/CBHI/VAT.
- ⬜ **ProductListing / Offer** — `offered_qty`, listing price, buffer, visibility scope, effective dates (on‑hand ≠ offered).
- ⬜ **PriceScheme / DiscountTier / BonusScheme / Rebate / Chargeback** — the commercial‑engine levers; **CreditTerms / CreditLimit** per customer.
- ⬜ **Claim / Deduction / Dispute** — receiving disputes, short‑pays, resolutions + evidence; **Complaint**; **DefectReport / AdverseEvent** (pharmacovigilance).
- ⬜ **Promotion / Campaign / Coupon / LoyaltyAccount / PointsLedger** — the promotions & marketing engine.

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
| **System / Org admin** | tenant config, users/roles, everything |

Feeds the **approvals engine** (who may approve what) and the **no‑self‑approval /
supervisor‑of / senior‑oversight** rules.

---

## Platform & non‑functional (must hold across every subsystem)
- **Multi‑tenancy** — shared‑schema + **`tenant_id` on every row**; ✅ app‑layer scoping (`organizations_visible_to`); ⬜ **PostgreSQL RLS** safety net; silo DB option for very large chains.
- **Offline‑first (POS)** — ⬜ local encrypted SQLite + **outbox + idempotency‑key** sync, **LWW** conflict resolution, server re‑runs FEFO on sync; append‑only money/stock = replay‑safe.
- **Security** — deny‑by‑default RBAC, tenant + branch scoping, **append‑only audit & stock ledger**, rate limiting, encryption (transit/at‑rest/field/device), MFA, secrets management.
- **Compliance** — **GDP** (immutability/traceability/cold‑chain), **RRA** (EBM/VAT), **Rwanda FDA** (licences, controlled reports), **Data Protection Law 058/2021** (consent, **data residency in Rwanda** or NCSA offshore cert, data‑subject rights).
- **Localisation** — **UI English**; **patient‑facing** (receipts, SMS, online) in **Kinyarwanda + French**; whole‑RWF rounding customer‑facing, 2‑dp internal cost.
- **Retention & e‑signatures** — per‑document retention (fiscal/GDP ≥ 5–10 yrs); approvals e‑signed; legally‑binding external signatures via document engine.
- **Reliability & ops** — backups + **restore drill**, observability/logging/metrics, error tracking, health checks, migrations discipline, CI/CD gates, a11y (≥ 4.5:1, keyboard, reduced‑motion), performance budgets, load/e2e tests.
- **Assets & prerequisites (procure, not code)** — brand SVGs per subsystem, EBM/MoMo/SMS/card/RSSB onboarding (build against **mocks** meanwhile), pilot partner (one depot + one chain), catalog seed data.

---

## What's already built (delivered to `staging`)
Legend: ✅ done · 🚧 in progress · ⬜ planned.

### Foundations ✅
- **Admin/IAM** — JWT/argon2, custom `User`, roles/RBAC (deny‑by‑default), org (depot/retail/HQ) + department + **Rwanda location** hierarchy, licences, append‑only **audit log**. *(Companies↔branches remains a single `Organization` with a parent link — a deliberate call; a true split is optional.)*
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

**Tally so far:** Foundations + Catalog + Distribution core shipped; Retail, Finance,
Connect, Inventory each partially built. ~50+ PRs merged; ~105 backend tests green.

---

## Delivery phases (module‑oriented, foundation‑first)
Each phase makes one or more subsystems materially more complete, end‑to‑end
(backend + UI + design + tests + docs).

- **Phase 0 — Foundations** ✅ — Admin/IAM, audit, CI, scaffolds.
- **Phase 1 — Core data + design system** ✅ — Catalog, Inventory core, org/branch model.
- **Phase 2 — Distribution & Documents** ✅ — the B2B cycle + document engine.
- **Phase 3 — Retail counter** 🚧 (~70%) — POS sale, dispensing gate, returns done; **remaining: cash‑drawer, offline‑first sync, Tauri desktop, OTC increment pricing, peripherals, POS calculators.**
- **Phase 4 — Warehouse depth** ⬜ — storage **zones/bins**, **temperature + excursion**, **quarantine/recall**, stock counts, reorder, disposal. *(Inventory → true WMS.)*
- **Phase 5 — Procurement, imports & the commercial engine** ⬜ — supplier POs, **import + landed‑cost**, goods receipt, supplier invoices (AP), 3‑way match; **buying tactics** (forward/deal buying, tenders, volume/framework contracts, rebates/chargebacks, gross‑to‑net); the **selling‑side trade engine** (offered‑quantity listing, price schemes/tiers, bonus/free‑goods, MOQ, payment terms) and **receiving disputes/deductions + defect/complaint handling**. *(Closes the buy side and makes the depot's commercial game real.)*
- **Phase 6 — Approvals engine + safety data + master data** ⬜ — the **central approvals inbox** (claim‑lock/SLA/escalation/senior oversight), **Customer/Patient + Prescriber + Prescription** entities, **drug interactions/contraindications/allergy** data, **permission matrix**. *(Unblocks safe dispensing, insurance, and every sensitive action.)*
- **Phase 7 — Insurance, EBM & the notification pipeline** ⬜ — eligibility + co‑pay split at POS, claims + adjudication + reconciliation, **RRA EBM** fiscal receipts, rules‑based notifications + channels (incl. SMS).
- **Phase 8 — Finance & consolidation** ⬜ — chart of accounts, journals + auto‑posting, AP/AR, banking/MoMo, tax, EOD/EOM close, **HQ consolidated** books, finance documents, Insights report builder & multi‑branch dashboards.
- **Phase 9 — People, training & SOP** ⬜ — recruit→onboard→licences→attendance/leave→**payroll (PAYE/RSSB/CBHI)**→**SOP + training + competency**→performance→offboard, controlled‑drug assurance.
- **Phase 10 — Online selling & Connect (full)** ⬜ — patient **e‑commerce** + prescription upload + delivery/click‑&‑collect; full **messaging, announcements, tasks, shift notes, knowledge base**, workspace tools (todo/calendar/calculators/templates).
- **Phase 11 — Hardening, certification & launch** ⬜ — real EBM adapter + **RRA CIS certification**, real insurer/MoMo/SMS adapters, **Postgres RLS**, observability, backups + restore drill, a11y audit, load/e2e, data‑protection registration, **pilot** at one depot + one chain.

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
- Rwanda specifics (EBM, MoMo, statutory, insurance, data protection) — see [docs 13, 17, 18](docs/README.md) for the full cited source lists.
</content>
</invoke>
