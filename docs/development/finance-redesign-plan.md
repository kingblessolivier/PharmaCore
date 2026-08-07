# Finance redesign

**Status:** F0–F4 delivered · **Started:** 2026-08-07 · **Owner:** Claude

The brief was blunt and correct: *"plan and redesign whole finance cause now has no
meaning."* This document says precisely what "no meaning" is, then fixes it.

---

## 1. Diagnosis — eight specific defects

Not "the UI looks dated". These are structural.

### D1 — The navigation is a list of database tables, not a finance function

Twenty flat entries. Five of them are accounts receivable (*Receivables & payables*,
*Receivables (AR)*, *Collections & dunning*, *Customer statements*, *Customer credit*).
Four are tax (*Tax & EBM Audit*, *VAT return*, *RRA tax payments*, *Tax codes*). Two are
payables. Three are reporting.

Nobody's job is "tax codes". Someone's job is **close the VAT period**. The nav names
tables; the user thinks in tasks. Worse, the names collide — a user cannot predict
whether an overdue customer lives under "Receivables & payables" or "Receivables (AR)",
because both exist.

### D2 — The Finance home reports, but does not run the month

`/finance` renders a real home (`pages/apps/FinanceHome.tsx`, 363 lines) with period
presets, KPI tiles and section cards. It is a reporting page and a good one.

What it is missing is the operating half. It cannot tell you whether the books are
*complete*: nothing on it shows the close checklist, whether the bank was reconciled,
whether depreciation and the stock provision were posted, or whether any part of the
business stopped reaching the ledger this month. A finance head opening it learns what
the numbers say, not whether to believe them.

### D3 — Budget variance is fiction

`Budget.actual_amount` is a stored decimal that **nothing computes**. The only reference
outside the model is a serializer field — it is typed in by hand. So the variance screen
asks the user for the budget *and* the actual, then subtracts them.

A variance report whose actuals are typed by the person being measured is not a control.

### D4 — The ledger has no analysis dimension

`JournalLine` has `account` and nothing else. No cost centre, no branch, no department.

`Budget` is keyed by `department`. **The ledger has never heard of a department**, so
budget-vs-actual by department is unanswerable in principle — which is presumably why
D3 exists. The fiction is downstream of the missing dimension.

This is the single biggest structural hole: an HQ pharmacy with branches cannot ask
"what did Kicukiro spend on rent this quarter" and get an answer from its own books.

### D5 — Reconciliation has no counterparty

`JournalLine.is_reconciled` / `.statement_reference` exist, and `BankAccount` exists,
but **there is no bank statement in the system**. Nothing models what the bank says.

"Reconciliation" is therefore a checkbox you tick against your own records. Reconciling
your books to your books always succeeds and proves nothing. Bank rec exists to catch
the payment that left the account and never reached the ledger — and that is exactly
the case this design cannot detect.

### D6 — The expiry provision is a number on a screen, never a posting

`pharmacy.inventory_expiry_exposure()` computes a defensible IAS 2 provision. It is
reported and never posted. So the balance sheet still carries expiring stock at full
cost, and the P&L never takes the write-down. The dashboard and the statements disagree,
and the statements are the ones that get filed.

### D7 — Consolidation sums; it does not eliminate

`reports.consolidated()` adds the branches up. For a group whose depot sells to its own
retail branches, that **double-counts every internal transfer**: revenue in the depot,
cost in the branch, and the same goods counted twice on the way through. Group revenue
is overstated by the entire volume of intercompany trade.

### D8 — No period spine

Finance is period-driven; every number is "for the month" or "as at". `AccountingPeriod`
exists and can be closed, but no screen makes the period the organising fact. Each page
invents its own date filter, or has none, so two screens can disagree about what "now"
means and neither is wrong.

### D9 — Retail POS money does not reach the ledger truthfully

The POS records split tenders properly: `retail.Payment` has CASH / MOBILE_MONEY /
CARD, and a sale can carry several. But `finance.post_sale_journal` **debits 1100
Cash on Hand for the entire sale total**, whatever the customer actually paid with.

So a MoMo sale adds to the cash drawer in the books and never touches 1300 MoMo. Then:

* **Every till will show a shortage.** `DrawerSession` counts physical cash against a
  GL cash balance that silently includes card and MoMo takings.
* **MoMo reconciliation is impossible** — the MoMo statement shows receipts the ledger
  never recorded against that account.
