# PharmaCore — Key Architectural Decisions (ADR log)

> **Alignment note — foundational (early) doc.** PharmaCore is now framed as a **workspace of subsystems**; the research-backed specs [docs 12–19](README.md) and the [ROADMAP](../ROADMAP.md) **supersede or extend** anything here (each cites its sources). Key deltas: backend is **Django + DRF** (ADR-006, not FastAPI); the depot→retail transfer shipped as the **lean flow** — place → **approve = ship** → **receive = land**, auto-listing at the destination — with picking / driver / per-item-count logistics deferred to the Warehouse phase; and much of this is **already built** (see ROADMAP status). Verified Rwanda/international facts live in [13](13-regulatory-licensing-and-documents-rwanda.md) / [14](14-international-operational-standards.md) / [17](17-insurance-and-government.md) / [18](18-rwanda-integrations-and-statutory.md).

Decisions that materially shape the design. Recorded as we settle them.

---

## ADR-001 — Retail POS must keep selling offline (local-first + sync)

**Decision:** The retail counter must continue selling when the internet drops.
Sales are captured locally and synchronized (including EBM fiscalization and
insurance claims) once connectivity returns.

**Status:** Accepted (2026-08-03)

**Consequences (this is the heaviest decision in the system):**
- The POS is a **desktop app with a local datastore** (Tauri/Electron + local DB,
  e.g. SQLite), not just a browser talking to a server. → confirms "web + desktop".
- We need a **sync engine**: local → central reconciliation, with:
  - **Conflict-free IDs** — sales/receipts get **UUIDs** generated on the device
    (never rely on a central auto-increment while offline).
  - **Batch stock is the contention point.** Two offline counters could both sell
    the last pack of a batch. Mitigate with per-terminal stock allocation and a
    server-side reconciliation that flags oversell for a manager (matches the
    "physical count mismatch" guardrail).
  - An **outbox pattern**: offline actions (sale, EBM submit, claim) are queued
    events, replayed in order when online.
- **EBM and insurance are inherently deferred** anyway → aligns perfectly with the
  async state machine. Offline just extends the queue window.
- Reporting/EOD closeout must tolerate **not-yet-synced** terminals (show pending).
- Central server remains the **source of truth**; the device holds a **working
  subset** (its own stock, catalog, pricing, open sales).

**Rejected alternative:** always-online POS (simpler single-DB design) — rejected
because Rwandan retail connectivity isn't reliable enough to stop selling.

---

## ADR-002 — Multi-insurer from day one

**Decision:** Support multiple insurance schemes from the start, not just CBHI.

**Status:** Accepted (2026-08-03)

**Consequences:**
- Model `insurance_scheme` (CBHI/RSSB, RAMA, MMI, private insurers…) each with its
  own **coverage rule** (e.g. 85/15) and **covered-drug formulary**.
- `organization` ↔ `insurance_scheme` is **many-to-many** (a pharmacy holds
  agreements with several insurers), with per-agreement terms.
- The sale engine computes coverage as a function of *(scheme, drug on formulary?,
  coverage rule)* — never a hard-coded percentage.
- Patient/customer record can carry a **policy/membership number** per scheme.
- Claims are grouped into **per-scheme periodic manifests** for submission.

---

## ADR-003 — Abstract the EBM integration (`EbmProvider`), choose OSDC/VSDC later

**Decision:** Build an `EbmProvider` interface now; defer the OSDC-vs-VSDC choice
until RRA certification details are confirmed.

**Status:** Accepted (2026-08-03)

**Consequences:**
- Define a provider contract: `register_item`, `register_purchase`, `sign_sale`,
  returning {SDC ID, receipt number, signature, QR}.
- Ship a **MockEbmProvider** for development/testing (no RRA dependency).
- Real adapters (`OsdcProvider`, `VsdcProvider`) implement the same contract;
  swap via config. Product master carries **tax class + RRA item code**;
  organization carries **TIN + SDC/Developer credentials**.
