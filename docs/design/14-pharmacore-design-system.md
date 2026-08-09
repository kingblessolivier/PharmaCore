# PharmaCore design system — the whole-system plan

**Date:** 2026-08-10
**Status:** Phase 1 shipped. Phases 2–4 specified below, not built.

The goal, in one line:

> **Enterprise-grade operational system + modern executive SaaS quality +
> pharmaceutical visual language.**

Not a classic desktop ERP, and not a consumer dashboard. The personality is
**professional, clinical, operational, trustworthy** — a system somebody works
in for eight hours, that also looks like something an executive would fund.

---

## 0. Why this document exists

A 106-screen application designed screen by screen becomes 106 different
applications. This is the alternative: one set of decisions, taken once, that
every screen inherits.

```
                 PHARMACORE
                     │
              DESIGN SYSTEM
                     │
       ┌─────────────┼─────────────┐
       ↓             ↓             ↓
   Navigation     Components     Tokens
       └─────────────┼─────────────┘
                     ↓
              MODULE TEMPLATES
                     ↓
   Procurement · Inventory · Sales · Distribution · Finance
```

The rule that follows from it: **nothing hardcodes a colour, a radius or a
row height.** They live in `src/index.css` and `tailwind.config.js`, which is
why the whole application changed personality twice in two days by editing two
files rather than 425.

---

## 1. The visual ratio

The single most important rule, and the easiest to break:

```
████████████████████  Neutral surfaces   80%
███                   Teal brand         15%
█                     Status colour       5%
```

Teal is an **accent**, not the interface. It marks the active nav item, the
primary button, the selected tab, a focus ring. A screen where everything is
teal has no emphasis left to spend on the thing that matters.

Status colour is rarer still, and always means something:

| Colour | Token | Means |
|---|---|---|
| Green `#059669` | `success` | approved, received, in stock, completed |
| Amber `#D97706` | `warning` | expiring soon, low stock, awaiting approval |
| Red `#DC2626` | `danger` | expired, rejected, critical, recall |
| Blue `#2563EB` | `info` | in transit, processing, new |

Status colours are **reserved**. They are never a chart series and never a
brand accent — the moment amber means "a category" as well as "expiring soon",
neither meaning survives.

---

## 2. Surfaces — depth without shadow

```
--page      #F6F8FB   the ground everything sits on
  ↓
--surface-0 #FFFFFF   panels, cards, table rows
  ↓
--chrome-100 #F8FAFC  table headers, footers, subtle fills
```

Borders do the work shadows would: `1px solid #E2E8F0` for a panel edge,
`#CBD5E1` where a stronger separation is needed. The only real shadow in the
system is `0 1px 2px rgba(15,23,42,0.04)` on a card, and something heavier on
overlays — dropdowns, modals, the command palette — where the element genuinely
floats.

Twelve floating cards on a dashboard is visual noise. Twelve bordered panels on
a tinted ground is a control room.

---

## 3. Density

Two modes, because a warehouse operator and a finance director want different
things from the same table.

| | Comfortable (default) | Compact |
|---|---|---|
| Table row | 48px | 40px |
| Control height | 36px | 32px |
| Nav item | 38px | 38px |

Set once as `--row-h` / `--row-h-compact` / `--field-h`. A row shorter than
40px is hard to hit with a mouse; a row taller than 52px turns twenty lines
into a scroll.

---

## 4. Typography

Inter, with a hierarchy that is deliberately shallow — an operational system
has no room for display type.

| Role | Size | Weight |
|---|---|---|
| Page title | 20px | 600 |
| Page subtitle | 13px | 400 |
| Section title | 14px | 600 |
| Body / table cell | 13px | 400 |
| Table header | 12px | 600 |
| Label | 12px | 500 |
| Helper | 11–12px | 400 |

Labels are **sentence case**. `UPPERCASE TRACKING-WIDE` on every field label
is a marketing idiom; a label read past forty times a minute should be quiet.

---

## 5. Radii

```
6px   controls
8px   inputs, buttons
10px  cards
12px  major panels
```

Nothing above 12px. A 20px corner reads as a consumer app and, at a 48px row,
spends more pixels on the corner than on the content.

---

## 6. Icons

**One family: Lucide.** Mixing Font Awesome, Material and Heroicons in one
interface is the fastest way to look assembled rather than designed.

| Context | Size | Stroke |
|---|---|---|
| Sidebar | 18px | 1.8 |
| Toolbar, buttons | 16px | 1.8 |
| Large actions | 20px | 1.8 |

The pharmaceutical vocabulary — `Pill`, `Boxes`, `Warehouse`, `Truck`,
`ScanBarcode`, `Thermometer`, `ShieldCheck`, `ClipboardCheck` — but only where
the icon says what the thing *does*. An icon chosen because it looks medical is
decoration.

---

## 7. Navigation

