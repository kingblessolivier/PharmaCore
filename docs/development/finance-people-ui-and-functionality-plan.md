# Finance (§9) & People (§10) — UI rebuild + functionality plan

> Generated 2026-08-07. Companion to [finance-hr-roadmap.md](finance-hr-roadmap.md)
> (which plans the *backend* PRs F1–F12) and to [ROADMAP.md](../../ROADMAP.md) §9/§10.
>
> This document exists because the backend has run ahead of the interface. Finance
> and People have real, working APIs behind screens that were written before the
> workspace had a design standard — so the subsystem *works* but does not *feel*
> like the rest of the product.

---

## 1. Where we actually are

### 1.1 Backend — mostly built

| PR | Scope | State |
|---|---|---|
| F1 | Domain event bus (`apps/events`, `OutboxEvent`, dispatcher) | ✅ |
| F2 | Existing cross-posts migrated onto the bus | 🚧 partial (`SALE_FINALISED`, approvals) |
| F3 | Statutory CoA sub-ledgers + Rwanda seed (2200–2250, 6100–6140) | ✅ |
| F4 | `NumberSequence` (+`Domain`), `TenantSettings`, `OpeningBalance` | ✅ |
| F5 | AR: `CustomerInvoice` / `CustomerReceipt` / `CustomerCredit` / `DunningNotice` | ✅ |
| F6 | Credit hold enforced on Distribution B2B orders | ❓ verify |
| F7 | AP 3-way match + `PaymentRun` / `PaymentRunLine` | ✅ (match shipped in `apps/procurement`) |
| F8 | `StatutoryFiling` generator + HQ intercompany eliminations | ❌ |
| F9 | Loans & advances deducted in payroll | ❌ |
| F10 | Recruitment → onboarding → offboarding + final settlement | ❌ |
| F11 | Training / CPD / competency / disciplinary / performance / salary revision | ❌ |
| F12 | Employee self-service (`/me/*`) + multi-currency FX | ❌ |

**People is the thin one.** `apps/hr` has exactly eight models — `Employee`,
`EmployeeDocument`, `StatutoryRate`, `PayrollRun`, `PayrollRecord`,
`AttendanceLog`, `ShiftRoster`, `LeaveRequest`. Against ROADMAP §10 that leaves
missing: `EmploymentContract`, `SalaryStructure`/`Component`/`Revision`,
`Timesheet`, `Shift` patterns, `LeaveType`/`Balance`/`Accrual`, `LoanAdvance`/
`LoanInstallment`, `PayrollAdjustment`, `StatutoryFiling`, `ProfessionalLicence`,
`CPDRecord`, `TrainingRecord`, `CompetencyAssessment`, `DisciplinaryAction`,
`PerformanceReview`, and the whole recruitment/onboarding/offboarding chain.

### 1.2 Two defects found while auditing

1. **`2230 CBHI Payable` is typed as an ASSET with a DEBIT normal balance**
   (`apps/finance/services.py` `_CONTROL_ACCOUNTS`). Every other statutory
   payable on the 2200 level is `LIABILITY`/`CREDIT`. As it stands, CBHI
   withheld from staff lands on the wrong side of the balance sheet and the
   Statutory Due dashboard will read it backwards. **One-line fix, but it needs
   a data correction for any tenant that has already run payroll.**
2. ~~Goods receipt posted `Dr 1200` (Bank) instead of `Dr 1500` (Inventory)~~ —
   the CoA was renumbered after the procurement postings were written. **Fixed
   2026-08-07**, tests updated.

### 1.3 Frontend — this is the real gap

32 screens already use the enterprise `DataGrid` (Distribution, Inventory,
Catalog, Admin, Procurement, and the newest AR screens). **Every older Finance
and People screen predates that rollout** and still hand-rolls `<table>` markup
with a `max-w-md` modal:

| Subsystem | On the standard | On the old pattern |
|---|---|---|
| Finance | Receivables, Dunning, Payment runs, Customer statement | Aging, Chart of accounts, Journal, Credit profiles, Supplier bills, Banking, Statements & close, Fixed assets, Tax & EBM, VAT, Tax payments, Budgets, Tax codes, Tenant settings, Statutory rates |
| People | *(none)* | Employees, Employee detail, Payroll, Attendance, Roster, Leave |

What the old pattern costs the user, concretely:

- **no search** — finding one employee in 400 means scrolling;
- **no sort** — you cannot rank payroll by net pay, or bills by due date;
- **no column control / density** — a finance clerk cannot make the grid dense
  and hide the columns they do not use;
- **no CSV export** — every one of these screens is something an accountant
  needs in Excel;
