# Application Design Blueprint — the whole workspace, end to end

How **PharmaCore** is laid out as a **workspace of subsystems** — the shell, every
subsystem's screens, the charts each needs, the documents/templates, the built‑in
tools, and the role dashboards. Builds on the existing design system
([00 principles](00-principles.md) · [01 tokens](01-design-tokens.md) ·
[02 brand/logo family](02-brand-and-logo-system.md) · [06 components](06-components.md) ·
[09 dashboards & charts](09-dashboards-and-charts.md)).

## 0. Design north star
- **Product class:** Healthcare + Finance/ERP → **trust & authority, calm, data‑dense
  but never cluttered.** Swiss/minimal grid; generous whitespace; content first.
- **Style rules (from the design skill):** SVG icons only (Lucide), **no emojis as
  icons**, no neon, **no AI purple/pink gradients**, strong contrast, restrained palette.
- **Palette:** brand **teal `#0D9488`** + the 8 **subsystem hues** (doc 02); semantic
  green/amber/red for status; neutral ink/surface/line tokens (doc 01). Light **and**
  dark, per viewer.
- **Type:** **Inter** (UI), tabular numerals for money/quantities; mono for codes,
  batches, document numbers.
- **Motion:** 150–300 ms transitions, respect `prefers-reduced-motion`.
- **Responsive:** 375 / 768 / 1024 / 1440; counter (POS) is touch‑first with large targets.
- **A11y:** contrast ≥ 4.5:1, visible focus, keyboard‑operable, status never by colour alone.

---

## 1. The workspace shell (every screen sits in this)
```
┌───────────────────────────────────────────────────────────────────────┐
│ [◧ app‑switcher] Pharma·Core   [Branch ▾]   [⌘K search]      [🔔][✔][👤]│  top bar
├──────────┬────────────────────────────────────────────────────────────┤
│ side nav │  Page header: Title            [primary action]            │
│ (role-   │  ─────────────────────────────────────────────────────     │
│  scoped) │  Content: list / detail / dashboard / workflow / board     │
│          │                                                            │
└──────────┴────────────────────────────────────────────────────────────┘
```
- **App‑switcher ("waffle")** — top‑left grid of **subsystem tiles** (doc 02 family:
  hue + glyph). Opens a panel to jump between subsystems; the current subsystem's tile
  shows in the wordmark lockup. This is what makes the suite feel like *one* workspace.
- **Branch switcher** — HQ users pick "All branches" or one branch; a branch user is
  pinned to theirs. Scopes every screen.
- **Command palette (⌘K)** — global search + run‑a‑command (jump to a product, order,
  patient; "new sale", "new transfer").
- **Bell (🔔)** — notifications; **Approvals (✔)** — the pending‑approvals inbox badge
  ([doc 12 §4](../12-requirements-fields-documents-approvals.md)); **avatar** — profile,
  theme, sign out.
- **Side nav** — **role‑scoped** (cashier sees POS; HQ exec sees Insights/Finance),
  grouped by subsystem; collapsible to icon rail (tiles at 20 px).

## 2. Screen archetypes (reused everywhere — build once)
| Archetype | Used for | Anatomy |
|---|---|---|
| **List / table** | catalogs, orders, batches, employees | search + filters + sort, dense rows, row actions, pagination, bulk actions, empty/loading/error |
| **Detail + tabs** | pharmacy, product, order, employee | header (name/status/actions) + tabbed sections |
| **Single‑page workflow** | **POS**, dispensing, checkout | left = pick, right = cart/summary, one‑screen, keyboard‑fast (doc 05) |
| **Wizard** | registration, payroll run, onboarding | stepper, validation per step, review → submit (→ approval) |
| **Dashboard** | home, role & exec views | KPI tiles + charts + alert strips + drill‑downs (doc 09) |
| **Board (kanban)** | approvals, claims queue, tasks, recruitment | columns by status, drag/claim, WIP |
| **Calendar** | shifts, leave, deliveries, licence expiries | month/week/day, colour by type |
| **Inbox / thread** | Connect chat, approvals, comments | list + reading pane |
| **Document viewer** | invoices, receipts, GRNs | PDF + hash/QR verify + download |

## 3. Subsystems — layout & the charts each needs
Each subsystem = its **screens** + the **visualisations** that make its data legible.
(✔ = shipped.)

### 3.1 Admin (IAM) — slate `#475569`
- Screens: Companies/HQ → **branches**, Users & roles, **permission matrix**, Licences
  & documents, Settings, **Audit log** ✔.
- Charts: users‑by‑role **donut**, licence‑expiry **timeline**, audit **activity heatmap**.