- **Business prerequisite (not code):** obtain RRA **CIS certification / Developer
  ID** before go-live. Track as a project milestone.

---

## ADR-004 — English-only user interface

**Decision:** The PharmaCore UI is **English only**. No bilingual/Kinyarwanda UI,
translation catalog, or language switcher is in scope.

**Status:** Accepted (2026-08-03)

**Consequences:**
- One string source, one voice — simpler copy, terminology, and QA.
- Copy is kept **plain and ESL-friendly** (many users are English-as-second-language);
  domain/legal terms follow official RRA / Rwanda FDA English forms.
- Money/date/quantity still use Rwandan conventions (RWF, `dd MMM yyyy`).
- UI strings are still **externalized into one catalog** (good practice + leaves the
  door open if another language is ever requested later) — not a bilingual commitment.
- See design doc [11-ux-writing-and-terminology.md](design/11-ux-writing-and-terminology.md).

## ADR-005 — Product naming: "PharmaCore" (by Medlink)

**Decision:** The unified platform is named **PharmaCore**. **Medlink** is the
**company** (vendor). Sub-systems are named **PharmaCore {Subsystem}** — PharmaCore
Distribution, Inventory, Retail, Insurance, Finance, People, Insights, Admin.

**Status:** Accepted (2026-08-03)

**Context:** "Medlink" alone is the company; the product needed its own name that (a)
signals a single unified platform and (b) makes the pharmacy domain obvious. The name
had to contain "Pharma".

**Consequences:**
- Brand hierarchy: **Medlink** (company) › **PharmaCore** (platform) › **PharmaCore
  {Subsystem}** (modules). Lockup: "PharmaCore" wordmark, optionally "by Medlink".
- The [brand & logo system](design/02-brand-and-logo-system.md) uses **PharmaCore** as
  the master wordmark; the sub-system logo family relabels to **PharmaCore {Subsystem}**
  (tiles/hues/glyphs unchanged).
- On generated documents, **PharmaCore by Medlink** appears as the system-of-record in
  the footer (Medlink is the vendor of record).
