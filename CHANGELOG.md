# Changelog

All notable changes to PharmaCore are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Sections used: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

<!--
Maintenance rules:
- Every PR that changes behavior adds a line under [Unreleased].
- On release, move [Unreleased] items into a new versioned section with the date,
  and reset [Unreleased] to empty section headers. (See docs/development/release-process.md)
- Write entries for humans: what changed and why it matters, not the commit hash.
-->

## [Unreleased]

### Added
- **Procurement & imports (ROADMAP §4) — new `apps/procurement` app, API + UI.** Closes the buy side end to end:
  - **Supplier master** — `SupplierProfile` (standing preferred→blacklisted, trade terms, banking, rolling scorecard), `SupplierLicence` with a **GDP qualification gate** (a missing, unverified or expired *required* licence blocks PO approval), `SupplierPriceAgreement` (effective-dated contract prices with volume breaks, MOQ, pack multiples) and `SupplierEvaluation` (delivery/quality scored from posted receipts, not self-reported).
  - **Requisitions → consolidated purchasing** — branches raise `PurchaseRequisition`, an approver signs it off through the **approvals engine** (claim-to-lock, no self-approval, SLA), then HQ consolidates several into one PO per supplier with the same product merged onto one line.
  - **RFQ & quote comparison** — `RequestForQuotation` → `SupplierQuote`; comparison table converts every quote to RWF so lead time, terms and supplier score are comparable; awarding raises the draft PO and declines the rest.
  - **Supplier purchase orders** — `PurchaseOrder` raise → approve (approvals engine) → send (PDF into the document vault) → partial receipt → close/cancel. Multi-currency + FX rate, Incoterms, payment terms, freight/charges/discount, line discount & VAT, drop-ship to a branch.
  - **Imports & landed cost** — `ImportConsignment` carries proforma, bill of lading/AWB, vessel, containers, ports, customs declaration, clearing agent and insurance; `LandedCostComponent` costs are allocated **by value or quantity** into each PO line's unit cost, with **recoverable import VAT excluded** so COGS isn't overstated.
  - **Goods receipt against the PO** — `GoodsReceipt` captures batch and expiry (mandatory), records over/under delivery and rejections, refuses expired stock, and posts into inventory with the batches **quarantined pending QC**; GRN document generated; `Dr Inventory / Cr GRNI` journal.
  - **Supplier invoices (AP) & 3-way match** — `SupplierInvoice` reconciles PO ↔ GRN ↔ invoice per line with configurable qty/price tolerances; a variance can only be submitted with an **audited override reason**; approval creates the `finance.SupplierBill` and posts `Dr GRNI + Dr VAT input / Cr AP`. `SupplierNote` (debit/credit) adjusts the payable and reverses cost; a **statement of account** reconciles invoices, notes and payments.
  - **RBAC** — new `PROCUREMENT_OFFICER` role and `procurement.view / manage / receive / invoice` permissions (approving stays with `approval.decide`, so no-self-approval still holds).
  - **UI** — a new **Procurement** app tile and side nav with eight screens (overview, requisitions, RFQ & quotes, purchase orders, imports & landed cost, goods receipts, supplier invoices, supplier master), built on the enterprise `DataGrid` plus a shared drawer/line-editor kit; every document is create/read/update/act in one place.
