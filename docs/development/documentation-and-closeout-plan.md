# Documentation gap & close-out plan

**Status:** in progress · **Started:** 2026-08-07 · **Owner:** Claude

Brief: *"check all not documented and do new plan and work on it"*, following
*"sort also those remaining"* (the two items left open by the finance redesign).

---

## 1. What the audit found

Measured, not estimated — the numbers come from walking `backend/apps/*/models*.py`
and `*/urls.py` and checking each name against the canonical reference docs.

### G1 — No current data-model reference exists

`docs/02-data-model.md` is missing **roughly 145 of ~160 models**, across entire
subsystems.

**The framing matters, though.** That document says of itself: *"This is a design
document, not migrations… Nothing here is code yet."* It is not a reference that
rotted — it is the model as first drawn, and it was never meant to track the
build. The real gap is that **nothing else ever took over the job**, so for most
of the system there was no current reference at all:

| App | Models missing from `02-data-model.md` |
|---|---|
| catalog | 13 / 13 |
| distribution | 16 / 16 |
| finance | 28 / 29 |
| hr | 32 / 32 |
| iam | 11 / 11 |
| inventory | 22 / 24 |
| procurement | 20 / 20 |
| retail | 12 / 13 |
| approvals, events, workspace, documents | all but one each |

### G2 — Same for the API

`docs/07-api-design.md` is missing **~100 registered route prefixes** — all of HR's
twenty-one people routes, all twenty inventory routes, nineteen finance routes,
nine catalog routes, six each in distribution and retail. It too describes itself
as indicative v1 design, so the same conclusion holds: the design doc is doing its
job, and no live reference was standing behind it.

### G3 — The decisions made during the finance redesign are not in the ADR log

`docs/01-key-decisions.md` runs ADR-001 → ADR-014 and stops before this work. Six
decisions from F0–F4 are now load-bearing — code and tests depend on them — and are
recorded only in a working plan document.

### G4 — Finance generates no documents, and finance *is* documents

The documents engine is real and good: `apps/documents` renders a numbered PDF,
hashes it SHA-256, attaches a QR verification token and stores it write-once.
Retail, distribution and procurement all call it.

**Finance calls it zero times.** The most document-heavy function in the business
produces nothing a customer, supplier, auditor or bank can be handed.

What is missing, and what exists to build on:

| Document | Source record | Status |
|---|---|---|
| Tax invoice | `CustomerInvoice` | DocType exists, never wired |
| Receipt | `CustomerReceipt` | DocType exists, never wired |
| Credit note | `CustomerCredit` | DocType exists, never wired |
| Debit note | `SupplierNote` | no DocType |
| Statement of account | `statement_of_account()` | no DocType — report only, cannot be sent |
| Remittance advice | `PaymentRun` | no DocType — suppliers get no advice |
| Payment voucher | `SupplierBillPayment` | no DocType — no authorisation record |
| Journal voucher | `JournalEntry` | no DocType — manual postings leave no signed slip |
| Financial statements | P&L, balance sheet, trial balance, cash flow | no DocType — on screen only |
| VAT return | `vat_return()` | CSV draft only, no filed-copy PDF |

A report you can only look at is not the same as a document you can send, file and
later prove was not altered. That difference is the entire point of the documents
engine, and finance was left outside it.

### G5 — Eight chart components, used on one screen

`components/Charts.tsx` provides `LineTrend`, `Donut`, `BarChart`, `Waterfall`,
`Meter` and their scaffolding — validated palette, theme-aware, hover layer.
**Exactly one page imports it.** Ten finance screens have no visualisation:
budgets, banking, statements, aging, schedules, reconciliation, receivables,
customer statements, VAT, and the Finance home itself.

These are screens where shape matters more than the digits: whether receivables
are ageing, whether a budget is drifting, whether cash is trending down. A grid of
numbers makes the reader do that work in their head.

### Not a gap (checked and dismissed)

ADR-001–014 *are* written up in `docs/01-key-decisions.md`. An earlier reading of
this suggested the code cited ADRs that did not exist; that was wrong, and the log
is complete through 014.

