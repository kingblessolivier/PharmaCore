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
- **Distribution redesign — the wholesale marketplace** (see `docs/development/distribution-redesign-plan.md`, ADR-021):
  - **Storefront engine (`apps/distribution/marketplace.py`, `/api/distribution/storefront/`)**: a depot decides what to show. `is_published`, `offered_qty`, `buffer_qty`, `min_order_qty` and `customer_segment` existed as fields but governed nothing — ordering priced from `PharmacyProduct.wholesale_price` in inventory and consulted neither them nor stock. Availability is now `min(offered, free unexpired stock − buffer)`, enforced at order creation. A wholesaler can hold 5,000 units and publish 800, or hold stock and publish none; **the buyer-facing API never returns the depot's real holding**, because leaking it would defeat the point of withholding it. A published listing supersedes the inventory offer entirely; where none exists the inventory offer still stands, so depots that never adopted listings keep trading — now capped by physical stock.
  - **Demand-driven sourcing (`BackorderLine`, `apps/distribution/demand.py`, `/api/distribution/demand/`)**: a retail pharmacy can order what the wholesaler does not stock. Instead of refusing the line, the shortfall is captured with the reason it could not be met, aggregated across every pharmacy that asked, and converted into a `PurchaseRequisition` that hands off to the existing procurement flow (RFQ → quote → PO → import). Backorders carry the requisition that sourced them so the same demand is never sourced twice; arriving stock settles the oldest request first. Buyers who want goods-or-nothing can pass `allow_backorder: false`.
  - **Tender contracts wired**: `contract_price`, `total_committed_qty` and `drawn_qty` were read by no service. An awarded price now beats the list price at ordering, and committed volume is drawn down by what actually ships — not what was ordered, so a cancelled or short line no longer consumes a customer's contract.
  - **Customer returns engine (`CustomerReturnLine`, `apps/distribution/returns.py`)**: `credit_note_amount` was a number a human typed, with no lines, no restock and no document behind it. Returns now record what came back, an inspection that must account for every unit, restocking of accepted goods only, and a credit note issued for exactly what was restocked. Expired goods cannot be restocked; rejected units never re-enter saleable stock; approving twice cannot duplicate stock.
  - **Van sales (`VanStockMovement`, `/api/distribution/sales-reps/{id}/van/`)**: `VanStock` had no API and no service — a quantity nobody could account for. Loading now takes goods out of depot stock, selling reduces the van, and returning puts unsold units back, with an audit trail behind every change and a manifest that reports whether the van reconciles. Rep performance and commission are computed from real orders against `monthly_sales_target` and `commission_rate_pct`, which previously drove no calculation.
  - **Screens**: all twelve distribution navigation entries audited for whether they load and whether they are on the `DataGrid` + `RecordKit` standard. `InstitutionalTendersPage` rebuilt off a raw table, now surfacing contract drawdown and validity; the distribution overview rebuilt from a brochure of static descriptions into storefront health, outstanding demand and a needs-attention panel. `B2BOrderingPortalPage` rebuilt as a real storefront — it had been posting `supplier`/`lines`/`quantity_requested` to an API expecting `depot`/`items`/`quantity_ordered`, so it could never have placed an order. It now shows availability before committing and separates "shipping now" from "to be sourced" in the basket. New `DemandBoardPage`; `DepotListingsPage`, `CustomerReturnsPage` and `FieldSalesPage` rebuilt on `DataGrid` + `RecordKit`.

### Fixed
- **The depot could reserve and ship expired stock.** `_reserve_item` filtered only on `status=ACTIVE`, while retail's `_fefo_consume` refused anything past its expiry. Because FEFO sorts by expiry date, expired batches were not merely reachable but *preferred* — the till refused expired goods while the depot shipped them.
- **`?buyer=None` returned HTTP 500** on the availability endpoint: a stringified null reached the ORM and raised `ValueError`. An absent buyer now reads as absent; only genuine garbage is refused with 400.
- **Sourcing demand a second time crashed with `IntegrityError`.** `PurchaseRequisition.requisition_number` is unique with a blank default, so the first requisition was created with no number at all and the second collided on `""`. Numbers are now allocated through procurement's gapless sequence.
- **The Goods Received Notes screen never loaded anything.** Both `GrnPage` and the distribution overview called `/api/distribution/grn/`; the registered route is `/grns/`. The 404 was swallowed, so an empty grid was indistinguishable from "no GRNs yet".
- **`?status=` was silently ignored on B2B orders**, so the overview's "pending approval" tile was really the all-time order count. `status`, `payment_status`, `depot` and `retail` filters are now honoured, and an unknown status is refused with 400 rather than quietly returning everything — an ignored filter is worse than a rejected one, because the number looks plausible.
- **The unmet-demand headline did not match the button beneath it.** The summary added open and already-being-sourced demand into one figure, but sourcing only picks up open lines — so the board advertised 1,745 units and then raised a requisition for 35. Open and sourcing volumes are now reported separately and the tile is bound to the actionable one.
- **The B2B order builder showed prices and quantities the server would not honour**, reading `PharmacyProduct` directly and so bypassing the published quantity, the buffer held back, the minimum order and any awarded tender price. It now reads the storefront — the same authority the order is priced against.

