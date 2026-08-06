# Finance (§9) & People / HR (§10) — Multi-PR Finish Plan

> Generated 2026-08-06. Companion to [ROADMAP.md](../../ROADMAP.md) §9 and §10.
> Each PR is sized so it lands as one reviewable unit, with its own tests,
> and never leaves the project in a broken state (migrations apply, existing
> tests still pass, no half‑posted journals).

## Current state (audit)

`apps/finance/` already ships (mature):
- Chart of Accounts, Journals, idempotent `post_journal` + auto‑posters for
  SALE / PURCHASE / PAYMENT / PAYROLL / INVENTORY_ADJ / STATUTORY_PAYMENT /
  DEPRECIATION / BANK_RECON.
- AR side: `CreditProfile`, `request_credit_override` (approval‑gated).
- AP side: `SupplierBill` + `SupplierBillPayment` (2‑way bill↔payment flow).
- Banking: `BankAccount`, statement import, `cash_book_lines`, `reconcile_lines`,
  `cash_flow_forecast`.
- Tax: `TaxCode` (A/B/C/D), `TaxRecord`, `TaxPayment` (incl. WHT), `vat_return`,
  EBM mirror to GL.
- Period close: `AccountingPeriod` (Open/SoftClosed/HardClosed) + reopen audit.
- Fixed assets, budgets, performance cockpit (P&L, BS, CF, KPIs incl. DSO/DPO,
  GMROI, stock turns, period compare), `consolidated()` across orgs.

`apps/hr/` already ships:
- `Employee` + extended fields, `EmployeeDocument`, `EmployeeViewSet`.
- `StatutoryRate` (versioned, effective‑dated) + 2025/26 seed data.
- `PayrollRun` + `PayrollRecord` + pure `payroll.py` gross→net engine.
- `AttendanceLog` (clock in/out, IP/geo), `ShiftRoster`, `LeaveRequest`.
- Pages: employees, employee detail, payroll, attendance, roster, leave.

### Gaps against the spec

1. **§D — Domain event bus / `OutboxEvent`** is not implemented. Every
   cross‑subsystem integration (Payroll→GL, Sale→AR, GRN→AP) is a direct
   function call today.
2. **§9 — Statutory CoA sub‑ledgers** (PAYE/RSSB/CBHI/Occ‑Hazards/RAMA/VAT/WHT
   at 2200/2300 level, employer‑cost lines 6100–6140) are not seeded; payroll
   posting therefore has no proper destination accounts.
3. **§E — `NumberSequence`, `OpeningBalance`, `TenantSettings` (costing_method,
   fx_provider, pay_period, statutory_remittance_day, pit_deadline)** do not
   exist as models.
4. **§9 — AR machinery**: `CustomerInvoice`, `CustomerCredit`, `CustomerReceipt`
   models exist (migration 0007) but no service layer, no receipt allocation,
   no statements of account, no dunning ladder, no page. `FinancePage`
   (aging) probably reads from `CreditProfile`, not from invoices.
5. **§9 — AP finish**: no **3‑way match** (PO↔GRN↔Invoice enforcement), no
   **payment run** (batched, dual approval, MoMo disbursement file with
   idempotency keys).
6. **§9 — Statutory filing generator** (PAYE/RSSB monthly return file due
   15th) is missing — only the *payment* side exists.
7. **§9 — HQ intercompany elimination entries** at EOM are not generated;
   `consolidated()` is a sum, not an elimination.
8. **§9 — Multi‑currency / FX** is missing (imports need it).
9. **§10 — Recruitment → onboarding → offboarding** flow absent (no
   `JobRequisition` / `Applicant` / `OfferLetter` / `ClearanceChecklist` /
   `FinalSettlement`).
10. **§10 — Loans & advances** (`LoanAdvance` / `LoanInstallment` deducted on
    payroll) absent.
11. **§10 — Training / SOP / CPD / competency / disciplinary / performance**
    (`TrainingRecord`, `CPDRecord`, `CompetencyAssessment`,
    `DisciplinaryAction`, `PerformanceReview`) absent.
12. **§10 — Employee self‑service** (own payslip / leave / attendance view)
    has no `/me` route.