* **Card money in transit is invisible.** Card settles T+1/T+2 net of a fee; there is
  no receivable, so cash is overstated on the day and the fee is never expensed.

And `DrawerSession.over_short` is computed, stored, and **never posted**. A till
shortage is a real cost that currently disappears before it reaches the P&L.

### D10 — Depreciation is never posted

`FixedAsset` carries `useful_life_years`, `salvage_value` and `accumulated_depreciation`,
and disposal posts a journal. **Nothing ever posts the periodic charge.** There is no
depreciation run — not a service, not a management command.

The P&L has a `DEPRECIATION` classification and EBITDA is defined as operating profit
plus depreciation. That add-back is always zero, so EBITDA silently equals operating
profit forever, and every asset sits on the balance sheet at cost until the day it is
sold, when the whole loss lands at once.

---

## 1a. The money map — what generates and consumes money, and whether the ledger hears about it

The brief: *"finance should communicate with other things that generate income and eat
money."* That is an auditable claim, so here it is audited. Every money-moving event in
the system, and its actual posting status today:

| Source | Effect | Posts today | Defect |
|---|---|---|---|
| Retail POS sale | income | ✅ `post_sale_journal` | **D9** — debits Cash even for card/MoMo |
| POS return / void | ‑income | ✅ | inherits D9 |
| Till over/short | cost | ❌ | computed by `DrawerSession`, never posted |
| Card settlement & fee | timing, cost | ❌ | no in-transit account, fee never expensed |
| B2B customer invoice | income | ✅ | — |
| Customer receipt | cash | ✅ | — |
| Goods receipt (GRN) | asset | ✅ procurement | — |
| Supplier invoice | cost/liability | ✅ procurement | — |
| Imports & landed cost | asset | ✅ procurement | — |
| Payroll + statutory | cost | ✅ | — |
| Stock count variance | cost | ✅ | — |
| Stock disposal / write-off | cost | ✅ `post_writeoff` | — |
| Expiry provision | cost | ❌ | **D6** — reported, never posted |
| Batch recall | cost | ❌ | no posting path at all |
| Depreciation | cost | ❌ | **D10** — no depreciation run exists |
| Fixed asset disposal | gain/loss | ✅ | — |
| Tax payments | cash | ✅ | — |
| Bank charges & interest | cost | ❌ | invisible until statements are imported (**D5**) |
| Inter-branch transfer | nil at group | ⚠️ | counted twice — **D7** |

Nine of nineteen money paths are broken or absent. That is the substance of "no meaning":
the ledger is not a faithful account of the business, so nothing built on top of it can be.

**The fix is structural, not a list of patches.** A `MONEY_SOURCES` registry in
`apps/finance/moneymap.py` declares each event, its GL treatment and its posting
callable; a coverage test fails if a declared source has no wired path; and the Finance
home renders the map so a gap is visible on screen rather than discovered at year end.

---

## 2. The redesign

### A. Information architecture — six sections, one home

The nav stops naming tables and starts naming the six jobs a pharmacy finance function
actually does. Each section gets a landing page (the `ProcurementHome` / `PeopleHome`
pattern): the KPIs for that job, what needs attention, and tiles into its screens.

```
Finance
├── Home              Period spine · money-flow map · what needs me today
├── Money in      AR  Invoices · Receipts · Credit control · Dunning · Statements · Aging
├── Money out     AP  Supplier bills · Payment runs · Aging · Supplier statements
├── Cash & bank       Accounts · Statement import · Reconciliation · Position & forecast
├── Ledger & close    Chart of accounts · Journal · Cost centres · Periods & close · Fixed assets
├── Tax & compliance  VAT return · EBM audit · RRA payments · Tax codes
└── Performance       P&L · Balance sheet · Cash flow · Budgets · Branches · Cockpit
```

Twenty ambiguous entries become seven predictable ones. The five AR entries become one
section with five screens under it — same screens, but now the user knows where to look
before they look.

### B. Model work

