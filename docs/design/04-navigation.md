# PharmaCore — Navigation (App Shell, Side Nav, Top Bar)

The frame every screen lives in. Designed so a user always knows *where they are,
who they are, and which organization's data they're looking at* — and can reach any
job in ≤2 clicks or one `⌘K`.

---

## 1. The app shell
```
┌──────────────────────────────────────────────────────────────────────────┐
│  TOP BAR (56px, sticky, --elev-0 with bottom hairline)                     │
│  [≡] [PharmaCore◆]   [Org/Branch ▾]        [ ⌘K  Search or run a command ]    │
│                                             [apps▦] [bell•] [help?] [user] │
├───────────────┬──────────────────────────────────────────────────────────┤
│ SIDE NAV      │  CONTENT AREA (single-surface workspace)                  │
│ 248px         │  ┌ breadcrumbs · title · [primary action]                 │
│ (collapses    │  │                                                        │
│  to 64px)     │  │  master list  │  detail / inline panel  │  context ▸   │
│               │  │                                                        │
│  sections…    │  └                                                        │
└───────────────┴──────────────────────────────────────────────────────────┘
```
- **Two-pane by default** (list + detail) so work stays on one page (see [05](05-single-page-workflow.md)).
- A right **context drawer** slides in for related info (batch history, audit, document preview) without leaving the page.

---

## 2. Top bar — what goes in it (and what doesn't)
Left → right:
1. **Sidebar toggle** (`≡`) — collapse/expand side nav.
2. **PharmaCore mark** — home / dashboard.
3. **Org / Branch switcher** (`building-2` + name + ▾) — *the* multi-tenant control.
   Switching re-scopes all data. Shows type badge (Depot/Retail/HQ). This is
   prominent because acting on the wrong branch is dangerous.
4. **Global command bar (center)** — the `⌘K` search-and-command surface, always
   visible as a wide input placeholder "Search or run a command". The heart of the
   single-page pattern.
5. **App switcher** (`▦` waffle) — grid of subsystem tiles (Google-waffle style).
6. **Notifications** (`bell` with count) — low-stock, expiry, claim-approved, EBM
   error, discrepancies. Opens a popover list, not a page.
7. **Help** (`?`) — docs, shortcuts, support.
8. **User menu** (avatar) — profile, shift status (clocked-in indicator!), theme,
   sign out.

**Not in the top bar:** primary page actions (those live in the content header),
deep navigation (that's the side nav), or per-record actions.

The **clocked-in indicator** on the user avatar is domain-specific and important:
it shows shift status, because terminal access depends on an active shift.

---

## 3. Side nav — structure
- **248px** expanded / **64px** collapsed (icons + tooltips). State persists per user.
- Grouped by **subsystem**, each group headed by its **hue tile + label**. The
  active item shows a **left accent bar in the subsystem hue** + filled icon +
  tinted background. Only the active item carries color — the rest is neutral.
- Max **2 levels**. Level-2 items reveal on group expand (accordion) or in the
  collapsed rail as a flyout.
- Role-aware: a user only sees subsystems/items their permissions allow (a cashier
  never sees Payroll).

### 3.1 Full navigation content (information architecture)

```
◆ Dashboard                         (home KPIs for current org)

▦ DISTRIBUTION            (depot & B2B)            [role: depot, manager]
   • Depot Catalog
   • Purchase Orders            (retail→depot)
   • Approvals & Allocation     (depot queue)
   • Shipments & Dispatch
   • Goods Received (GRN)        (retail intake)
   • Discrepancy Claims

▦ INVENTORY                                        [all stock-holding orgs]
   • Stock on Hand              (batch view)
   • Supplier Intake
   • FEFO / Expiry Forecast
   • Stock Adjustments
   • Wastage Log
   • Recalls
   • Department Transfers

▦ RETAIL                    (POS & dispensing)     [retail]
   • Point of Sale             (the counter — full-focus mode)
   • Prescriptions
   • Dispensing Queue
   • Cash Sessions / Drawer
   • Customers / Patients

▦ INSURANCE                                        [retail, insurance clerk]
   • Claims Queue
   • Adjudication
   • Manifests & Submission
   • Schemes & Formulary
   • Receivables Aging

▦ FINANCE & EBM                                    [accountant, admin]
   • EBM Fiscalization         (+ error retry queue)
   • Invoices & Credit Notes
   • Chart of Accounts
   • Journal Entries
   • Fiscal Periods
   • Expenses

▦ PEOPLE (HR)                                      [HR, manager]
   • Employees
   • Attendance & Shifts
   • Leave Requests
   • Payroll Runs
   • Licenses & Compliance

▦ INSIGHTS (Reporting)                             [manager+]
   • Dashboards
   • Operational Reports
   • End-of-Day Closeout
   • Document Vault

▦ ADMIN                                            [admin only]
   • Organizations & Branches
   • Users & Roles
   • Departments
   • Integrations (EBM / Insurers / SMS / Momo)
   • Statutory Rates
   • Audit Log
   • Notifications Settings

⚙ Settings   ·   ? Help & Shortcuts               (pinned bottom)
```

### 3.2 Behavior
- **Active state:** subsystem-hue left bar (3px) + `--brand-50`/hue-50 tint + filled icon.
- **Hover:** subtle `--surface-100` fill, 150ms.
- **Collapsed rail:** show subsystem tiles; hovering a tile flies out its level-2 list.
- **Badges:** counts on items needing attention (e.g. "Claims Queue ⁵", "EBM ⁽²⁾" errors) — muted unless danger (EBM errors red).
- **Search within nav:** typing in `⌘K` jumps to any nav destination too.

---

## 4. Breadcrumbs & page header
Inside the content area, each screen has:
`Subsystem › Section [ › Record]`  +  **screen title** (`text-h1`)  +  the **one
primary action** (filled button, right-aligned)  +  secondary actions (overflow `⋯`).
Breadcrumbs are for orientation and up-navigation; they are **not** how you perform
a task (that stays on-page).

---

## 5. Responsive behavior
- **≥1280:** full shell (nav + two-pane + optional context drawer).
- **1024–1280:** side nav auto-collapses to rail; context drawer overlays.
- **768 (tablet, e.g. GRN scanning):** nav becomes a slide-over; content single-pane;
  primary action becomes a bottom-fixed button.
- POS runs full-screen desktop; can hide the side nav entirely in "counter focus" mode.