13. **§10 — Pharmacist licence auto‑revoke on expiry** (FR‑HR‑7) is wired
    (per doc 16: ✔), but worth a focused test pass.

---

## PR plan (12 PRs)

Each PR follows the [Definition of Done](definition-of-done.md): API **and**
UI shipped, role‑verified, tests + migrations, ROADMAP box ticked.

### ✅ Status — 2026-08-06

PRs F1, F2 (bus wiring), F4 (NumberSequence + helper + TenantSettings +
OpeningBalance) and the F1 → F2 partial land on `feat/finance-hr-f1-f4` off
`origin/staging`. PRs F5+ remain pending.

- **F1 — Domain Event Bus (§D).** `apps/events/` with `OutboxEvent`,
  `outbox.publish()` on `transaction.on_commit`, `subscribe(event_type,
  handler)` registry, `run_outbox_dispatcher` command (`SELECT … FOR UPDATE
  SKIP LOCKED`, exponential backoff, DEAD after 8 retries). Event taxonomy
  in `apps/events/events.py`. Tests in `backend/tests/test_outbox.py` and
  `backend/tests/test_dispatcher.py`. **9 commits on the branch.**
- **F2 — First events wired onto the bus (partial).** `SALE_FINALISED` from
  `apps.retail.services.complete_sale`; `APPROVAL_REQUESTED` /
  `APPROVAL_DECIDED` from `apps.approvals.services.request_approval` and
  `decide()`. Each publish is `transaction.on_commit`-wrapped.
  **`post_journal` is idempotent on `(org, reference_type, reference_id)`**
  via conditional `UniqueConstraint` — replays of the same source-doc tuple
  return the existing entry. Migration `0009_journalentry_uniq_reference_per_org`.
  Tests in `backend/tests/test_finance_post_journal_idempotency.py`.
- **F4 — Cross-cutting infrastructure (§E).**
  - `NumberSequence` extended with `Domain`; the unique constraint widens
    from `(org, kind, year)` to `(org, domain, kind, year)`. New Finance +
    HR kinds. Migration `0003_numbersequence_domain.py`.
  - `apps/core/sequences.py` `next_number()` + `next_document_number()`
    helpers. Tests in `backend/tests/test_core_sequences.py` (covers 10
    thread concurrency + transactional rollback).
  - `TenantSettings` model + lazy `tenant_settings_for()` service.
    Migration `0010_tenantsettings.py`. Tests in
    `backend/tests/test_tenant_settings.py`.
  - `OpeningBalance` import — single typed row per import line, validated
    per kind (trial balance must tie out, partners/products/employees must
    exist, no duplicate keys), atomic, idempotent on re-import. Management
    command `import_opening_balances <file.json>` with `--apply` to
    promote drafts to applied. Migration `0011_openingbalance.py`. Tests
    in `backend/tests/test_opening_balance.py`.

> The branch lives off `origin/staging`. Untracked WIP (inventory
> `analytics/coldchain/gs1/serialisation/warehouse_services`, finance
> `0007/0008`, the entire `apps/procurement/` directory) belongs to other
> developers — **not** part of this slice.

### PR F1 — Domain Event Bus (§D)

**Scope.** New app `apps/events/` (lightweight):
- `OutboxEvent(id, event_type, payload JSONB, occurred_at, status, retries,
  last_error, locked_at, locked_by)`.
- `outbox.publish(event_type, payload, *, source_doc_type, source_doc_id)`
  — must be called inside `transaction.on_commit`.
- `OutboxDispatcher` management command (Celery worker, or a management
  command invoked by a cron in dev) that:
  - claims pending rows with `SELECT … FOR UPDATE SKIP LOCKED`
  - dispatches to registered handlers via `subscribe(event_type, handler)`
  - retries with exponential backoff, marks `failed` after N.