```
┌──────────────────────────────────────────────────────────────┐
│ ☰  PharmaCore │ All organizations │ 🔍 Search / ⌘K │ 🔔 👤 │
├──────────────┬───────────────────────────────────────────────┤
│  248px       │  Page header                                  │
│  sidebar     │  Content                                      │
├──────────────┴───────────────────────────────────────────────┤
│  Status bar — branch · user · connection                     │
└──────────────────────────────────────────────────────────────┘
```

Sidebar 248px expanded, 68px collapsed, grouped under headings:

```
MAIN           Dashboard
OPERATIONS     Procurement · Inventory · Sales · Distribution
MASTER DATA    Products · Suppliers · Customers · Warehouses
FINANCE        Invoices · Payments
REPORTING      Reports · Analytics
ADMINISTRATION Users · Roles · Settings · Audit
```

Grouping is not decoration on a fourteen-module ERP — it is the difference
between scanning and hunting.

The active item is a **tint and a 2px left rule**, not a solid brand block.

---

## 8. The interaction model

This is the part that separates a good ERP from a set of pages:

```
SEARCH  →  TABLE  →  DETAIL DRAWER  →  FULL TRANSACTION
```

A user searching "Paracetamol" gets a table, clicks a row, sees a drawer with
the numbers that answer most questions, and only opens the full screen when
they need to *act*. Navigating away for every look is what makes an ERP feel
slow even when it is fast.

Actions are **contextual**. A selected purchase order offers Approve, Reject,
Print, Create GRN. A selected product offers Adjust Stock, Transfer, Batches,
History. A toolbar of twenty verbs where eighteen are invalid teaches people to
ignore toolbars.

---

## 9. Documents and transactions

Every document screen — PO, GRN, invoice, delivery note — is the same shape:

```
Goods Receipt Note
GRN-2026-00128                              ● Received
Supplier · PO · Warehouse · Received date
[Print] [PDF] [Approve] [More]
────────────────────────────────────────────────────
[Overview] [Items] [Delivery] [Approval] [History]
────────────────────────────────────────────────────
Grouped field sections, then the line grid
```

Forms are **grouped**, never one long vertical list: Supplier · Order ·
Delivery · Pricing · Items · Notes · Attachments · Approval. A forty-field
pharmaceutical transaction is navigable in eight groups and unusable as one
column.

Every transaction carries an audit trail — created / submitted / reviewed /
approved / completed, each with who and when. For a regulated product that is
not a feature, it is the record.

---

## 10. Pharmaceutical specifics

Where PharmaCore should go beyond a generic ERP:

**Batch and expiry as a first-class view.**

```
Paracetamol 500mg
Available 12,450 · Batches 8 · <30d 124 · <90d 450 · Expired 0

Batch      Qty     Manufactured   Expiry     Status
PCM-001    4,000   Jan 2026       Jan 2028   Good
PCM-003      124   Mar 2025       Sep 2026   ⚠ Expiring
```

**Handling requirements on the product**, not buried in a note: cold chain,
light sensitivity, humidity, hazard class. Already modelled in
`apps/catalog/handling.py`.

**Barcode and QR as an input method**, not a feature page — a warehouse screen
should accept a scan wherever it accepts a product.

---

## 11. Roadmap

### Phase 1 — Foundation ✅ shipped

Tokens, surfaces, density, typography, radii, icons, shell, sidebar, table,
buttons, fields, cards, drawers, dialogs. Applied through the shared layer so
all 106 screens moved together.

### Phase 2 — Components

A named component per job, so a screen is assembled rather than authored:

```
ui/          Button Input Select Badge Dialog Dropdown Tooltip Tabs Card
navigation/  AppHeader Sidebar Breadcrumb CommandPalette
data/        DataTable DataToolbar Pagination ColumnSelector
transaction/ TransactionHeader TransactionTabs TransactionSection
             ItemGrid ApprovalTimeline
pharma/      BatchStatus ExpiryIndicator StockIndicator ProductBadge
             BarcodeScanner
```

Most of `ui/`, `navigation/` and `data/` exists. `transaction/` is partly there
as `Workbench`. `pharma/` does not exist and is the highest-value gap.

### Phase 3 — Screen conversion

**81 of 106 screens still do their main work in a drawer or modal.** They now
look right, but the interaction is wrong: a purchase order is a document, not a
dialog. Convert in dependency order — procurement, then inventory, then sales —
so each module is coherent before the next begins.

### Phase 4 — Intelligence

Command palette (exists), then a PharmaCore assistant over the same data:
*"which products expire in 60 days"*, *"which warehouse is lowest on
amoxicillin"*, *"unpaid supplier invoices"*. It should **assist, never silently
act** — a system that can post a journal on a sentence is a system nobody can
audit.

---

## 12. The rule to keep

Do not design PharmaCore screen by screen. Change the token, the component or
the template — and let 106 screens follow. Twice in two days the entire
application changed personality by editing two files. That property is the
system; losing it is how enterprise software becomes inconsistent.