### Added
- **Finance redesign — ledger spine & money map** (see `docs/development/finance-redesign-plan.md`):
  - **Cost centres (`CostCentre`, `/finance/cost-centres`)**: an analysis dimension on every journal line, as a tree of branches / departments / functions, so the ledger can answer "what did Kicukiro spend on rent" without inventing an account per branch. Journal entries also record a `source_module` (which part of the business produced the posting). A cost-centre P&L reports contribution per centre plus `tagged_pct` — how much of the P&L is actually coded, so the report states how far it can be trusted.
  - **Budgets rebuilt (`Budget` header + `BudgetLine`)**: account × cost centre × month, with annual lines pro-rating across a partial window, budget approval and locking, and variance signed correctly per account type (under-spending a cost is favourable; under-selling revenue is not). Spend with no budget now appears in the report.
  - **Month-end close checklist (`PeriodTask`)**: thirteen items — cut-off, stock count, provision, bank rec, till variance, AR/AP review, payroll, depreciation, accruals, VAT, trial balance — that block the close until done, or waived with a reason.
  - **Money map (`apps/finance/moneymap.py`, `/api/finance/operations/money-map`)**: a registry of all sixteen ways money moves through the business, each declaring its GL treatment and posting path. A test fails the build if any declared source has no wired implementation, and the map reports which wired sources posted nothing this period.
  - **Bank reconciliation (`BankStatement`, `BankStatementLine`, `ReconciliationMatch`, `/finance/reconciliation`)**: the bank's own lines are now stored and matched against the ledger's. CSV import (signed-amount or debit/credit exports, normalised to one sign convention) that refuses a statement whose opening + movements do not equal its closing balance; auto-matching on exact amount within a five-day window scored by reference overlap, which declines to guess when two ledger lines fit equally well; many-to-many manual matching for payment runs, where the signed total must equal the bank line exactly; posting unexplained lines straight from the statement, which is the only way bank charges and interest can enter the books; and a reconciliation statement ending in the unexplained difference. Signing off is refused while that difference is non-zero or any line is still unaccounted for.
  - **Accruals & prepayments (`RecurringSchedule`, `ScheduleRun`, `/api/finance/schedules/`)**: a cost is spread across the months it belongs to rather than landing in the month it was billed, so an annual insurance premium no longer wrecks one month and flatters eleven. Accruals post as reversing entries by default — in on the last day of the month, out on the first of the next — so the supplier invoice can be booked normally without double-counting; prepayments never reverse. The final period absorbs the rounding remainder so a schedule always fully releases its balance. Catching up posts each missed month to the month it belongs to.
  - **Every Finance screen rebuilt on the `DataGrid` + `RecordKit` standard** and the navigation regrouped from twenty flat entries into seven sections that name the work (Money in, Money out, Cash & bank, Ledger & close, Tax & compliance, Performance) rather than the database tables. New screens for cost centres, accruals & prepayments and bank reconciliation; chart of accounts gained classification editing; the journal shows cost centres and which part of the business produced each posting; fixed assets runs depreciation; periods & close carries the checklist; the Finance home shows the money map and close readiness. Statement layouts (P&L, balance sheet, cash flow, VAT return) stay as statements — those are not lists.
  - **Finance documents (`apps/finance/documents.py`, `/api/finance/documents/…`)**: the documents engine — numbered, SHA-256 hashed, QR-verifiable, write-once — was used by retail, distribution and procurement but never by finance. Seven new document types (debit note, statement of account, remittance advice, payment voucher, journal voucher, financial statements, VAT return) plus wiring for tax invoices, receipts and credit notes. Vouchers carry the amount in words. A customer disputing a balance can now be sent a statement; a supplier receiving a bulk payment gets a remittance advice telling them which invoices it settled.
  - **Generated documentation reference (`manage.py generate_docs`)**: `docs/reference/data-model.md` (160 entities) and `docs/reference/api.md` are emitted from the model registry and URL resolver, and `--check` runs in CI. The hand-written design docs (`02-data-model.md`, `07-api-design.md`) keep their intent role and point at the generated reference. Previously ~145 models and ~100 routes had no current reference anywhere.
  - **Charts across finance**: variance and plan-to-actual on budgets, revenue-to-net-profit waterfall and cost donut on the P&L, overdue-ranked bars on aging, still-to-release bars on accruals & prepayments — on the already-validated palette. The chart components existed but were used on a single screen.
  - **ADR-015 → ADR-020** recording the load-bearing decisions from the finance redesign.
  - **Multi-currency FX revaluation (IAS 21)**: `ExchangeRate` (effective-dated, never overwritten), `currency` / `amount_fc` / `exchange_rate` on journal lines, and `Account.is_monetary` to decide what gets restated. Open foreign monetary balances are retranslated at the closing rate with the difference posted to *7100 FX Gain / Loss*; inventory is deliberately excluded as non-monetary. An exposure report shows the position before anything posts, and refuses to guess when no rate has been published. New command surface under `/api/finance/operations/fx-exposure` and `…/fx-revaluation`.
  - **Unrealised profit on intercompany stock eliminated**: `InventoryBatch.origin_unit_cost` records what the selling group member paid, so consolidation can remove the margin on goods still sitting inside the group. Transfers made before the field existed are counted and reported as unmeasured rather than assumed to be zero-margin.
  - **New month-end command** `python manage.py run_month_end` (`--as-of`, `--organization`, `--dry-run`).