| # | Change | Fixes |
|---|---|---|
| M1 | `CostCentre` (org-scoped; BRANCH / DEPARTMENT / FUNCTION) + `JournalLine.cost_centre` | D4 |
| M2 | `JournalEntry.source_module` — which part of the business produced this posting | D2 (money map) |
| M3 | `Budget` → header + `BudgetLine` (account × cost centre × month). **Actuals computed from the ledger, never stored.** Drop `actual_amount`. | D3, D4 |
| M4 | `BankStatement` + `BankStatementLine` + `ReconciliationMatch` | D5 |
| M5 | `RecurringSchedule` + `ScheduleRun` — accruals & prepayments posted monthly | accuracy |
| M6 | `StockProvision` — post the IAS 2 expiry write-down, reverse and re-recognise each period | D6 |
| M7 | `PeriodTask` — the close checklist, with a trial-balance sign-off gate | D8 |
| M8 | `intercompany` flag on counterparty orgs + elimination pass in `consolidated()` | D7 |

Chart-of-accounts additions: `1590 Provision for slow-moving & expiring stock` (contra-asset),
`1600 Prepayments`, `2170 Accruals`, `5900` reused for the write-down charge.

### C. Screen work

Fifteen screens still run the old `<table>` + `max-w-md` modal pattern and move to
`DataGrid` + `RecordKit`: chart of accounts, journal, supplier bills, customer statement,
fixed assets, banking, budgets, credit profiles, tax codes, VAT, EBM, tax payments,
statements & close, aging, tenant settings.

Four are already on the standard (receivables, dunning, payment runs, cockpit) and only
need re-homing into the new sections.

### D. Phases

| Phase | Content | Gate |
|---|---|---|
| **F0** | Ledger spine — M1, M2, M3, M7 | Budget variance reads from the ledger; a cost-centre P&L is possible |
| **F1** | **Money map** — `moneymap.py` registry + coverage test; fix D9 (POS tenders, till over/short, card settlement & fee), D10 (depreciation run), batch recall, and post the D6 provision | Every declared money source has a wired posting path; the coverage test proves it |
| **F2** | Bank & cash truth — M4 | An unmatched bank line is detectable; bank charges surface |
| **F3** | Accuracy — M5 accruals/prepayments, M8 eliminations | Statements and cockpit agree; group revenue nets internal trade |
| **F4** | IA + screens — sections, landing pages, 15 rebuilds | Seven nav entries; no `<table>` left in finance |

F1 is sequenced second, immediately after the spine, because it is where money actually
leaks. A prettier screen over an unfaithful ledger is a worse product, not a better one.

Chart-of-accounts additions for F1: `1150 Card settlement in transit`, `1160 Till floats`,
`6150 Card & payment charges`, `6160 Cash over/short`, `6500 Depreciation`,
`1750 Accumulated depreciation` (contra-asset).

Each phase ends green: pytest, ruff, `tsc --noEmit`, `vite build`, and a live HTTP
walkthrough — the walkthrough has caught every bug the unit tests missed so far.

---

## 3. Progress log

- **2026-08-07** — Plan written. Diagnosis confirmed against the code: `Budget.actual_amount`
  has no producer (D3); `JournalLine` has no dimension beyond `account` (D4); no bank
  statement model exists (D5). Then D9 and D10 found while auditing the money map:
  `post_sale_journal` debits cash for every tender regardless of how the customer paid,
  and no depreciation run exists anywhere.
  **Correction:** D2 first claimed `/finance` and `/finance/aging` rendered the same
  component. They do not — `/finance` is a genuine 363-line home. D2 has been rewritten to
  the defect that is actually there: the home reports numbers but shows nothing about
  whether the books are complete.

- **2026-08-07 — F0 shipped (ledger spine).**
  - `CostCentre` (tree, BRANCH/DEPARTMENT/FUNCTION/PROJECT) + `JournalLine.cost_centre`
    + `JournalEntry.source_module`. `post_journal` now takes both, and a line-level
    centre overrides the entry-wide one so a single rent invoice can split across branches.
  - `Budget` rebuilt as header + `BudgetLine` (account × cost centre × month).
    **`actual_amount` deleted.** `budgeting.py` computes actuals from posted journal lines,
    excluding reversals exactly as the statements do; annual lines pro-rate across a partial
    window; variance carries a verdict read the right way round per account type.
  - `cost_centre_pnl()` reports contribution per centre plus `tagged_pct` — how much of the
    P&L is actually coded, so the report says how far it can be trusted.
  - `PeriodTask` + `closing.py`: a 13-item month-end checklist that blocks `close_period`
    until every blocking item is done or waived with a reason.
  - Migrations `0017`–`0019`. The old `Budget` was **renamed** to `BudgetLine` rather than
    dropped, so existing plans survived; verified against the dev database.
    The header takes an explicit `db_table` because SQLite keeps the original index names
    through a `RenameModel` and the old ones would have collided.