- Event taxonomy seeded (constants module, not DB rows):
  `SaleFinalised`, `SaleReturned`, `EBMReceiptIssued`,
  `PurchaseOrderApproved`, `GoodsReceivedNotePosted`, `SupplierBillApproved`,
  `InventoryAdjusted`, `BatchQuarantined`, `BatchRecalled`, `StockDisposed`,
  `EmployeeHired`, `EmployeeTerminated`, `TimesheetApproved`,
  `PayrollRunApproved`, `PayslipPublished`, `StatutoryFilingGenerated`,
  `StatutoryPaymentConfirmed`,
  `CustomerInvoiceIssued`, `PaymentReceived`, `PaymentMade`,
  `CreditLimitChanged`, `CreditHoldEngaged`,
  `FiscalPeriodOpened`, `FiscalPeriodClosed`, `PeriodReopened`,
  `EODCloseFinalised`, `EOMCloseFinalised`,
  `ApprovalRequested`, `ApprovalClaimed`, `ApprovalGranted`,
  `ApprovalRejected`, `ApprovalEscalated`, `ApprovalSLABreached`.
- Handler registry, idempotency contract documented (consumers must tolerate
  duplicates; idempotent on `(event_type, source_doc_id, source_line_id)`).
- **Migration only — no existing handlers moved.** That is PR F2.

**Tests.** `test_outbox.py` — publish on commit, dispatcher claim/dispatch,
retry/backoff, idempotency contract, failed status after N retries.

**ROADMAP box ticked.** *(none — new infrastructure)*

---

### PR F2 — Migrate existing cross-posts onto the bus

**Scope.** Replace direct calls with event publishing:
- Sale finalisation in `apps/retail` → publish `SaleFinalised` → consumer
  in `apps/finance` calls `post_sale_journal` (already exists).
- `PayrollRun.approve()` in `apps/hr/payroll_run.py` → publish
  `PayrollRunApproved` → consumer in `apps/finance` calls
  `post_payroll_journal`.
- `GoodsReceivedNotePosted` in `apps/procurement` → publish →
  consumer posts inventory receipt (currently direct).
- `InventoryAdjusted` / `StockDisposed` → publish → consumer calls
  `post_inventory_adjustment` / `post_writeoff`.
- `TaxRecord.paid()` in `apps/finance/services.record_tax_payment` →
  publish `StatutoryPaymentConfirmed` → consumer posts the statutory
  clearing.
- `FiscalPeriodClosed` / `EOMCloseFinalised` → publish → consumer runs
  `consolidated()` eliminations (added in PR F8).

Direct callers are removed only after the consumer is proven end‑to‑end.
`outbox.publish` is `transaction.on_commit`-wrapped, so a rolled‑back
business transaction never produces a phantom event.

**Tests.** Extend `test_sale_journal_posting`, `test_payroll`,
`test_inventory_ops`, `test_tax_vat_ebm` — assert events are emitted,
handled, and the journal lines match the pre‑migration direct path.

**ROADMAP box ticked.** *(none — internal refactor)*

---

### PR F3 — Statutory sub-ledger CoA + Rwanda seed data

**Scope.** Extend `ensure_default_accounts(organization)` (called on first
finance access for a tenant) to seed:
- 1100 Cash, 1200 Bank, 1300 MoMo, 1400 AR Trade, 1500 Inventory,
  1700 Fixed Assets, 1701 Accumulated Depreciation.
- 2100 AP Trade.
- 2200 PAYE Payable, 2210 RSSB Pension Payable, 2220 RSSB Maternity Payable,
  2230 CBHI Payable, 2240 Occupational Hazards Payable, 2250 RAMA Payable.
- 2300 VAT Payable (Output), 2400 EBM Liability, 2500 WHT Payable.
- 3000 Equity.
- 4100 Retail Revenue, 4200 Wholesale Revenue, 4300 Services Revenue.
- 5000 COGS, 5100 Inventory Adjustments, 5900 Shrinkage.
- 6100 Salaries, 6110 Employer RSSB Pension, 6120 Employer Maternity,
  6130 Occupational Hazards Insurance, 6140 RAMA Employer.
- 7000 Tax expense.
- `TaxCode` rows for VAT A (0%) / B (18%) / C (0%) / D (exempt + WHT).
- New admin/manager page on `/finance/accounts` showing the seed tree.