- **Retail Pharmacy & Advanced Point of Sale (POS) Engine (ROADMAP §6):**
  - **Prescription Lifecycle & Digital Refill Intake (`Prescription`, `PrescriptionsPage`)**: Digital prescription intake, prescriber licence verification, patient medication history, remaining refill counters, and automated refill-due notifications (`/retail/prescriptions`).
  - **Statutory Controlled-Drug Audit Logbook (`ControlledSubstanceRegister`, `ControlledSubstancesPage`)**: Statutory running balance ledger, witness sign-off capture, quarterly audit report generation, and receipt-to-dispensing trail for narcotics & controlled substances (`/retail/controlled-drugs`).
  - **POS Promotions, Coupons & Loyalty Discount Rules (`POSPromotion`, `PromotionsPage`)**: Seasonal campaigns, coupon redemption codes, BOGO bundles, percentage/flat discounts, and min-spend thresholds at POS checkout (`/retail/promotions`).
  - **Billable Pharmacy Clinical Services (`ClinicalService`, `ClinicalServiceRecord`, `ClinicalServicesPage`)**: Clinical service catalog (Vaccinations, Blood Pressure & Glucose Screenings, Consultations) with patient encounter notes, fee tracking, and billing integration (`/retail/clinical-services`).
  - **Frontend UI & App Shell**: Built interactive pages with creation modals and product dropdowns. Registered routes in `App.tsx` and added Retail subnavigation items in `AppShell.tsx`.