- **2026-08-07 — F1 shipped (money map).**
  - `moneymap.py`: 16 declared money sources with direction, GL treatment, posting callable
    and reference types. `test_money_map.py` fails the build if any declared source has no
    importable posting path.
  - **D9 fixed** — `_tender_debits()` splits a POS sale across `1100` cash, `1300` MoMo and
    `1150` card-in-transit per `retail.Payment`, falling back to cash when no tender rows
    exist. `settle_card_batch()` clears transit to bank and expenses the acquirer fee to
    `6150`. `post_drawer_variance()` posts till over/short to `6160` and is now called from
    `retail.services.close_drawer`.
  - **D10 fixed** — `run_depreciation()` charges straight-line monthly depreciation across
    the register (`6500` / `1701`), capped at the depreciable amount, idempotent per month.
    `6500` is the first account classified `DEPRECIATION`, so EBITDA's add-back is no longer
    structurally zero.
  - **D6 fixed** — `post_expiry_provision()` posts the IAS 2 write-down to `1590`, moving
    only the *difference* between the required and carried provision so the shrinkage line
    stays readable, and releasing it when the stock sells.
  - New accounts: `1150`, `1590`, `6150`, `6160`, `6500`. New command `run_month_end`
    (`--dry-run`, `--organization`, `--as-of`). New endpoints under
    `/api/finance/operations/`: `money-map`, `depreciation`, `expiry-provision`,
    `card-settlement`; plus `/api/finance/cost-centres/`, `.../pnl`,
    `/api/finance/budgets/{id}/variance`, and `/api/finance/periods/{id}/checklist`.
  - **Map correction:** `BatchRecall` carries no value — it is a freeze order, and its cost
    correctly reaches the ledger when the frozen stock is disposed of through `post_writeoff`.
    It was listed as a gap in the original audit; it is not one.

- **2026-08-07 — F4 started (information architecture).**
  - The Finance nav is now **seven sections instead of twenty flat entries**: Finance,
    Money in, Money out, Cash & bank, Ledger & close, Tax & compliance, Performance.
    The five separate receivables entries became one section; the four tax entries became
    one. `NavGroup` gained an `app` key so several groups can render as sections of a
    single app — without it `activeApp` matches the first group and the rest of Finance
    vanishes from the nav.
  - New **Cost centres** screen (`DataGrid` + `RecordKit`) with contribution per centre
    and the `tagged_pct` banner, so the report states how much of the P&L is actually
    coded before anyone relies on it. The parent picker excludes the centre's own
    descendants — the server rejects a cycle, but offering the choice is a trap.
  - Frontend types for the whole spine added to `lib/finance.ts`.

- **2026-08-07 — F2 shipped (bank reconciliation).** Closes D5.
  - `BankStatement` / `BankStatementLine` / `ReconciliationMatch` (migration `0020`).
    Statement lines are stored as first-class rows, so the two sides can actually
    disagree — which is the only way a disagreement can be found.
  - **The import refuses a statement that does not foot** (opening + movements ≠ closing).
    A file that has been truncated or edited would send someone chasing a difference that
    was never in the bank. Re-importing a period tops up missing lines rather than
    duplicating them, keyed on the bank's own transaction id where the export has one.
  - `parse_statement_csv` handles both export shapes — one signed `amount` column, or
    separate `debit`/`credit` columns — and normalises to one sign convention (positive
    increases our cash) so no reader downstream has to guess.
  - **Auto-match** pairs on exact amount within a five-day window, scored by reference
    overlap. It **refuses to guess** when two ledger lines fit equally well: two identical
    payments on one day are genuinely ambiguous, and picking one produces a reconciliation
    that looks complete while pointing at the wrong entry.
  - **Manual match is many-to-many** — a payment run leaves the bank once and settles a
    dozen bills — but the signed total must equal the bank line exactly, and a ledger line
    can only be claimed once (matching one payment to two bank lines would hide a duplicate).
  - **`explain_line` is how bank charges and interest reach the books at all.** No internal
    document produces them; the statement is their only source.
  - `reconciliation_summary` is the classic four-line statement, ending in the **unexplained
    difference**. `close_reconciliation` refuses to sign off while that is non-zero *or* any
    line is still unexplained — balances that agree by coincidence are not a reconciliation.
  - UI: `/finance/reconciliation` — statement list, then a workspace with the line grid,
    one-click match at the suggested confidence, a "post to ledger" drawer for unexplained
    lines, and the reconciliation panel with the difference called out.
  - 19 tests, including `test_a_payment_that_left_the_bank_without_reaching_the_ledger_is_caught`
    — the case the old boolean-tick design could not detect even in principle.