Rewrite `post_payroll_journal` to debit the right employer‑cost accounts
and credit the 2200‑level statutory payables — today it just credits
"Salaries Payable".

**Tests.** `test_finance.py` / `test_payroll.py` — full payroll run
asserts each employee has lines on the correct statutory accounts, and the
trial balance rolls up per account.

**ROADMAP box ticked.** §9 chart of accounts ✅, statutory sub‑ledgers ✅.

---

### PR F4 — Cross-cutting infrastructure (§E): NumberSequence (extended), TenantSettings, OpeningBalance

> ⚠️ `apps/procurement/models.NumberSequence` already implements ROADMAP §E
> for procurement document kinds. This PR **extends** that model rather than
> duplicating it.

**Scope.**
- Extend `apps.procurement.models.NumberSequence`:
  - Add `Domain` (`choices ∈ {PROCUREMENT, FINANCE, HR, DOCUMENT}`).
  - Add a helper `next_number(org, kind, *, year=None) -> str` in a
    shared module (`apps/core/sequences.py`) that wraps the
    `SELECT … FOR UPDATE` claim used in `apps/documents/services.py:32`.
  - Add finance / HR kinds: `INVOICE` (customer), `JOURNAL` (voucher),
    `PAYSLIP`, `LOAN` (advance number), `STATUTORY_FILING` (PAYE/RSSB/
    VAT/PIT return reference), `PAYMENT_RUN`. Re‑use existing
    procurement kinds (`PO`, `GRN`, `SINV`, etc.).
- `TenantSettings(organization, costing_method ∈ {wac, fefo_lot},
  currency='RWF', fx_provider, default_country='RW',
  pay_period ∈ {monthly, fortnightly, weekly},
  statutory_remittance_day=15, pit_filing_deadline_month=3,
  pit_filing_deadline_day=31)` — one‑to‑one with org, seeded on tenant
  creation. Add `apps/finance/migrations/0009_tenant_settings.py` with a
  `post_migrate` signal that ensures a row exists for every Organization.
- `OpeningBalance(organization, kind ∈ {ar, ap, gl, stock, leave},
  payload JSONB, imported_at, imported_by)` + a management command
  `import_opening_balances` that validates trial balance ties out before
  commit.

Replace hand‑rolled invoice/bill/PO numbering with `next_number(...)`.

**Tests.** `test_number_sequence.py` (gapless under contention, both
procurement and finance kinds share the helper), `test_tenant_settings.py`
(default + override), `test_opening_balances.py` (import + tie‑out).

**ROADMAP box ticked.** §E infrastructure ✅ (first‑class).

---

### PR F5 — AR finish: CustomerInvoice services, receipts, allocation, dunning

**Scope.** Models already exist (`CustomerInvoice`, `CustomerCredit`,
`CustomerReceipt`). Add the service layer + pages:
- `services.py`:
  - `issue_customer_invoice(*, organization, customer, lines, due_date,
    tax_class, reference_type='SALE', reference_id) → CustomerInvoice` —
    posts Dr AR / Cr Sales + VAT Output, idempotent on
    `(reference_type, reference_id)`.
  - `record_receipt(*, organization, customer, amount, method, reference,
    invoice_ids) → CustomerReceipt` — splits the receipt across invoices
    in FIFO order, posts Dr Bank/MoMo / Cr AR, writes `PaymentAllocation`
    rows, rolls up `CustomerInvoice.status` (OPEN/PARTIAL/PAID/OVERDUE).
  - `statement_of_account(customer, as_of) → list[lines]` with 0–30/31–60/
    61–90/90+ buckets (aging).
  - `dunning_ladder(organization) → list[Customer]` — flag customers
    past `terms.days_overdue` with the next dunning step (reminder → letter
    → hold → legal).
- Pages:
  - `/finance/customers/:id/invoices` — invoice list + PDF download.
  - `/finance/customers/:id/statement` — printable statement.
  - `/finance/dunning` — dunning queue with bulk "send reminder".
- Outbox: `PaymentReceived` and `CreditHoldEngaged` are published by these
  services (Distribution consumes `CreditHoldEngaged` in PR F6).