- **HR (People) + Finance global design — spec only, no code yet.** Major additions to the [ROADMAP](ROADMAP.md) and to [docs/01-key-decisions.md](docs/01-key-decisions.md):
  - **Statutory rates engine** — versioned, effective-dated `StatutoryRate` table owns PAYE bands (0/10/20/30%), RSSB pension (6%+6% in 2025, phased to 10%+10% by 2030), maternity 0.3%+0.3% (gross excl. transport), CBHI 0.5% on net (per PM Order N° 034/01), occupational hazards 2% ER, RAMA 7.5%+7.5% on basic, VAT 18%, WHT. Rwanda compliance becomes **data, not code** — a new Finance Law = one new row with `source_url`, no deploy.
  - **Domain event bus (`OutboxEvent`)** — HR ↔ Finance ↔ Distribution ↔ Inventory integrate through a transactional outbox + Django Signals; idempotent on `(event_type, source_doc_id, source_line_id)`. First-class events listed (ADR-010).
  - **People (HR & payroll) design** — full entity list (Employee/Contract/SalaryStructure/Attendance/Timesheet/Shift/Leave/Loan/PayrollRun/Payslip/StatutoryFiling/Licence/CPD/Competency), gross→net formula versioned by `StatutoryRate`, run lifecycle `Draft → Calculated → Approved → Paid → Locked`, end-to-end dataflows including the `PayrollRunApproved → JournalPostingService → STATUTORY_PAYMENT` chain (ROADMAP §10).
  - **Finance design** — full entity list (CoA/FiscalPeriod/PeriodClose/Journal/Invoice/Payment/BankAccount/BankReconciliation/MoMoTransaction/TaxRecord/EBMReceipt/FixedAsset/Budget/CostCenter), Rwanda-appropriate CoA with **2200-level statutory payable accounts**, `JournalPostingService` with idempotent per-source `PostingHandler`, AR + credit profile + dunning, AP + 3-way match, statutory filing generation, period close, HQ consolidation (ROADMAP §9).
  - **Subsystem integration map** — ASCII diagram + numbered end-to-end flows + cross-system invariants (ROADMAP "Subsystem integration & event flows").
  - **Cross-cutting engines** added as named sections: StatutoryRate (C), OutboxEvent bus (D), NumberSequence/FiscalPeriod/OpeningBalance/TenantSettings (E).
  - **Master data & core entities** expanded with the full HR + Finance entity lists plus `OutboxEvent` and the approval engine's first-class data (ROADMAP "Master data & core entities").
  - **Phase 8 & Phase 9** split into ordered sub-phases with explicit cross-cutting engine dependencies (ROADMAP "Delivery phases").
  - **7 new ADRs** in `docs/01-key-decisions.md`: ADR-009 (StatutoryRate data-not-code), ADR-010 (Outbox event bus), ADR-011 (double-entry + auto-posting + statutory sub-ledgers), ADR-012 (single approvals engine), ADR-013 (payroll engine as pure function), ADR-014 (Numbers/Periods/OpeningBalances first-class), and the cross-system invariants they each entail.