- **2026-08-07 — F3 shipped (accruals, prepayments, eliminations).**
  - `RecurringSchedule` / `ScheduleRun` (migration `0021`), new accounts `1600 Prepayments`
    and `2170 Accruals`. A cost now belongs to the months it was incurred in rather than
    the month it happened to be billed — insurance paid annually in January no longer
    wrecks January and flatters the other eleven.
  - **Accruals reverse by default**: the charge posts on the last day of the month and comes
    straight back out on the first of the next, so the supplier's invoice can be booked
    normally when it arrives without the cost being counted twice. Prepayments never
    reverse — the asset really is being consumed — and `create_schedule` enforces that even
    if a caller asks otherwise.
  - **The last period absorbs the rounding remainder.** Twelve months of 1,000,000 / 12 add
    up to 1,000,000, not 999,999.96; otherwise the balance sheet keeps a stub nobody can clear.
  - `run_schedules` catches up quietly — three missed months post to the months they belong
    to, not as a lump in the current period — and the run table's unique constraint on
    `(schedule, period_month)` is what makes it idempotent, not a flag someone remembers.
  - **D7 closed: `consolidated()` now eliminates.** Internal invoices (seller *and* buyer both
    inside the consolidation set) are netted out of group revenue and cost, and the matching
    intercompany receivable and payable cancel. VAT is stripped first, since the buyer
    recovers it and it never was group income. `gross_totals` keeps the pre-elimination sum
    visible beside the consolidated figures.
  - **Stated limitation:** profit on internally transferred goods still sitting in the buying
    branch's stock is *not* eliminated — that needs the transfer price of each remaining
    batch, which the stock records do not carry. `unrealised_profit_note` says so on every
    response. A consolidation that quietly ignores a known limitation is worse than one that
    names it.
  - API: `/api/finance/schedules/` with `run`, `summary` and `cancel`. `run_month_end` now
    posts schedules alongside depreciation and the provision.
  - 21 tests.

- **2026-08-07 — F4 shipped (every Finance screen).**
  - **One screen was actually broken, not merely dated:** `BudgetsPage` still POSTed
    `department` + `budgeted_amount` to an endpoint that now expects a header with lines.
    Rebuilt on the new model with a line editor and a variance view whose actuals come
    from the ledger — and no actual field anywhere in the form.
  - **Three API gaps found while wiring the UI.** `Account.classification`,
    `JournalEntry.source_module` and `JournalLine.cost_centre` all existed on the models
    and none were exposed on their serializers, so the fields the statements depend on had
    no way to be read or corrected from a screen. All three now are.
  - **Chart of accounts** gained classification editing, showing the effective statement
    line and flagging accounts still reporting on a type default — an account in the wrong
    line moves gross profit without anything looking broken.
  - **Journal** shows the source module and cost centres, filters by source, and tags a
    centre per line when posting.
  - **Fixed assets** runs depreciation from the screen; **Periods & close** carries the
    13-item checklist with per-item done/waive-with-reason; **consolidation** shows gross
    vs eliminated with the unrealised-profit limitation printed on the page.
  - **Finance home** gained the two panels it was missing (D2): the money map with per-source
    posting counts, and close readiness. It now answers "should I believe these numbers",
    not just "what are they".
  - New screens: **Cost centres**, **Accruals & prepayments**, **Bank reconciliation**.
  - Rebuilt: chart of accounts, journal, budgets, fixed assets, supplier bills, credit
    control, customer statements, aging, banking & cash book, EBM audit, RRA payments,
    tax codes, periods & close, plus receivables and payment runs moved from `Modal` to
    `Drawer`. **No Finance screen uses the old modal pattern any more.**
  - The `<table>` elements that remain are statement and document layouts — P&L, balance
    sheet, cash flow, VAT return, journal-entry lines. Those are not lists and should not
    be grids: you do not sort a profit and loss account.

**F0–F4 complete.** Still open beyond this plan: multi-currency FX revaluation, and
eliminating unrealised profit on internally transferred stock (needs transfer price per
batch on the inventory records).

The sequencing was deliberate: the ledger work came first because a prettier screen over
an unfaithful ledger is a worse product, not a better one.