### 3.2 Catalog — cyan
- Screens: Product list ✔ (image, tax, Rx), Product detail + **Clinical tab**
  (interactions/contraindications), Manufacturers, Suppliers, **CSV import** ✔, price lists.
- Charts: products **by ATC** (treemap/bar), **Rx vs OTC vs controlled** donut, price
  distribution.

### 3.3 Inventory & Warehouse — cyan
- Screens: Stock on hand ✔ (FEFO), **Movements ledger** ✔, **Storage zones & bins**,
  **Temperature monitoring** (per zone), **Quarantine/Recall**, Stock‑count sessions,
  Intake (depot) ✔.
- Charts: **stock value** trend (area), **expiry runway** (bar by 30/60/90 days),
  **temperature log** (line with excursion band, 2–8 °C), **turnover** by product,
  low‑stock **bar**, ABC/Pareto.

### 3.4 Procurement — indigo
- Screens: Supplier POs, **Imports** (bill of lading/customs/**landed cost**), Goods
  receipt, Supplier invoices (AP).
- Charts: spend **by supplier** (bar), **landed‑cost** breakdown (stacked: price/
  freight/duty), lead‑time distribution, PO status funnel.

### 3.5 Distribution — indigo
- Screens: Orders ✔ (place→approve→receive), **In‑transit** ✔, GRNs ✔, delivery docs ✔,
  **branch↔branch transfers** ✔, settlement ✔, B2B **online ordering portal**.
- Charts: order **status funnel**, fulfilment **service‑level** gauge, transfer flow
  (sankey/flow), units **in transit** by destination.

### 3.6 Retail POS — teal
- Screens: **POS single‑page** ✔ (search→FEFO→cart→pay→change→receipt), **cash‑drawer
  session**, returns ✔, held sales, dispensing gate ✔ + **interaction warnings**,
  customer/patient lookup.
- Charts: **sales today** big number + **sparkline**, hourly **column** (busy hours),
  **payment‑mix** donut (cash/MoMo/card/insurance), top sellers, basket size.

### 3.7 Online (e‑commerce) — teal
- Screens: Storefront, product page, cart/checkout, **prescription upload**, order
  tracking, **pharmacist verification queue** (board, via approval engine), fulfilment.
- Charts: online vs counter **split**, conversion funnel, orders by status, delivery SLA.

### 3.8 Insurance — violet
- Screens: Insurers & schemes, policies/formulary, **claims queue** (board:
  accepted/declined/reversed), adjudication, **reconciliation**, prior‑auth.
- Charts: claims **status donut**, **rejection reasons** bar, insurer **aged
  receivables** (stacked buckets), co‑pay vs claim **split**.

### 3.9 Finance — green (see §5 for templates)
- Screens: **Receivables/Payables aging** ✔, AP/AR, **chart of accounts + journals**,
  cash & bank/MoMo reconciliation, **EOD closeout**, **financial statements**, budgets,
  **consolidated HQ**, EBM fiscal.
- Charts: **revenue vs margin** (dual‑axis line/bar), **cash position** (area),
  **P&L waterfall**, expense **breakdown donut**, **aging** stacked bar, **budget vs
  actual** (bullet), branch **comparison** bars, **daily/monthly gain** KPI tiles + trend.

### 3.10 People / HR — orange
- Screens: Employees + documents, **recruitment board**, **onboarding checklist**,
  **attendance**, **shift roster (calendar)**, **leave**, **payroll run wizard** +
  payslips, **training & competency** + SOP sign‑off, offboarding.
- Charts: headcount by branch/role (bar), **attendance** heatmap, leave **calendar**,
  payroll cost trend, training‑compliance **gauge**, turnover.

### 3.11 Connect (workspace/chat) — brand
- Screens: **Chat** (direct + branch/department channels), **Announcements**,
  **Tasks/To‑do**, **Shift notes**, **Knowledge base/SOPs**, contextual comments ✔,
  notification centre ✔.
- Charts: (light) unread/activity counters; task **board** + burn‑down.

### 3.12 Insights — rose
- Screens: **Role dashboards** (§6), **report builder**, saved reports, exports,
  **multi‑branch consolidation**.
- Charts: the full catalogue (§4), composable; scheduled report snapshots.

---

## 4. Visualisation catalogue (which chart for which job)
Pick by the **question**, not decoration ([doc 09](09-dashboards-and-charts.md); use the
validated palette + `dataviz` rules).
| Question | Visual |
|---|---|
| "What's the number now?" (sales today, cash, due) | **KPI tile** + delta + **sparkline** |
| "How is it trending?" (daily/**monthly gain**, stock value) | **line / area** |
| "Compare categories/branches/suppliers" | **bar / column** (grouped) |
| "What's the composition?" (payment mix, Rx/OTC, expense split) | **donut / pie** (≤6 slices) |
| "Composition over time" (sales by category by month) | **stacked bar / area** |
| "How overdue?" (receivables/payables) | **stacked aging bar** (current/30/60/90+) |
| "Where do we lose in a process?" (orders, claims, PO) | **funnel** |
| "Target vs actual" (budget, service level) | **bullet / gauge** |
| "Concentration" (ABC stock, top sellers) | **Pareto / treemap** |
| "When is it busy/absent?" (hours, attendance) | **heatmap** |
| "Flow between places" (transfers) | **sankey / flow** |
| "Profit build‑up" (P&L) | **waterfall** |
Rules: money right‑aligned tabular; colour‑blind‑safe; status never colour‑only; every
chart has a title, units, empty state, and a table fallback.

## 5. Documents & templates (numbered, hashed, QR‑verifiable — doc 08)
One template system: **org logo + subsystem tile** letterhead, gapless number,
SHA‑256, QR verify, vault. (✔ = built.)
- **Distribution/logistics:** Purchase order ✔, Proforma, Delivery note ✔, Packing
  slip, Waybill, **GRN** ✔, Bill of lading/customs (imports).
- **Retail:** **Receipt** ✔ (EBM fiscal fields), **Credit note** ✔, dispensing label,
  controlled‑drug register extract.
- **Finance:** **Tax invoice** ✔, Statement of account, Remittance advice, **Payslip**,
  **P&L**, **Balance sheet**, **Cash‑flow statement**, **Trial balance**, Receipt/voucher.
- **People/Compliance:** Employment contract, SOP acknowledgement, Training certificate,
  Controlled‑substance quarterly report.
Each template = a designed A4/thermal layout with header/body/totals/footer, bilingual
(EN + RW) where patient‑facing.

## 6. Role dashboards (the "manage everything" home per person)
- **Cashier:** today's sales + drawer, quick POS, held sales, shift note.
- **Pharmacist:** dispensing queue, interaction alerts, low stock, Rx to verify.
- **Warehouse:** put‑away/pick tasks, expiring/quarantine, temperature excursions.
- **Branch manager:** branch sales/margin, **pending approvals**, staff on shift,
  low‑stock, receivables — with **day vs month** toggles.
- **Finance officer:** cash position, aging, unreconciled, EOD status.
- **HR officer:** attendance today, leave to approve, licences/training expiring, payroll due.
- **HQ executive:** **multi‑branch** revenue/margin, cash, stock value, service level,
  compliance heat — drill into any branch; **"what we gained today / this month."**

## 7. Built‑in tools (the workspace utilities)
Always reachable (Connect + a tools launcher):
- **To‑do / tasks** — personal + assigned; due dates; board & list.
- **Calendar** — shifts, leave, deliveries, licence/expiry, payroll dates; per‑subsystem overlays.
- **Calculators** — **pricing/markup**, **VAT (by tax class)**, **cash & change**,
  **dosage & unit conversion**, **payroll PAYE/RSSB/CBHI** (rates in
  [doc 18](../18-rwanda-integrations-and-statutory.md)), **reorder/EOQ**, **aging/interest**.
- **Notes & knowledge base** — SOPs, shift notes, announcements.
- **Search everywhere** (⌘K) and **saved views/filters** across lists.

## 8. States, motion, responsiveness, accessibility (non‑negotiable)
- Every list/screen has designed **empty / loading (skeleton) / error** states.
- **Overlays** (doc 07): modals cap at viewport height and scroll their body; the
  app‑switcher and command palette are keyboard‑first.
- **Motion** 150–300 ms; **reduced‑motion** honoured; hover/focus always visible.
- **Responsive**: side nav collapses < 1024; POS is touch‑first; tables scroll inside
  their own container (page never scrolls sideways).
- **Theming**: light/dark via tokens; subsystem hue tints headers/active states only —
  never body text.

---

### How to read this with the rest of the docs
This blueprint = the **layout**. Field/document completeness → [doc 12](../12-requirements-fields-documents-approvals.md);
what each subsystem *does* → [ROADMAP](../../ROADMAP.md) + [operational playbooks](../16-operational-playbooks.md);
visual tokens/components/charts → [design/01](01-design-tokens.md), [06](06-components.md),
[09](09-dashboards-and-charts.md); brand/app‑switcher → [design/02](02-brand-and-logo-system.md).
</content>