- **B2B Wholesale Distribution & Automated Stock Transfers (Subsystem #4).** Added B2B Purchase Orders (`StockOrder`, `OrderItem`), 1-click FEFO depot approval and stock reservation (`approve_and_allocate`), live driver delivery notes and packing manifests (`Shipment`, `ShipmentItem`), zero-ghost-stock in-transit ledger (`InTransitStock`), 1-click retail receiving and Goods Received Notes (`GoodsReceivedNote`, `GRNLine`, `receive_all`), automated retail catalog and inventory batch landing (`receive_intake`), and B2B settlement recording (`OrderPayment`, `record_order_payment`) with financial journal postings. Built dedicated UI pages (`DistributionHome.tsx`, `PurchaseOrdersPage.tsx`, `GrnPage.tsx`, `InTransitPage.tsx`) and registered `/distribution/*` navigation routing.
- **Inventory & Warehouse Operations (Subsystem #3).** Added Good Distribution Practice (GDP) climate storage zones (`StorageZone`: Ambient, Cold Room 2–8°C, Freezer -20°C, Controlled Safe) and bin locations (`BinLocation`: Aisle, Shelf, Bin Code), cold-chain environmental sensor logging and excursion status (`TemperatureSensor`, `TemperatureLog`: Normal, Warning, Critical Breach), inbound quality control quarantine hold queue (`QualityCheck`) with `pass_qc` (releases batch to sellable stock) and `fail_qc` (quarantines batch) custom DRF actions, emergency batch recall directory (`BatchRecall`) with 1-click multi-branch `execute_freeze` engine, physical stock audit sessions (`StockCount`, `StockCountItem`: Cycle Count, Full Physical, Spot Check) with `approve_count` auto-reconciling variances into `StockMovement` ledger adjustments, and expired/damaged stock disposal write-offs (`StockDisposal`) with mandatory dual-witness sign-offs and destruction certificates (`DESTROYED`). Built dedicated UI pages (`InventoryHome.tsx`, `StorageZonesPage.tsx`, `TemperatureLogsPage.tsx`, `QualityControlPage.tsx`, `BatchRecallsPage.tsx`, `StockCountsPage.tsx`, `StockDisposalPage.tsx`) and registered full navigation routing.
- **Catalog Management & Global Formulary (Subsystem #2).** Added multi-tier price lists (`PriceList`: Wholesale, Retail, Contract, Promotional with effective dates and volume breaks), insurer formularies (`FormularyItem`: RSSB/CBHI/MMI reimbursement, co-pay %, prior auth), drug-drug interaction matrix (`ProductInteraction`: Minor, Moderate, Major severity and clinical management), UoM package conversions (`ProductUomConversion`), generic substitutes (`ProductSubstitute`), manufacturers directory (`Manufacturer`), INN active ingredients (`ActiveIngredient`), low-stock alert list (`LowStockPage.tsx`), expiry forecast page (`ExpiryPage.tsx`), and an Executive Catalog Dashboard (`CatalogHome.tsx`) with live KPI counters, operational widgets, and 10 module directory cards.
- **API keys / service accounts (Admin).** Machine/integration requests can authenticate
  with an `X-API-Key` header that acts **as a chosen user** (reusing that user's roles &
  pharmacy). Keys are hashed at rest (raw key shown once), admin-managed, org-scoped, and
  revocable; create/revoke are audited. Managed from an **API keys** panel on the Admin home.
- **Force-logout / session revocation (Admin).** An admin can end all of a user's
  sessions instantly — a token-version stamped on every JWT is bumped, so all their
  outstanding access **and** refresh tokens are rejected at once (audited); a
  **Force logout** action was added to the Users page. Tokens issued before the
  feature are grandfathered until they expire.
- **Admin oversight analytics.** The audit-log explorer gains a **per-branch filter**
  and a **CSV export** (respecting the active filters), plus **per-user and per-branch
  performance** endpoints (sales rung, items dispensed, returns, voids, logins; branch
  headcount) surfaced as a KPI strip in the user-activity view.
- **Password controls (Admin).** Admins can **reset a user's password** (forcing a
  change on next sign-in), users can **change their own** password, both **strength-
  validated** and audited; `/api/auth/me` exposes `must_change_password`. A **Reset pw**
  action was added to the Users page.
- **Per-tenant org settings (Admin).** Each organization now has a **subscription plan**
  (Basic / Standard / Premium / Enterprise), a **brand colour**, and **feature toggles**
  (online store, insurance, loyalty, B2B portal, offline POS), managed by an admin via
  an org **Settings** modal (audited).
- **Organisation onboarding & activation gate (Admin).** Capture and **verify** an
  org's compliance documents (Rwanda FDA / NPC / RDB / RRA / tax clearance), an
  onboarding **status** (draft → pending → active → suspended) with **activate / suspend**
  actions that gate whether the pharmacy can trade — admin-gated, org-scoped, audited,
  with an **Onboarding** modal on the Organizations page.
- **User identity documents (Admin).** Capture and **verify** identity documents on a
  user account (`UserDocument`: national ID, passport, professional licence, contract) —
  admin-gated, org-scoped, audited, with a **Documents** modal on the Users page (add /
  verify / delete). Distinct from HR employment documents.
- **Permission matrix (Admin).** Permissions are now `resource × action` (23-code
  catalogue); roles are **bundles of permissions** (seeded for every role);
  `User.has_permission()` + a `HasPermission.require()` DRF class + a `can()` frontend
  helper; `/api/auth/me` returns the user's permission codes. A **SYS-ADMIN-editable
  matrix UI** (roles × permissions grid, audited) lets you reshape what each role may do.
- **App homes + app-switcher springboard (workspace layout).** A top-left waffle
  opens a grid of subsystem tiles (Oracle-Fusion / Google-Workspace pattern); each
  built app opens its **home page** showing what's inside it — starting with the
  **Admin home** (stat strip + section cards for Organizations & branches, Users,
  Departments, Audit log).

### Changed
- **Finance: sales, inventory variances, and writeoffs now auto-post to the GL.** A completed POS sale produces two balanced journal entries — Dr Cash & Bank / Cr Sales Revenue + VAT Output, then Dr COGS / Cr Inventory at the FEFO batch's `wholesale_cost`. Approved stock-count variances post Dr/COGS / Cr/Inventory at the variance amount. `log_wastage` posts Dr Inventory Adjustment / Cr Inventory at the batch's cost. **Result: the leader's performance cockpit now reflects the day's revenue, COGS, and gross margin in real time** instead of staying empty until someone hand-posts a journal. Three new control accounts (`1200 Inventory on Hand`, `2050 VAT Output`, `2500 Inventory Adjustment Expense`) are auto-vivified by `seed_finance` / `ensure_default_accounts`.
- **Finance home + People home now expose operational KPIs.** Finance home adds a **period switcher** (this month / last month / quarter / YTD / custom) and tiles for **Cash on hand**, **Payroll liability**, **Inventory value**, **Stock turns** (annualised), and **GMROI** (gross-margin % × stock turns). People home adds tiles for **On leave today**, **Pending leave requests**, **Rostered today** plus quick-action shortcuts to clock-in/out, leave, payroll, roster, and the central approvals inbox.

### Added
- **HR data foundations.** `User` gains `tin` (RRA TIN), `payroll_email`, and `reports_to` (self-FK for org charts / supervisor links). `Employee` gains `gender`, `dob`, `photo`, `probation_end`, `contract_end`, `pay_group`, `pay_frequency`, `tin`, and `supervisor`. Migration `0017_iam` / `0007_hr_employee_extended_fields` apply the schema; existing rows pick up defaults.
- **HR and Finance seed commands (idempotent).** `python manage.py seed_finance` guarantees the standard 15-account CoA for every active org; `seed_statutory_rates` adds the OCCUPATIONAL_HAZARD 2% row plus the 2027 phased-pension rows; `seed_departments` guarantees FINANCE + HR departments per org.
- **Inventory valuation report.** `GET /api/finance/reports/inventory-valuation/` returns on-hand × wholesale cost broken down by product, plus the total — powers the inventory-valuation tab on the statements page and the Finance home KPI.
- **HR self-service data (LeaveRequest / AttendanceLog / ShiftRoster).** New endpoints `/api/hr/leave/`, `/api/hr/attendance/`, `/api/hr/roster/` (read + request/approve flows) — surfaced in the People home tiles, on the new `LeavePage`, `AttendancePage`, and `ShiftRosterPage`, and on the EmployeeDetail tabs.
- **Domain event bus + first-class Finance/HR infrastructure (F1 + F4, ROADMAP §D/§E).** Cross-subsystem integration now flows through a transactional outbox instead of direct function calls, and three long-promised first-class data primitives land.
  - **`apps/events` — OutboxEvent + dispatcher (F1.1, F1.3, F1.4).** New `OutboxEvent` table with a unique idempotency key on `(event_type, source_doc_type, source_doc_id, source_line_id)` (ADR-011). `outbox.publish()` defers via `transaction.on_commit` so a rolled-back business transaction never produces a phantom event. In-process `subscribe(event_type, handler)` registry (explicit, greppable). `run_outbox_dispatcher` management command claims pending rows with `SELECT … FOR UPDATE SKIP LOCKED`, dispatches to handlers, retries with exponential backoff, marks DEAD after `MAX_RETRIES=8`. First-class events emitted: `SALE_FINALISED`, `PURCHASE_ORDER_APPROVED`, `GOODS_RECEIVED_NOTE_POSTED`, `INVENTORY_ADJUSTED`, `STOCK_DISPOSED`, `STOCK_ORDER_APPROVED/SHIPPED/RECEIVED`, `CUSTOMER_INVOICE_ISSUED`, `PAYMENT_RECEIVED`, `CREDIT_LIMIT_CHANGED`, `CREDIT_HOLD_ENGAGED`, `SUPPLIER_BILL_APPROVED`, `PAYMENT_MADE`, `EMPLOYEE_HIRED/TERMINATED`, `TIMESHEET_APPROVED`, `PAYROLL_RUN_APPROVED`, `PAYSLIP_PUBLISHED`, `STATUTORY_FILING_GENERATED`, `STATUTORY_PAYMENT_CONFIRMED`, `FISCAL_PERIOD_OPENED/CLOSED`, `PERIOD_REOPENED`, `EOD_CLOSE_FINALISED`, `EOM_CLOSE_FINALISED`, `APPROVAL_REQUESTED/CLAIMED/GRANTED/REJECTED/RETURNED/ESCALATED/SLA_BREACHED`.
  - **`post_journal` is now idempotent on `(org, reference_type, reference_id)` (F1.2).** A re-run with the same source-doc tuple returns the existing posted entry instead of creating a duplicate; the protection is enforced by a conditional `UniqueConstraint` (`reference_type != ""`) so manual / adjustment postings (which legitimately share an empty reference) still work.
  - **First events wired (F1.3).** Sale finalisation in `apps.retail.services.complete_sale` publishes `SALE_FINALISED`; approval requests + decisions in `apps.approvals.services` publish `APPROVAL_REQUESTED` / `APPROVAL_DECIDED`. Each publish is `transaction.on_commit`-wrapped; replays are safe end-to-end.
  - **`NumberSequence` extended with `Domain` (F4.1, ADR-014).** Adds `PROCUREMENT / FINANCE / HR / INVENTORY / DISTRIBUTION / RETAIL / DOCUMENT` and widens the unique constraint to `(org, domain, kind, year)`. New kinds for Finance (`CUSTOMER_INVOICE`, `CUSTOMER_RECEIPT`, `JOURNAL_ENTRY`, `PAYROLL_RUN`, `STATUTORY_FILING`) and HR (`PAYSLIP`, `EMPLOYEE`, `LOAN_ADVANCE`).
  - **`apps/core/sequences.py` — `next_number()` helper (F4.2).** Single gapless numbering primitive every module calls. Wraps the existing `SELECT … FOR UPDATE` claim; `next_document_number(...)` formats as `PO-2026-00042` etc. Tests cover monotonic increasing, transactional rollback (the number returns to the pool on rollback), 10-thread concurrency, and per-(org, domain, kind, year) isolation.
  - **`TenantSettings` model + lazy `tenant_settings_for()` (F4.3, ADR-014).** Per-tenant configuration as data, not code: costing method (WAC / FEFO_LOT), base currency, FX provider, pay period (daily/weekly/fortnightly/monthly), statutory remittance day, PIT filing deadline (month/day), default country, timezone. One row per organization via `OneToOneField`; lazily created the first time any module asks for one.
  - **`OpeningBalance` import for onboarding + legacy migration (F4.4).** Single typed row per import line: `GL_TRIAL_BALANCE`, `AR_AGING`, `AP_AGING`, `STOCK_BATCH`, `EMPLOYEE_LEAVE`. `import_opening_balances` service validates per-kind tie-outs (trial balance must balance, partners / products / employees must exist, no duplicate keys) **before** any row is written — a failed import leaves the table untouched. `import_opening_balances <file.json>` management command reads `{organization, rows}` from JSON; with `--apply` it writes the GL opening journal and creates inventory batches / leave balances in the same transaction.

### Fixed
- **Performance cockpit was blind without sales posting.** Before this slice, the P&L was always empty because nothing auto-posted to the GL. Sales, inventory variances, and writeoffs now feed the ledger so `performance()` reports the business as it happens.
- **Admin pages are now route-guarded.** Non-admins could reach admin pages
  (`/admin`, `/companies`, `/users`, …) by typing the URL even though the nav hid
  them; a `RequireRoles` guard now bounces them to the dashboard — matching what the
  nav already enforces. (Data was already API-scoped; this closes the UI hole.)

### Added (earlier)
- **Company ↔ branch split (Admin).** A first-class `Company` above `Organization`:
  a company owns one or more branch organizations (a solo pharmacy = one company with
  one branch; a chain = a company with an HQ + branches). Company CRUD (admin-gated,
  audited, scoped), attach/detach organizations, and **HQ-of-company visibility** (an
  HQ user sees every branch in their company; a branch sees itself). Organizations may
  still stand alone with no company. New admin **Companies** page.
- **Retail cash-drawer / till sessions (Phase 3).** Open a drawer with a float, ring
  up sales against it, and **cash up** at close — the register computes **expected
  cash** (float + cash taken − change given − cash refunds) and the **over/short**.
  X/Z report endpoint, one open drawer per cashier, opener/admin-only close, audited.
  POS shows a till-status bar with live expected cash and a cash-up flow.
- **Admin oversight foundation.** Sign in with a **PF/staff number** (not just a
  username); **view-as / impersonation** so an admin can enter any user's session to
  see exactly what they see and do (banner-flagged in the UI, fully audited, blocked
  for self / other admins / out-of-scope users); **per-user activity** (recent audit
  trail + action counts + last login); and an **Activity & logs explorer** with
  filters (user / action / entity / date). New admin **Users** and **Activity** pages.
- Full system analysis & design documentation set (`docs/`): research findings,
  key decisions (ADRs), data model, SRS, use cases, architecture, workflows/state
  machines, API design, security & compliance.
- Design system documentation (`docs/design/`): principles, tokens, brand & logo
  system, iconography, navigation, single-page workflow, components, overlays,
  document design & authenticity, dashboards & charts (validated colour-blind-safe
  palette), motion, UX writing & terminology. Two visual references (app shell,
  dashboard).
- Development process docs (`docs/development/`, root governance files, `.github/`
  templates): git workflow, coding standards, testing strategy, CI/CD, release
  process, environments, definition of done, onboarding, ADR process; ROADMAP,
  CONTRIBUTING, SECURITY, CODE_OF_CONDUCT.

- **Phase 0 scaffolding:** Django + Django REST Framework backend skeleton (settings,
  health endpoint, tests, ruff/black/mypy/pytest-django, docker-compose, Django
  migrations); React + TypeScript + Vite frontend wired to the design tokens (Tailwind);
  GitHub Actions CI running backend and frontend checks.
- **Phase 0 auth/audit/RBAC (`iam` app):** custom `User` model, JWT login via
  djangorestframework-simplejwt (`/api/auth/login`, `/refresh`, `/me`), argon2 hashing; base RBAC
  (`Role` + `HasRole` permission, roles seeded); append-only `AuditLog` with
  model-level immutability. **Phase 0 complete.**

- **Phase 1 complete** — Core data + design-system UI (19 PRs). Identity (orgs,
  departments, users & roles, licences, tenant scoping, audit), Catalog (products,
  ingredients, suppliers, barcodes), Inventory (batch stock, **immutable movement
  ledger**, **FEFO**, intake, adjustments, wastage), per-pharmacy catalog/pricing, and
  org-scoped activity logs — surfaced through a pharmacy **Manage** console (Details ·
  Users & roles · Catalog & pricing · Stock · Licences · Activity logs). Frontend:
  app shell, component library, command palette (⌘K), org switcher. Security: rate
  limiting, CSP + security headers, prod hardening, login-failure logging. 60 backend
  tests pass. **Exit criterion met:** stock received/counted/viewed at batch level with
  FEFO in the UI.

- **Phase 2 complete** — Distribution & Documents. B2B purchase orders (retail→depot),
  depot approval with **FEFO batch allocation/reservation**, picking & dispatch
  (`TRANSFER_OUT`), **GRN reception** (`TRANSFER_IN` into the retail FEFO ledger) with
  discrepancies, a **PDF document engine** (gapless numbering, SHA-256 hashing, QR
  verification, immutable vault: PO/GRN/invoice), and a **workspace** layer (contextual
  comments + @mention notifications with an in-app bell). New apps: `distribution`,
  `documents`, `workspace`. 81 backend tests pass. **Exit:** a full order→approve→dispatch→
  receive cycle runs in the UI and produces immutable, verifiable documents.

### Changed
- UI scope set to **English only** (ADR-004); removed the bilingual/Kinyarwanda plan.
- Project renamed: **PharmaCore** (platform) by **Medlink** (company) — ADR-005.
- Backend framework: **Django + DRF** (ADR-006, chosen over FastAPI before code existed).
- Backend framework changed from FastAPI to **Django + Django REST Framework** — ADR-006.

### Notes
- No application code yet — the project is in the design/documentation phase by
  decision. The first code lands in Phase 0 (see [ROADMAP](ROADMAP.md)).

---

## [0.0.0] — 2026-08-03
### Added
- Project inception: repository and documentation foundation for PharmaCore, a unified
  pharmaceutical ERP for Rwanda (wholesale distribution + retail POS + compliance +
  HR/finance).

[Unreleased]: https://example.com/pharmacore/compare/v0.0.0...HEAD
[0.0.0]: https://example.com/pharmacore/releases/tag/v0.0.0