- The **repository directory** stays `Medlink` (harmless — it's the folder, not the brand).
- Docs are being updated to distinguish company (Medlink) from product (PharmaCore);
  where older docs say "Medlink" as the *system*, read it as *PharmaCore*.

## ADR-006 — Backend framework: Django + Django REST Framework

**Decision:** The backend is **Django + Django REST Framework (DRF)**, with the
**Django ORM + Django migrations**. This supersedes the initial FastAPI + SQLAlchemy
+ Alembic scaffolding (which existed only as a Phase 0 health-endpoint skeleton).

**Status:** Accepted (2026-08-03) · supersedes the implicit FastAPI choice

**Context:** PharmaCore is a CRUD-heavy ERP with strong compliance requirements
(RBAC, immutable audit, license-gated actions). We evaluated FastAPI vs Django.

**Options considered:**
- **FastAPI** — async-first, Pydantic, minimal, auto-OpenAPI. Excellent for an
  API-first SPA backend; but we'd hand-build the ORM, migrations, admin, and auth.
- **Django + DRF (chosen)** — batteries-included **ORM, migrations, auth, and admin**;
  DRF for the JSON API our React SPA consumes; **drf-spectacular** gives the OpenAPI
  schema that still generates the typed frontend client.

**Consequences:**
- We get an integrated ORM/migrations and a built-in **admin** (useful for an ERP's
  back-office) without extra wiring.
- Auth via **djangorestframework-simplejwt** (JWT) + Django's permission framework as
  the base for our custom RBAC; **argon2** password hashing.
- API contract via **drf-spectacular** → typed React client (unchanged goal).
- Trade-off: less async-native than FastAPI (fine at our scale; heavy IO work already
  runs in Celery workers). Our compliance rules (immutability, append-only audit) are
  custom regardless of framework, so Django's editable admin/auth is customized, not
  taken as-is.
- Docs updated across the repo to Django/DRF (stack, architecture, coding standards,
  CI, onboarding, etc.). See [09-technology-stack.md](09-technology-stack.md).

## ADR-007 — Include a Collaboration, Notifications & Tools layer (`workspace`)

**Decision:** PharmaCore includes a first-class **workspace layer**: internal
communication (contextual comments, messaging, announcements, tasks, shift notes), a
full **notification pipeline** (events → rules → recipients → channels + preferences +
real-time), and **utility tools/calculators** (dosage, pricing/VAT, co-pay, conversions,
reorder, payroll). Delivered **incrementally** alongside the modules that feed it.

**Status:** Accepted (2026-08-03)

**Context:** Early discussion raised a productivity/collaboration layer ("Google-apps"
style). Only `notifications` (table) + the nav bell were captured; comms, notification
*handling*, and tools were not designed. They're needed for real daily operations.

**Consequences:**
- New module **`workspace`** (module 11) + design doc
  [10-collaboration-notifications-and-tools.md](10-collaboration-notifications-and-tools.md)
  + data-model tables (comments, conversations/messages, announcements, tasks, shift
  notes, notification preferences/deliveries, knowledge articles).
- Roadmap updated: **comments** land in Phase 2, the **notification pipeline** in Phase 4,
  the **full collaboration + tools** in Phase 6 — so Phase 1 scope is unchanged.
- Tools **reuse** authoritative engines (co-pay/PAYE/pricing/FEFO), never reimplement,
  so a calculator can't disagree with a real transaction.
- Open items: chat depth, drug-interaction dataset, real-time transport (Channels vs SSE),
  SMS scope.

## ADR-008 — Security & data-protection posture

**Decision:** Security is a **cross-cutting property of every module**, not a late phase.
We commit to: comprehensive **activity + access logging**, **rate limiting**, **deny-by-default
RBAC** with tenant + object scoping, **encryption in transit (TLS 1.3) and at rest
(AES-256)** plus **application-level field encryption** for the crown jewels (credentials,
national IDs, sensitive patient data) with keys in a **KMS**, an **encrypted device DB**
(SQLCipher), and platform hardening.

**Status:** Accepted (2026-08-03)

**Context:** The system handles medicine, money, patient data, and tax records — a breach
or unauthorized entry is unacceptable. A stakeholder asked specifically for full activity
logging, rate limiting, strong authN/authZ, data security, hardening, and "end-to-end
encryption."

**Key clarification — encryption:** true **zero-knowledge end-to-end encryption** (server
cannot read the data) is **incompatible with an ERP**: the server must search inventory,
adjudicate insurance, compute payroll, and report — it cannot operate on data it cannot
decrypt. We therefore **do not claim zero-knowledge E2E**. Instead we encrypt on **every
hop and at rest**, add **field-level encryption** for the most sensitive data, encrypt the
offline device DB, hold keys in a KMS, and pair this with strict access control + full
logging. This is the honest, achievable, correct posture.

**Consequences:**
- Foundational controls (rate limiting, security headers, security-event logging,
  field-level encryption) land in **Phase 1**, not Phase 7 (roadmap updated).
- Full detail + a hardening/go-live checklist: [08-security-and-compliance.md](08-security-and-compliance.md).
- Dependency/SAST scans become **required** CI checks once the runner is unblocked.

## Still open (deferred, not yet decided)

- Drug-interaction dataset: license clinical data vs. basic duplication check.
- Exact medicine **tax-class** mapping (A/B/C) — confirm with accountant/RRA.
- Which insurers to onboard *first* operationally (schema supports all; rollout order TBD).

---

## ADR-009 — Rwandan payroll compliance is data, not code (StatutoryRate engine)

**Decision:** PAYE bands, RSSB pension rates (and the 2025 → 2030 phased rises),
maternity, CBHI, occupational hazards, RAMA, VAT, WHT, and any future statutory
rate live in a single, **effective-dated, versioned** table (`StatutoryRate`). The
payroll engine, the statutory filing generator, and the Finance tax sub-ledger
read from this resolver; **no rate or band is hard-coded** in application logic.

**Status:** Accepted (2026-08-06)

**Context:** Rwanda 2025 doubled pension contributions from 6% to 12% (Presidential
Order N° 086/01, gazetted 13 Dec 2024) and set a phased rise to 20% by 2030. The
new income-tax framework (Organic Law N° 026/2024) revised PAYE bands for FY 2025.
Any change that requires a code deploy, a migration, or a hotfix is a bug. Compliance
must survive a Finance Law with zero code changes — only a new `StatutoryRate` row,
with its `source_url` for audit.

**Consequences:**
- New entity `StatutoryRate(code, valid_from, valid_to, params JSONB, source_url,
  published_by, status)` with a resolver service used by HR + Finance + Reporting.
- Publishing a new rate is **approval-gated** (Finance manager + Director), audit-logged,
  and visible in a timeline UI with diff between consecutive rows.
- 2025/26 seed data: PAYE bands per Organic Law N° 026/2024; pension 6%+6% per
  Presidential Order N° 086/01; maternity 0.3%+0.3% per Law N° 003/2016 amended by
  Law N° 049/2024; CBHI 0.5% on net per PM Order N° 034/01; occupational hazards 2%
  ER per Law N° 13/2009; RAMA 7.5%+7.5% on basic; VAT 18% class B.
- CBHI's base rule (0.5% on **net** after PAYE/RSSB/maternity) is encoded in the
  resolver as a `base_rule` string, not branched in code, so a future change (e.g.
  flat amount) is a single row update.
- Transport allowance is now in the contributory base — `SalaryComponent` carries a
  `contributory_to_pension` flag that drives the engine; no code branch on allowance type.
- Open data file: `docs/18-rwanda-integrations-and-statutory.md` is the source of truth
  for which rates to seed.

## ADR-010 — Domain events + outbox bus, not direct cross-app calls

**Decision:** HR ↔ Finance ↔ Distribution ↔ Inventory integrate through a **domain
event bus** backed by an `OutboxEvent` table and Django Signals; **no subsystem
imports another's models or services directly** for cross-cutting events.

**Status:** Accepted (2026-08-06)

**Context:** Direct Django-import integration between HR and Finance (the previous
implicit design) couples releases, makes tests brittle, blocks independent scaling
of workers, and prevents the same event from being observed by Reporting / Analytics
without code changes. A reliable, idempotent, auditable event bus is the standard
fix and matches the workspace's "single source of truth" principle.

**Consequences:**
- New entity `OutboxEvent(event_type, payload JSONB, occurred_at, status, retries)`;
  producers publish via `transaction.on_commit(lambda: outbox.publish(...))`;
  consumers register `subscribe(event_type, handler)` and must be **idempotent on
  `(event_type, source_doc_id, source_line_id)`**.
- First-class events: `SaleFinalised`, `PurchaseOrderApproved`, `GoodsReceivedNotePosted`,
  `InventoryAdjusted`, `StockDisposed`, `EmployeeHired`, `EmployeeTerminated`,
  `TimesheetApproved`, `PayrollRunApproved`, `PayslipPublished`, `StatutoryFilingGenerated`,
  `StatutoryPaymentConfirmed`, `CustomerInvoiceIssued`, `PaymentReceived`, `PaymentMade`,
  `CreditLimitChanged`, `CreditHoldEngaged`, `FiscalPeriodOpened`, `FiscalPeriodClosed`,
  `PeriodReopened`, `EODCloseFinalised`, `EOMCloseFinalised`, plus the full approval
  lifecycle (`ApprovalRequested`, `ApprovalClaimed`, `ApprovalGranted`, `ApprovalRejected`,
  `ApprovalEscalated`, `ApprovalSLABreached`).
- The outbox makes the HR → Finance payroll→GL→statutory-payment flow **observable
  end-to-end**: any stuck event is a row in `OutboxEvent` with a failure reason.
- Reporting / Insights subscribe to the same bus without coupling to any subsystem.
- ADR-001 (POS offline outbox) and ADR-008 (audit logging) both reuse this primitive.

## ADR-011 — Finance is double-entry from day one, driven by auto-posting

**Decision:** Finance uses a real **chart of accounts + double-entry journals** from
the first commit; every money- or compliance-moving domain event auto-posts a
journal through a `JournalPostingService`. Statutory sub-ledgers (PAYE, RSSB pension,
RSSB maternity, CBHI, occupational hazards, RAMA, VAT, WHT) are **first-class GL
accounts**, not side tables.

**Status:** Accepted (2026-08-06)

**Context:** The owner's question — *am I making money, who owes me, is cash safe* —
requires reports that reconcile to source events. Single-entry "append-only" ledgers
cannot produce a reliable balance sheet or trial balance. EBM/RRA reconciliation
also requires that posted liabilities equal the statutory filing amounts, which is
trivial when they share the same chart of accounts.

**Consequences:**
- New entities: `ChartOfAccounts`, `FiscalPeriod`, `PeriodClose`, `JournalEntry`,
  `JournalLine`, `JournalSource`. Seeded Rwanda-appropriate CoA with **2200-level
  statutory payable accounts** (`2200 PAYE Payable`, `2210 RSSB Pension Payable`,
  `2220 RSSB Maternity Payable`, `2230 CBHI Payable`, `2240 Occupational Hazards
  Payable`, `2250 RAMA Payable`, `2300 VAT Payable`, `2400 EBM Liability`,
  `2500 WHT Payable`).
- `JournalPostingService` dispatches per-source handlers (`SALE / PURCHASE / PAYROLL
  / INVENTORY_ADJ / MANUAL / OPENING_BALANCE / FX / DEPRECIATION / BANK_RECON /
  STATUTORY_PAYMENT`). All handlers are idempotent on `(source_doc, source_line)`.
- `FiscalPeriod.status ∈ {Open, SoftClosed, HardClosed}`; reopen requires audit-recorded
  reason. Reversal entries (not edits) are the only way to correct a HardClosed period.
- Cross-system invariants encoded at the model/service level:
  - A payroll run cannot be marked `FILED_PAID` unless its GL sub-ledger balance equals
    the filing amount.
  - An employee cannot be terminated while referenced by an open payroll run.
  - A `CreditProfile.on_hold = True` blocks new B2B orders in Distribution.
  - A HardClosed fiscal period rejects all postings except reversal entries.
- Inventory valuation (WAC vs FEFO-lot) is a `TenantSettings.costing_method`; lot-level
  cost drives COGS posting on `SaleFinalised`.
- EBM, MoMo, bank integrations live behind a `Provider` interface; **MockEbmProvider**
  and **MockMomoProvider** ship before real adapters (EBM OSDC certification is gated).

## ADR-012 — Approvals engine is the only path for sensitive actions

**Decision:** Every sensitive action across all subsystems — payroll run final
approval, salary revision, credit-limit change, AR/AP write-off, supplier bill
3-way-match variance, inventory write-off / disposal, period reopen, statutory rate
publish, credit hold engagement, user creation, claim resubmit, price override,
discount beyond threshold — routes through a single **Approvals engine** with a
**central inbox**, **claim-to-lock**, **no self-approval**, **SLA timers with
escalation**, and **senior oversight**. No subsystem reinvents approval.

**Status:** Accepted (2026-08-06)

**Context:** A standalone approval in each subsystem (HR approval, Finance approval,
Distribution approval) creates inconsistent UX, double-work, and hidden approvals.
The memory rule "central inbox, claim-to-lock, SLA timeout, escalation, senior
oversight" is a system property, not a per-module convention.

**Consequences:**
- `ApprovalRequest`, `ApprovalStep`, `ApprovalDecision`, `ApprovalDelegation`,
  `ApprovalSLATimer` are first-class data so the inbox is queryable, filterable,
  exportable, and auditable.
- Senior leaders (HQ exec, Finance director) see **all** pending approvals across
  branches and can **forward/reassign** — the "oversight" guarantee.
- Every approval is **e-signed** (actor + timestamp + immutable audit trail) and
  drives a downstream `Approval*` event on the outbox bus, so Finance and Reporting
  react without polling.
- The engine supports **multi-step / parallel** chains and **delegation while away**.
- Rule tables (who can approve what, by amount / branch / cost center) are seeded
  per role and overridable by tenant; sensitive approval rules (payroll final,
  AR write-off) are not overridable by tenant.

## ADR-013 — Payroll engine is a pure function over a StatutoryRate snapshot

**Decision:** The payroll engine computes a `Payslip` as `f(employee_inputs ×
StatutoryRate effective on period_end_date)`. It is **pure, deterministic, and
re-runnable**; once a run is `Locked`, the rate resolver, the attendance, the leave
balances, and the loan schedules for that period are frozen.

**Status:** Accepted (2026-08-06)

**Context:** Payroll errors cost real money and erode trust. A re-run with a
different rate set, or with attendance that changed mid-calculation, would produce
non-reproducible payslips and unreconcilable GL postings. The Labour Code (Art. 70)
allows daily / weekly / fortnightly / monthly pay periods — the engine must handle
all four without special-casing.

**Consequences:**
- The run lifecycle `Draft → Calculated → Approved → Paid → Locked` is enforced
  server-side; `Lock` snapshots `StatutoryRate` resolution, attendance, leave, and
  loans for the period into the run record.
- Any later change (correction, back-pay, arrears) is a new `PayrollAdjustment`
  in a future period, not a mutation of the locked run.
- Labour Code Art. 70 pay-period support is configurable per tenant (`TenantSettings.pay_period`)
  but defaults to **monthly** for full-time formal-sector staff.
- For monthly employees, the **15th of the following month** is the practical deadline
  driven by PAYE/RSSB remittance rather than a calendar day stated in the Code (the
  2009 7-working-day rule was removed in 2018). The engine surfaces statutory filing
  due dates on `StatutoryFiling.due_date` and the **Statutory Due** dashboard.
- Gross-to-net formula (Rwanda, versioned): see ROADMAP §10.3. CBHI's base is **net
  after PAYE/RSSB/maternity**; transport is **in the contributory base** for pension;
  RAMA is on **basic only** and only if the employer opts in (≥7 employees).
- End-to-end demo scenario lives in ROADMAP §10 to validate the engine against the
  Rwanda 2025/26 rates before Phase 9 begins.

## ADR-014 — Numbers, periods & opening balances are first-class

**Decision:** `NumberSequence`, `FiscalPeriod`, `PeriodClose`, `OpeningBalance`,
and `TenantSettings` are **first-class subsystems**, not ad-hoc utilities. They
are loaded before any tenant can transact.

**Status:** Accepted (2026-08-06)

**Context:** Numbering collisions, missing opening balances, ambiguous fiscal periods,
and tenant-specific defaults (costing method, pay period, FX provider) cause
post-go-live chaos that sinks rollouts. The previous roadmap had these scattered
across modules.

**Consequences:**
- `NumberSequence` is **gapless, monotonic, transactional**; the documents engine
  and the journal engine call `next_number(tenant, type)` under `SELECT … FOR UPDATE`.
- `FiscalPeriod` supports standard calendar (month) and retail (4-4-5) calendars;
  `Open → SoftClosed → HardClosed`; reopen requires approval + audit reason.
- `OpeningBalance` covers opening stock (batches + qty + valuation), opening AR/AP
  with aging preserved, opening GL trial balance, opening employee + leave balances.
  A migration wizard validates that sums tie out before committing.
- `TenantSettings` carries `costing_method ∈ {wac, fefo_lot}`, `currency`,
  `fx_provider`, `default_country='RW'`, `pay_period`, `statutory_remittance_day=15`,
  `pit_filing_deadline_month=3, day=31`.