- **no bulk actions** — no "approve these six bills", "remind these customers";
- **no drawer** — records open as a cramped 448px modal, so multi-field forms
  (an employee, a fixed asset, a bank account) are a scroll tunnel;
- **inconsistent status colours** — each page redeclares its own `STATUS_TONE`
  map, so `APPROVED` is green here and brand-blue there.

---

## 2. The standard (what "meets standard" means)

Established by the Procurement subsystem and now extracted into shared modules:

| Module | Responsibility |
|---|---|
| `components/DataGrid.tsx` | The list. Search, sort, column show/hide, density, sticky header, bulk selection + action bar, CSV export, empty/loading states, per-user persisted view. |
| `components/RecordKit.tsx` | The record. `Drawer` (right-hand slide-over, sticky action footer), `Section`, `Field`, `Grid`, `Input`/`Select`/`Textarea`, `LineEditor` + `TotalsRow` for line items, `StatusBadge`, `ErrorNote`, `Facts`, `Empty`. |
| `lib/format.ts` | One vocabulary: `money`, `amount`, `pct`, `shortDate`, `dateTime`, `statusTone`, `statusLabel`. No page declares its own status colours again. |
| `components/AppHome.tsx` | The subsystem home: `AppHeader`, `StatTile`, `QuickAction`, `SectionCard`. |

**Rules for every screen.**

1. A list is a `DataGrid` — never a raw `<table>`.
2. A record opens in a `Drawer`, not a modal. Modals are only for a single
   confirm or a 2–3 field action.
3. Money is right-aligned, `tabular-nums`, formatted by `lib/format`.
4. Status is a `StatusBadge` — colour comes from `statusTone`, never inline.
5. Errors render inline at the point of action (`ErrorNote`), never a toast.
6. Every destructive or approval action states its rule in the UI
   ("you cannot approve your own run").
7. Read-only records render `Facts`, not disabled inputs.

---

## 3. Plan — UI

Ordered so the most-used screens land first. Each row is one commit.

### Phase U1 — People (6 screens)

| # | Screen | Work |
|---|---|---|
| U1.1 | Employees | `DataGrid` (search by name/number/title, sort, export, status + org filters) + employee `Drawer` with tabbed sections: identity, employment, pay & banking, next-of-kin, documents. Replaces the 5-field modal. |
| U1.2 | Payroll | `DataGrid` of runs (period, status, headcount, gross, deductions, net, approver). Run opens a `Drawer` with the **payroll register** as its own sortable/exportable grid + per-employee payslip download + submit/approve/mark-paid in the sticky footer. |
| U1.3 | Attendance | `DataGrid` (employee, date, in, out, hours, late, source) + date-range and exception filters; bulk-approve corrections. |
| U1.4 | Leave | `DataGrid` of requests + `Drawer` (balance, overlap warning, approve/reject) + a per-employee balance strip. |
| U1.5 | Shift roster | Keep the week grid (it is the right shape) but rebuild it on the kit, add publish/credential-check state and a `DataGrid` fallback list view. |
| U1.6 | People home | Rebuild on `AppHome` with real counters: headcount, on duty today, pending approvals, payroll due, licence expiries, training compliance. |

### Phase U2 — Finance core (6 screens)

| # | Screen | Work |
|---|---|---|
| U2.1 | Chart of accounts | Tree + `DataGrid` (code, name, type, normal balance, balance) with a drill-in `Drawer` showing that account's journal lines. |
| U2.2 | Journal | `DataGrid` (entry no, date, source, description, debit, credit, status) + `Drawer` with the balanced line detail and the reversal action. |
| U2.3 | Supplier bills (AP) | `DataGrid` + `Drawer`; show the linked PO/GRN and 3-way-match state now that Procurement provides it; bulk "add to payment run". |
| U2.4 | Aging (AR/AP) | `DataGrid` with bucket columns, per-partner drill-in `Drawer`, export. |
| U2.5 | Banking & cash | Account `DataGrid` + cash-book `Drawer`, statement import, reconciliation with bulk match. |
| U2.6 | Credit profiles | `DataGrid` + `Drawer` (limit, terms, hold, exposure vs limit bar). |

### Phase U3 — Finance tax, assets, close (6 screens)

| # | Screen | Work |
|---|---|---|
| U3.1 | Fixed assets | `DataGrid` + `Drawer` (acquisition, depreciation schedule, NBV, disposal). |
| U3.2 | Budgets | `DataGrid` with budget/actual/variance and a variance bar. |
| U3.3 | VAT / tax payments / EBM | One tax section on the kit; return `DataGrid`, payment `Drawer`. |
| U3.4 | Tax codes & statutory rates | Effective-dated `DataGrid` + `Drawer` with the source-URL requirement made visible. |
| U3.5 | Statements & close | Keep the report layout, move tables to `DataGrid` for export, add the close wizard to a `Drawer`. |
| U3.6 | Finance home | `AppHome` with the performance cockpit tiles. |