- **Advanced B2B Distribution & Route-to-Market Engine (ROADMAP §5):**
  - **Depot Offered Listings vs. Physical On-Hand Stock (`DepotProductListing`)**: Decoupled depot physical warehouse inventory (`on_hand`) from public retailer-facing offered quantities (`offered_qty`, `buffer_qty`, and custom listing prices). Receiving stock lands in on-hand without auto-publishing; depot managers explicitly control exposed inventory.
  - **Controlled Substance Compliance & Trading Partner Guard**: Trading partner pharmacy licence validation (Rwanda Board of Pharmacy / Rwanda FDA) prior to B2B order submission, auto-flagging suspicious order volume spikes (>3x average or restricted substances).
  - **Field Sales Reps & Route-to-Market (Van Sales / Pre-Sales)**: Sales rep profiles, territory beats, daily journey plans, call logs, van-stock sell-from-vehicle, and rep commission ledgers.
  - **Institutional & B2G Customer Tenders**: Awarded tender contract price locks, committed volume tracking, and scheduled call-off delivery schedules for hospitals and NGOs.
  - **Customer Returns & Account Statements**: Retailer return-to-depot requests with RFDA inspection verification, credit note issuance, and automated monthly B2B customer financial statement generation.
  - **Frontend UI & App Shell**: Built `DepotListingsPage.tsx` (`/distribution/listings`), `B2BOrderingPortalPage.tsx` (`/distribution/portal`), `FieldSalesPage.tsx` (`/distribution/sales-reps`), `InstitutionalTendersPage.tsx` (`/distribution/tenders`), and `CustomerReturnsPage.tsx` (`/distribution/returns`). Defined type interfaces in `types.ts` and updated subnavigation in `AppShell.tsx`.
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
- **Four finance document generators were broken or silently wrong on first release.** The credit note and receipt referenced fields that do not exist (`reason`, `received_by`) and raised; the VAT return guessed at the report's payload keys and rendered an empty return; the remittance advice showed the run's creation date rather than its disbursement date. All were masked by defensive `getattr`/`.get()` fallbacks used in place of reading the models. Fixed against the real fields, with a test for every generator.
- **Journal lines silently dropped their currency.** `currency`, `amount_fc` and `exchange_rate` were added to `JournalLine` but `post_journal` never wrote them, so every posting stayed in base currency and no foreign exposure could ever be detected.
- **Document generation could issue two numbered originals of the same thing.** `generate_document` allocated a fresh number on every call, so pressing "Statement" twice produced STMT-00001 and STMT-00002 for one period and burned a number out of a gapless sequence. It now takes an opt-in `reuse_existing`, which every finance document passes; it stays opt-in because a purchase order reissued after an amendment genuinely is a new document.
- **The frontend `ProfitAndLoss` type predated the statement-ladder rewrite**, missing depreciation, operating profit, finance cost and tax expense — every line between gross and net.
- **The budgets screen was broken by the model redesign.** It still posted `department` and `budgeted_amount` to an endpoint that now expects a budget header with lines, so creating a budget failed outright. Rebuilt on the new model.
- **Three fields the statements depend on had no API surface.** `Account.classification`, `JournalEntry.source_module` and `JournalLine.cost_centre` existed on the models but were missing from their serializers, so a misclassified account could not be corrected from any screen and the analysis dimension could not be set when posting a manual journal.
- **HQ consolidation double-counted internal trade.** `consolidated()` summed the branches, so a depot's sale to its own retail branch was counted as group revenue and the branch's purchase as group cost — the same goods twice on their way through one business. Invoices where both seller and buyer are inside the consolidation set are now eliminated from group revenue and cost, and the matching intercompany receivable and payable cancel. Profit on internally transferred goods still held in stock is not yet eliminated and is reported as a stated limitation rather than ignored.
- **Bank reconciliation reconciled the books against themselves.** `JournalLine.is_reconciled` was a boolean an operator ticked, with a free-text reference beside it; nothing modelled what the bank actually said. Agreeing the ledger with the ledger always succeeds, so the cases reconciliation exists to catch — a payment that left the account and never reached the books, a double posting, an unrecorded standing order — were undetectable in principle. There is now a real two-sided reconciliation.
- **Retail POS takings were all recorded as cash.** `post_sale_journal` debited *Cash on Hand* for the whole sale total regardless of how the customer paid, even though the POS records split tenders. Mobile-money and card takings therefore appeared in the cash drawer: every till counted short by the non-cash total, MoMo could not be reconciled, and card money that had not yet arrived was reported as cash. Sales now post per tender to *Cash*, *Mobile Money* and the new *1150 Card Settlement in Transit*; `settle_card_batch` clears transit to the bank and expenses the acquirer fee to *6150*.
- **Till over/short never reached the profit & loss.** `DrawerSession` computed and stored a cash variance that nothing ever posted, so cash losses were invisible in the accounts. Closing a drawer now posts the variance to *6160 Cash Over / Short*.
- **Depreciation was never posted.** The fixed-asset register held useful lives and salvage values but no depreciation run existed, so assets sat at cost until disposal and EBITDA's depreciation add-back was structurally zero. `run_depreciation` now charges straight-line monthly depreciation (*6500* / *1701*), capped at the depreciable amount and idempotent per month.
- **The IAS 2 expiry provision was reported but never posted.** Expiring stock stayed on the balance sheet at full cost while the dashboard showed a provision the accounts had never taken. `post_expiry_provision` now posts the movement between the required and carried provision to *1590*, and releases it when the stock sells.
- **Budget variance was unverifiable.** `Budget.actual_amount` was an editable column that nothing computed — a variance report whose actual was typed in by the person being measured. The column is removed; actuals come from posted journal lines, excluding reversals exactly as the statements do.
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