**Tests.** `test_customer_ar.py` (extend) — full sale → invoice →
receipt → allocation → statement round‑trip; dunning escalates; credit
hold engaged on overdue breach.

**ROADMAP box ticked.** §9 AR & customer credit management ✅ (the
"receipts, credit application → credit limit, credit terms, credit holds,
aging + DSO, statements of account, collections/dunning" line).

---

### PR F6 — Credit hold enforces on Distribution B2B orders

**Scope.** When `CreditProfile.on_hold = True` (or `outstanding >
credit_limit`, or `days_overdue > terms.max_overdue`), the B2B order
creation endpoint in `apps/distribution` must reject with HTTP 409 and a
clear message — currently the limit is only *informational*.

- Add a small middleware/service hook on `OrderCreateView` (or whatever
  the B2B order endpoint is) that consults `CreditProfile` and rejects
  if blocked.
- The hold is **engaged** by the Finance service in PR F5; this PR only
  wires the enforcement side.
- Surfaces a banner on `OrganizationDetailPage` for sales reps.

**Tests.** `test_distribution_approval.py` — extend with credit‑hold
rejection case; `test_customer_ar.py` — engaged hold blocks B2B order
even when raised by an admin.

**ROADMAP box ticked.** §9 Credit hold → Distribution integration ✅.

---

### PR F7 — AP finish: 3‑way match + Payment Runs

**Scope.**
- **3‑way match.** `SupplierBill` has `reference_type` / `reference_id`.
  Add a service `record_supplier_bill_with_match(...)` that:
  - Looks up the linked GRN + PO.
  - Validates qty (± tolerance) and unit price (± tolerance) match.
  - On variance > tolerance, creates an `ApprovalRequest` (variance =
    "PO↔GRN↔invoice mismatch") and parks the bill in `PENDING_MATCH`.
  - On match, posts via the existing `record_supplier_bill` and moves the
    bill to `APPROVED`.
- **Payment runs.** New `PaymentRun(organization, status, total_amount,
  created_at, approved_by, approved_at, disbursement_file)` with
  `PaymentRunLine(payment_run, bill, amount)`.
  - States: DRAFT → AWAITING_APPROVAL → APPROVED → DISBURSED → LOCKED.
  - Threshold: amount > X requires dual approval (Finance manager +
    Director). Enforced via the existing approvals engine.
  - On APPROVED, generate a **MoMo disbursement file** (CSV with MSISDN,
    amount, reference, idempotency key = `run_id:bill_id`) and/or a
    **bank file** (CSV/MT103 placeholder). Stored on
    `PaymentRun.disbursement_file`.
  - On DISBURSED, calls `record_supplier_bill_payment` per line in a
    single transaction (idempotent).
- Pages:
  - `/finance/payables/matches` — variance queue.
  - `/finance/payables/runs` — payment runs list + new run wizard
    (select approved bills, optional grouping by supplier).

**Tests.** `test_finance_ap.py` (extend) — match succeeds, variance
parks for approval, payment run dual approval, MoMo file content matches
spec, idempotency on re‑dispatch.

**ROADMAP box ticked.** §9 AP — 3‑way match ✅, payment runs ✅, MoMo
disbursements ✅.

---

### PR F8 — Statutory filing generator + HQ intercompany eliminations

**Scope.**
- **Filing generator.** New `StatutoryFiling(organization, kind ∈
  {PAYE_MONTHLY, RSSB_MONTHLY, VAT_MONTHLY, PIT_ANNUAL}, period_start,
  period_end, due_date, status ∈ {DRAFT, GENERATED, FILED, FILED_PAID},
  payload JSONB, file)`.
  - For PAYE/RSSB monthly: aggregate `PayrollRecord` rows for the period,
    cross‑check against the 2200‑level GL sub‑ledger balances
    (validation invariant: filing amount must tie to GL balance).
  - For VAT monthly: aggregate `TaxRecord` (output) and supplier bill VAT
    input for the period.
  - Generates a return file (CSV) per filing kind, attaches to
    `StatutoryFile.file`.
  - `mark_filed()` requires Finance manager approval; `mark_filed_paid()`
    requires the linked `TaxPayment` to exist.
  - Surface on `/finance/statutory` — due‑soon list + "Generate" button.
- **HQ consolidation eliminations.** `consolidated()` currently sums orgs.
  Extend with `eliminate_intercompany(organizations, period)`:
  - Find `JournalLine` rows where `memo` matches the intercompany marker
    (or a new `IntercompanyTransaction` model in `apps/finance/`).
  - Generate elimination entries at EOM (Dr/Cr the same accounts) so the
    consolidated trial balance zeroes intercompany balances.
  - Wire as a consumer of `FiscalPeriodClosed`.

**Tests.** `test_finance_reports.py` (extend) — filing generator ties
out, FILED_PAID blocked when GL mismatch; `test_consolidation.py` —
eliminations zero intercompany, consolidated BS still balances.

**ROADMAP box ticked.** §9 Statutory filings ✅, HQ consolidation
eliminations ✅.

---

### PR F9 — HR: Loans & advances, integrated with payroll

**Scope.**
- `LoanAdvance(employee, principal, balance, monthly_installment,
  start_date, kind ∈ {SALARY_ADVANCE, EMERGENCY, OTHER}, status)`.
- `LoanInstallment(loan, payroll_run, due_date, amount, paid)`.
- A payroll‑engine hook in `apps/hr/payroll.py` that auto‑deducts the
  next due installment per loan on `PayrollRun.Calculated`, unless the
  employee is on unpaid leave (configurable).
- New `LoanAdvanceViewSet`, `/people/loans` page (list, detail, schedule).

**Tests.** `test_payroll.py` (extend) — installment deducted on next
run, balance rolls down, unpaid‑leave case skips, fully repaid loan
becomes inactive.

**ROADMAP box ticked.** §10 loans/advances ✅ (lives under payroll
controls).

---

### PR F10 — HR: Recruitment, Onboarding, Offboarding

**Scope.**
- Recruitment: `JobRequisition(department, role, status, opened_at,
  closes_at, hiring_manager)`, `Applicant(requisition, name, contact,
  documents, stage ∈ {APPLIED, SHORTLISTED, INTERVIEWED, OFFERED,
  HIRED, REJECTED, WITHDRAWN})`, `InterviewSlot(applicant, panel,
  scheduled_at, score, decision)`.
- Onboarding: `OnboardingChecklist(employee, items JSONB, completed_at)`
  with default items from a per‑role template (NPC licence, contract,
  ID copy, asset issue, SOP ack). Drives a `OnboardingProgress` percent
  on the employee detail page.
- Offboarding: `Termination(employee, reason, last_working_day,
  initiated_by, approved_by, approved_at, status)`, `ClearanceItem(...)`
  (laptop, badge, keys, final payslip, certificate of service),
  `FinalSettlement(employee, leave_encash, pro_rata, dues_total,
  computed_at, paid_via)`.
- Termination approval publishes `EmployeeTerminated` (already seeded in
  PR F1). On approval: `Employee.user.is_active = False`,
  `Employee.status = TERMINATED`, `FinalSettlement` generated.
- Pages: `/people/recruitment`, `/people/onboarding/:employeeId`,
  `/people/offboarding/:employeeId`.

**Tests.** `test_hr_advanced.py` (extend) — applicant → hired →
onboarding → termination → final settlement round‑trip; invariants hold
(employee cannot terminate while open payroll run exists — enforced by
a `pre_save` check on `Termination`).

**ROADMAP box ticked.** §10 recruitment → onboarding ✅, offboarding
+ final settlement ✅.

---

### PR F11 — HR: Training, CPD, Competency, Disciplinary, Performance

**Scope.**
- `TrainingRecord(employee, course, completed_at, certificate_no,
  expiry_date)`.
- `CPDRecord(employee, activity, hours, date, evidence)`.
- `CompetencyAssessment(employee, competency, assessed_at, score,
  assessor, valid_until)` — special competency
  `CONTROLLED_DRUG_HANDLING` is required for any user granted the
  dispense‑controlled permission.
- `DisciplinaryAction(employee, kind ∈ {VERBAL, WRITTEN, FINAL,
  SUSPENSION, DISMISSAL}, issued_at, reason, document)`.
- `PerformanceReview(employee, period, rating, goals JSONB, manager,
  acknowledged_at)`.
- `SalaryRevision(employee, effective_date, old_structure, new_structure,
  approved_by)` — historical record (also used by payroll for back‑pay).
- Pages:
  - `/people/training` — training matrix + competency heat‑map.
  - `/people/licences` — pharmacist licence expiries (already partly
    exists via `EmployeeDocument`; this PR adds the expiry‑gating test
    and the renewal alert job).
  - `/people/performance/:employeeId` — reviews + goals.

**Tests.** `test_hr_advanced.py` (extend) — controlled‑drug competency
gates dispense permission; expired licence auto‑revokes (FR‑HR‑7);
salary revision flows into next payroll run.

**ROADMAP box ticked.** §10 Training & SOP ✅, CPD ✅, Performance ✅,
auto‑revoke licence ✅ (focused test pass).

---

### PR F12 — Employee self‑service + Multi‑currency (FX)

Two small surfaces bundled because each is a focused, single‑page PR:

**Self‑service.**
- `/me/payslips` — employee's own payslips (PDF download).
- `/me/leave` — leave balance + request form.
- `/me/attendance` — own attendance history.
- `/me/profile` — editable personal info (limited fields: phone,
  address, next‑of‑kin, password change).
- RBAC: any authenticated `Employee` whose `user` row matches the
  requester.

**Multi‑currency.**
- `Currency(rate_to_rwf, valid_from, valid_to, source)` + resolver.
- `TenantSettings.currency='RWF'` (default) or `'USD'` / `'EUR'`.
- `JournalLine.foreign_amount`, `JournalLine.foreign_currency`,
  `JournalLine.fx_rate` — non‑RWF amounts stored in addition to RWF
  base.
- Supplier bills with foreign currency: convert at `valid_on= bill_date`
  rate; FX gain/loss posted on payment (Dr/Cr FX Gain/Loss, Cr AP).
- `/finance/fx` — daily rate import + manual override.

**Tests.** `test_hr.py` — self‑service permissions, leave request flow
end‑to‑end; `test_finance_ap.py` (extend) — foreign‑currency supplier
bill → payment posts FX gain/loss correctly.

**ROADMAP box ticked.** §10 self‑service ✅, §9 multi‑currency ✅.

---

## Sequencing & dependencies

```
F1 (bus) ──► F2 (migrate) ──► F3 (CoA) ──► F4 (infra) ──► F5 (AR) ──► F6 (credit hold)
                                                            │
                                                            └─► F7 (AP) ──► F8 (statutory + elim)
                                                                          │
F9 (loans) ──► F10 (recruit/onboard/offboard) ──► F11 (training/CPD) ─────┤
                                                                          │
                                                                          └─► F12 (self‑service + FX)
```

- F1 must land first — every later PR uses the bus.
- F2 is independent of F3–F12 but must come early so the bus has real
  traffic.
- F3, F4 are pure‑infra and parallel‑safe; merge in either order.
- F5, F7, F8 are Finance‑side and can be parallelised after F3+F4.
- F9, F10, F11 are HR‑side and can be parallelised after F2.
- F12 is a focused wrap‑up PR.

Suggested cadence: **2 PRs per week** (one Finance, one HR), 6 weeks to
finish.

---

## Risks & non‑goals

- **Performance cockpit** is already ✅ (in `reports.performance`).
  No new KPI work in scope.
- **Inventory valuation & costing (WAC vs FEFO‑lot)** is partially ✅
  (current `inventory_valuation()` is WAC). Switching costing method
  per `TenantSettings` is a separate workstream — out of scope here;
  flagged for a follow‑up PR after F4 lands.
- **Approval workflow** (FR‑generic) is already ✅ across the codebase
  per the memory note; no approval‑engine changes in this plan.
- **Multi‑branch consolidation** already works; only the **eliminations**
  are added.
- **EOD/EOM closeout wizard** is partially in `reports.py`; the wizard
  UI on `/finance/periods/:id/close` is a small follow‑up if needed.