---

## 2. Why hand-writing 160 entity descriptions is the wrong fix

The obvious response — write prose for every model — produces a document that is
correct for a week. It drifts the moment a field is added, and nobody notices,
because a stale document looks exactly like a current one — which is precisely why
the design docs were never promoted into references in the first place.

**The reference must be generated from the code, and the narrative must stay
hand-written.** Two documents with two jobs:

* **Generated reference** — every model, field, relation, constraint and endpoint,
  emitted from the live code by a management command. Always accurate by
  construction. The docstrings already carry the *why*; this work has been writing
  them all along, so the generated output is prose, not a field dump.
* **Curated narrative** — `02-data-model.md` and `07-api-design.md` keep explaining
  how a domain hangs together and which invariants matter, and point at the
  generated reference for the exhaustive detail.

A CI check then fails when the generated reference is out of date, which makes this
class of gap impossible to reopen.

---

## 3. Plan

| # | Work | Gate |
|---|---|---|
| **P1** | Finance document set — new DocTypes, templates, generation services, API + UI download | Every finance record a third party receives can be produced as a verified PDF |
| **P2** | Charts on the finance screens where shape matters, on the existing validated palette | No screen makes the reader plot a column of numbers in their head |
| **D1** | `manage.py generate_docs` → `docs/reference/data-model.md` and `docs/reference/api.md`, generated from models, serializers and routers | Every model and route appears; re-running produces no diff |
| **D2** | Narrative sections in `02-data-model.md` / `07-api-design.md` for the domains that have none, each pointing at the generated reference | No app is unexplained |
| **D3** | ADR-015 → ADR-020 for the load-bearing decisions from F0–F4 | Each cites the code and test that depend on it |
| **D4** | `--check` mode wired into CI so a model change without a docs regen fails | Regenerating is the only way to go green |
| **F5** | Multi-currency FX revaluation — the last open finance item | A foreign balance is restated at the closing rate; the difference posts to 7100 |
| **F6** | Unrealised profit on intercompany stock — the stated limitation in `consolidated()` | Group profit excludes margin on goods still inside the group |

F5 and F6 close the two items the finance redesign left explicitly open.

---

## 4. Progress log

- **2026-08-07** — Audit run and quantified (G1–G5). Confirmed ADR-001–014 exist, so the
  ADR log was complete up to this work rather than missing entirely. Also confirmed that
  `02-data-model.md` and `07-api-design.md` describe themselves as design-stage documents,
  so the finding is "no current reference existed", not "the reference rotted".

- **2026-08-07 — D1/D4 shipped.** `manage.py generate_docs` emits
  `docs/reference/data-model.md` (160 entities, 4,150 lines) and `docs/reference/api.md`
  from the model registry and URL resolver. Model docstrings carry the reasoning, so the
  output reads as prose rather than a schema dump. `--check` is wired into CI between the
  migration check and pytest, so a model or route change without a regen fails the build.
  Verified: zero models and zero routes missing; a second run produces no diff.
  It immediately proved itself — adding the eight finance document routes regenerated
  `api.md` without anyone remembering to.

- **2026-08-07 — D2/D3 shipped.** `02-data-model.md` and `07-api-design.md` now point at
  the generated reference and keep their design-intent role. ADR-015 → ADR-020 written for
  the load-bearing decisions from the finance redesign: the cost-centre dimension, actuals
  that can never be supplied, the checklist-gated close, two-sided bank reconciliation,
  reversing accruals, and the elimination policy.

- **2026-08-07 — P1 shipped (finance documents).** Seven new document types
  (debit note, statement, remittance advice, payment voucher, journal voucher, financial
  statements, VAT return) with templates, `apps/finance/documents.py`, eight API routes and
  UI buttons on statements, journal, the statement pack and the VAT return.
  **A test caught a real bug:** the module docstring claimed generation was idempotent and
  it was not — asking twice burned a number out of a gapless sequence and produced two
  numbered originals of the same statement. `generate_document` gained an opt-in
  `reuse_existing`, which finance passes everywhere. It stays opt-in because a purchase
  order reissued after an amendment genuinely *is* a new document.
  Vouchers carry the amount in words, because that is the line a pen cannot alter after
  signature.