---

## 4. Plan — functionality

Ordered by what unblocks the most. Each is API + UI + tests, per the
[Definition of Done](definition-of-done.md).

### Phase P1 — People foundations (the biggest hole)

1. **`EmploymentContract` + `SalaryStructure`/`SalaryComponent`/`SalaryRevision`.**
   Today `Employee.base_salary` is a single number, so the gross→net engine
   cannot itemise housing/transport/responsibility — and transport matters
   because it is in the RSSB pension base but out of the maternity base.
   *Unblocks a correct payslip.*
2. **`LeaveType` / `LeaveBalance` / `LeaveAccrual`** behind the existing
   `LeaveRequest`, so a request can be validated against a real balance and
   unpaid leave can feed payroll. (F9-adjacent.)
3. **`Timesheet`** built from `AttendanceLog` + roster, with overtime and
   lateness derived, manager approval, and the invariant *"a payroll run cannot
   be approved while a timesheet is pending"*.
4. **`LoanAdvance` / `LoanInstallment`** (PR F9) auto-deducted on
   `PayrollRun.Calculated`.

### Phase P2 — People lifecycle

5. **Recruitment → onboarding** (PR F10): `JobRequisition`, `Applicant`,
   `InterviewSlot`, `OnboardingChecklist` driving a progress % on the employee.
6. **Offboarding** (PR F10): `Termination`, `ClearanceItem`, `FinalSettlement`,
   publishing `EmployeeTerminated`, de-provisioning the login.
7. **Training / CPD / competency / disciplinary / performance** (PR F11), with
   the two gates that actually matter: **an expired pharmacist licence revokes
   dispensing**, and **controlled-drug competency gates the dispense-controlled
   permission**.
8. **Employee self-service** `/me/payslips`, `/me/leave`, `/me/attendance`,
   `/me/profile` (PR F12) — the single most-used HR surface in any deployment.

### Phase P3 — Finance completion

9. **`StatutoryFiling` generator** (PR F8) — PAYE/RSSB monthly + VAT monthly +
   PIT annual, with the invariant *"cannot be marked FILED_PAID unless the GL
   sub-ledger balance equals the filing amount"*, plus the Statutory Due
   dashboard.
10. **HQ intercompany eliminations** (PR F8) — `consolidated()` is a sum today,
    not an elimination, so a consolidated balance sheet double-counts
    inter-branch transfers.
11. **Multi-currency / FX** (PR F12) — imports already post in RWF at a fixed
    rate; FX gain/loss on settlement is unmodelled.
12. **Finish F2** — move the remaining direct cross-app calls onto the bus
    (`PayrollRunApproved`, `GoodsReceivedNotePosted`, `InventoryAdjusted`,
    `StockDisposed`, `StatutoryPaymentConfirmed`).

### Phase P4 — Corrections

13. Fix **`2230 CBHI Payable`** to `LIABILITY`/`CREDIT` + a data migration for
    tenants that already posted payroll.
14. Verify **credit hold** (F6) actually rejects a B2B order, with a test.

---

## 4b. Progress log

**2026-08-07 — P4 corrections + P1/P2 People backend landed.**

- ✅ **P4.13** `2230 CBHI Payable` corrected to `LIABILITY`/`CREDIT`.
- ✅ **Goods-receipt posting** corrected from `Dr 1200` (Bank) to `Dr 1500`
  (Inventory) after the CoA renumbering.
- ✅ **Models** — 24 new People models in `apps/hr/models_people.py`
  (migration `0008`), plus ~25 new `Employee` fields. Covers ROADMAP §10's
  entity list end to end.
- ✅ **Services** — `apps/hr/services_people.py`: contracts, effective-dated
  salary structures + revisions, leave types/balances/accrual with held
  `pending` days, timesheet derivation from attendance, loan schedules and
  payroll settlement, hire-an-applicant, terminate-and-settle, competency gates,
  compliance alerts. `apps/hr/statutory.py` generates PAYE/RSSB/CBHI/VAT/PIT
  filings and cross-checks them against the GL sub-ledger.
- ✅ **API** — 20 new routers under `/api/hr/` plus `/api/hr/overview/`.
- ✅ **Tests** — `tests/test_people_lifecycle.py`, 27 tests, all green;
  98 green across HR + Finance + Procurement.

**2026-08-07 — U1 People UI landed.**

All People screens now run on the standard (`DataGrid` + `RecordKit` drawer +
`lib/format`). Nine screens, four of them new:

- ✅ **U1.1 Employees** — grid + a five-tab record drawer (profile, contract, pay
  structure, leave, development). The pay tab is the itemised component editor
  with live gross / pension-base / maternity-base totals.
- ✅ **U1.2 Payroll** — run grid + drawer whose payroll register is itself a
  sortable, searchable, exportable `DataGrid`.
- ✅ **U1.3 Attendance** — grid with derived hours and overtime badges.
- ✅ **U1.4 Leave** — requests grid with bulk approve, plus a balances view with
  seed-types and accrue actions.
- ✅ **U1.6 People home** — `AppHome` with live counters and a compliance
  attention list (contracts, probations, work permits, competencies, loans).
- ✅ **new** Timesheets, Loans & advances, Recruitment, Offboarding, Statutory
  filings.
- ✅ Shared kit promoted app-wide: `ProcurementKit` → `RecordKit`,
  `procurementData` → `recordData`, new `lib/format.ts` owning money and the
  status vocabulary; `EmployeeSelect` and `ProgressBar` added.

Two API defects the live run caught and fixed: `SalaryStructureViewSet` and
`LeaveBalanceViewSet` declared `http_method_names` without `post`, which silently
405'd their `set_for_employee` / `accrue` actions.

**2026-08-07 (later) — U1.5 roster + Finance foundations & cockpit.**

- ✅ **U1.5 Shift roster** rebuilt: week calendar with a real **pharmacist
  coverage guard** (a day flagged pharmacist-required is only covered if someone
  rostered on it holds a licence; uncovered days are called out), plus a
  `DataGrid` list view and a drawer that warns before you roster an unlicensed
  person onto a covered shift.

**Finance — the accounting itself, before any screen.** An audit against real
practice found five gaps; all five are now closed:

1. ✅ **`Account.classification`** (migration `0015`) — statements group by an
   explicit classification instead of inferring meaning from the account code.
   The old code read *anything starting with 5* as cost of sales, so adding
   "5500 Marketing" silently destroyed gross margin. There is now a regression
   test for exactly that.
2. ✅ **EBITDA corrected.** It was `net profit + depreciation`, which understates
   it by the interest and tax charged. It is now
   `operating profit + depreciation`, and a test asserts the 50,000 difference.
3. ✅ **P&L ladder** — revenue → COGS → gross profit → opex → **operating
   profit** → finance cost → tax → net profit, with margins at each level.
4. ✅ **Balance sheet grouped** current / non-current, with **working capital,
   current ratio and quick ratio**. Quick ratio matters most here: inventory is
   the bulk of a pharmacy's current assets and the least liquid thing it owns.
5. ✅ **Pharmacy-specific analytics** (`apps/finance/pharmacy.py`):
   - **Expiry exposure & IAS 2 provision** — stock banded by time-to-expiry with
     a ramped provision rate. Inventory that will not sell before it expires is
     a loss waiting to be recognised, and the owner needs it visible while there
     is still time to discount, transfer or return.
   - **Cash conversion cycle** (DIO + DSO − DPO) and the working-capital funding
     it implies — the number that explains how a profitable pharmacy runs out of
     money.
   - **Break-even** revenue and margin of safety.
   - **Capital returns** — ROE, ROA, ROCE and **GMROI**, all annualised.
   - **Margin by channel** (OTC vs Rx, brand vs generic, controlled) costed on
     the **FEFO lot the sale was actually drawn from**, not a price-list guess.
   - **Retail vs wholesale** split, and **branch comparison** for HQ.
   - Endpoints under `/api/finance/reports/`; **13 tests** in
     `tests/test_finance_pharmacy.py`, all green.
6. ✅ **Finance cockpit UI** (`/finance/cockpit`) — KPI row, expiry alert, and
   charts built as inline SVG in `components/Charts.tsx`: donut (where the money
   goes), waterfall (cash cycle), ranked bars (channel margin, expiry bands,
   branch revenue), meters (GMROI, current & quick ratio). The palette is
   **validated** — worst adjacent CVD ΔE 9.1 light / 8.4 dark — and every mark
   that falls under 3:1 on the light surface carries a visible direct label.


**Still open:** ⬜ the remaining Finance screens (chart of accounts, journal,
supplier bills, aging, banking, credit profiles, fixed assets, budgets, tax,
statements & close) still run the old table+modal pattern; ⬜ the
`EmployeeDetailPage` route, superseded by the drawer; ⬜ **P3** — intercompany
eliminations, multi-currency FX, finishing F2 on the bus.

**Known pre-existing failures** (all predate this work, all proven by reverting):
`test_tax_vat_ebm::test_vat_return_computes_net_payable`,
`test_sales::test_expired_stock_is_not_sold`,
`test_notifications::test_alerts_command_flags_low_stock_and_expiry`.