- **2026-08-07 — P2 shipped (charts).** `Charts.tsx` had eight validated components used on
  one screen. Added: biggest-variance bars and a plan-to-actual waterfall on budgets; a
  revenue-to-net-profit waterfall and cost donut on the P&L; overdue-ranked bars on aging;
  still-to-release bars on schedules. Ranked by the number that matters — aging by overdue
  rather than total, since a large current balance is not a problem.
  Also fixed a stale `ProfitAndLoss` frontend type that predated the statement-ladder
  rewrite and was missing every line between gross and net.

- **2026-08-07 — F5 shipped (multi-currency FX revaluation).** IAS 21.
  - `ExchangeRate` is effective-dated and never overwritten: a revaluation done last
    month must keep producing last month's answer. `rate_for` takes the latest rate
    published **on or before** the date — falling forward would restate a period with
    news that did not exist yet — and raises rather than guessing when none exists.
  - `JournalLine` gained `currency`, `amount_fc` and `exchange_rate`. `amount` stays base
    currency, because a ledger foots in one currency or it does not foot; `amount_fc` is
    what revaluation needs, since a balance cannot be restated without knowing how many
    foreign units it is.
  - `Account.is_monetary` drives what gets restated, rather than guessing from a code.
    **Inventory is deliberately not revalued** — non-monetary, carried at the rate on the
    day it arrived. Revaluing it would restate the cost of goods sitting on a shelf.
  - `revalue()` posts the difference to `7100`, one entry per organization per date and
    idempotent on it. `exposure_report()` shows the exposure before anything is posted,
    and says plainly when it cannot compute for want of a rate.
  - **A test caught a real omission:** the currency fields were added to the model but
    `post_journal` never persisted them, so every line silently stayed RWF and no exposure
    could ever be found. Fixed, and covered.

- **2026-08-07 — F6 shipped (unrealised profit on intercompany stock).** Closes the
  limitation `consolidated()` had been printing.
  - `InventoryBatch.origin_unit_cost` records what the *selling* entity paid, populated on
    intercompany receipt. A lot the depot itself received from elsewhere in the group keeps
    the original cost, so margin cannot be laundered by transferring twice.
  - `unrealised_profit_in_stock()` eliminates the margin on group stock still held inside
    the group, and feeds `profit_effect` in `intercompany_eliminations`.
  - Batches transferred before the field existed have no origin cost. Those are **counted
    and reported** as `unmeasured_batches`, with the adjustment described as a floor —
    assuming zero margin would understate it and nobody would ever know.

- **2026-08-07 — document generators re-audited after a direct challenge.** Asked whether
  finance was genuinely sound, the honest answer was no, and checking found four defects
  that the first pass had shipped:
  - `credit_note_document` used `credit.reason`; the field is `notes` → **AttributeError**.
  - `customer_receipt_document` used `receipt.received_by`; the field is `created_by` →
    **AttributeError**.
  - `vat_return_document` guessed the report's payload keys (`rows`, `total_output`); the
    real ones are `output_by_class` / `output_total`, so it **rendered an empty return** —
    worse than crashing, because nobody goes looking at a document that produced output.
  - `remittance_advice_document` used a non-existent `value_date` and fell back to the
    creation date. A run raised on the 1st and paid on the 15th is a payment on the 15th.

  **Root cause: defensive `getattr(obj, "field", default)` and `dict.get(k, fallback)` in
  place of reading the models.** Those fallbacks did not make the code robust, they made
  it silently wrong, and they hid the fact that four of the nine generators had never been
  tested. All four are fixed against the real fields, the guessing is gone, and
  `test_every_generator_is_covered` now fails the build if any generator lacks a test.

**All planned work delivered.** 14 document tests (every generator), 16 FX/intercompany
tests, on top of the reference work above.
