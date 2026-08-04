# PharmaCore — Roadmap

Phased, dependency-ordered delivery. We build **foundation-first**: every phase ships
something usable end-to-end and is a prerequisite for the next. Dates are relative —
the *order* is the commitment.

**A phase is ✅ only when it is complete across all layers** — **backend + frontend/UI +
design + tests + docs** — per the [Definition of Done](docs/development/definition-of-done.md).
"Done" never means "backend done, UI later." If a checkbox below is unticked, the phase
is not complete.

Legend: ✅ done · 🚧 in progress · ⬜ planned · every phase implicitly includes tests
(unit→integration→e2e) and doc updates.

---

## Phase 0 — Foundations & scaffolding  ✅
Repo, tooling, and the walking skeleton everything else stands on.
- [x] Repo init, branch protection (staging/main), GitHub Actions CI (lint→type→test→build)
- [x] **Backend** scaffold (Django + DRF, ORM + migrations), docker-compose (Postgres/Redis/MinIO)
- [x] **Frontend** scaffold (React + TS + Vite), **design tokens wired into Tailwind**
- [x] Auth: JWT login (simplejwt), argon2 hashing, custom `User`, `/api/auth/me`
- [x] `audit_log` (append-only) + base RBAC (`Role` + `HasRole`); roles seeded
**Exit:** ✅ a user can log in; CI green locally; migrations run clean.
> Note: GitHub Actions runners are blocked at the account level (email verification) —
> code is verified green locally. Making CI checks *required* on merge is pending that fix.

## Phase 1 — Core data + Design-system implementation  ✅
The data foundation every module reads from, **and** the reusable UI it's rendered with.
**Backend**
- [x] Identity: organizations (depot/retail/HQ), departments, user↔org/department scoping, licenses
      *(role-based RBAC kept as the permission model; a separate per-permission table was intentionally not added — see ADR note)*
- [x] Catalog: product master (ATC/GTIN/tax class), ingredients, manufacturers, suppliers, barcodes
- [x] Inventory: batch inventory, `stock_movements` (immutable ledger), FEFO queries
- [x] Supplier intake, stock adjustments, wastage, expiry alerts; DRF endpoints + OpenAPI
**Frontend / UI**
- [x] **App shell**: top nav, side nav, **org/branch switcher**, **command palette (⌘K)**
- [x] **Component library**: buttons, inputs/forms, tables, cards, badges, tabs, modals, toasts, empty/loading/error states
- [x] Auth screens (login, profile); Admin: organizations, users & roles, departments, licences
      (in the pharmacy **Manage** console: Details · Users & roles · Catalog & pricing · Stock · Licences · Activity logs)
- [x] Catalog UI (product list/detail, ingredients, barcodes); Inventory UI (batch stock-on-hand,
      supplier intake, FEFO/expiry, adjustments, wastage)
**Design**
- [x] Tokens in code (light/dark), lucide iconography, accessibility baseline (visible focus, reduced-motion)
**Security (foundational)**
- [x] Rate limiting (API throttles), security headers + HSTS + CSP, CORS lockdown, `check --deploy` (security) clean
- [x] Security-event logging (login failures)
- [ ] **Field-level encryption** — *deferred to Phase 4/5*: its target fields (national IDs,
      EBM/insurer credentials) don't exist until those phases; adding crypto now would be unused scaffolding.
**Exit:** ✅ stock can be received, counted, and viewed at batch level with FEFO **in the UI**.
> **Phase 1 complete.** 55+ backend tests green; frontend lint/typecheck/build green. 19 PRs merged.
> (GitHub Actions runners remain blocked at the account level — code verified green locally.)

## Phase 2 — Distribution & Documents (B2B)  ✅
Depot→retail transfer with the paperwork.
**Backend**
- [x] Purchase orders → depot approval/**FEFO allocation** (batch reserve) → picking → dispatch
- [x] GRN reception (the stock write-event: `TRANSFER_OUT` at depot → `TRANSFER_IN` at retail) + discrepancies
- [x] Document engine: PDF renderer, gapless sequences, SHA-256 hashing, vault, QR verify
- [x] Templates: PO, GRN, invoice
**Frontend / UI**
- [x] PO create/cart, approvals & allocation, dispatch, GRN reception checklist (counts vs manifest)
- [x] **Document vault + viewer**
**Workspace (first slice)**
- [x] Contextual **comments** on orders + **@mention notifications** (bell + notification centre)
**Exit:** ✅ a full order → approve → dispatch → receive cycle runs in the UI, produces immutable,
verifiable documents, and moves stock into the retail FEFO ledger.
> **Phase 2 complete.** 81 backend tests green; frontend green. PRs #22–#27.
> (Multi-stop shipments, packing slip/waybill/credit-note templates, and email/SMS notification
> channels are folded forward — the depot→retail cycle + core documents are done.)
> **Flow streamlined (post-Phase 2):** the buyer places an order (one step), the depot
> **approves** (stock ships in the same action), and the pharmacy **receives** in one click —
> which lands the stock *and auto-lists the product in its catalog* (no re-adding). The separate
> picking / driver-capture / per-item-count steps were removed as unnecessary ceremony. Delivery
> note, GRN, and tax invoice are still generated automatically underneath.

## Phase 3 — Retail POS + Offline + Desktop app  🚧
The counter, built offline-first (ADR-001). The hardest phase.
**Backend**
- [x] Sale state machine (OPEN → COMPLETED → VOIDED), split-tender payments, FEFO stock
      consumption (immutable `SALE` ledger), void reversal (`RETURN`), fiscal **receipt** doc
- [x] Retail pricing pulled from the pharmacy's own listing (server-authoritative)
- [ ] Cash-drawer sessions, prescriptions + dispensing gate
- [ ] **Sync API** (outbox push, delta pull, oversell reconciliation/conflicts)
**Frontend / UI**
- [x] POS single-page workflow: manual search → FEFO auto-pick → cart → payment → change → receipt
- [ ] Split-payment UI, drawer open/close & reconciliation, prescription attach/verify, dispensing labels
**Desktop (Tauri)**
- [ ] Tauri shell wrapping the React app + **encrypted local SQLite**, offline sync engine,
      thermal-printer support, signed auto-update
**Tools**
- [ ] POS calculators: pricing/markup, VAT (tax class), cash & change
**Exit:** a sale completes with the internet off and reconciles correctly on reconnect — in the desktop POS.
> **Slice P3.1 done** (online POS sale core): ring up → FEFO deduct → pay → receipt + void,
> 9 tests. 91 backend tests green; frontend green. Offline/Tauri, drawer, and prescriptions
> are the remaining slices.

## Phase 4 — Insurance & EBM + Notification pipeline  ⬜
Multi-insurer claims (ADR-002) + fiscalization (ADR-003).
**Backend**
- [ ] Insurance schemes, org agreements, formulary; co-pay computation
- [ ] Claims queue, adjudication, manifests, receivables aging
- [ ] `EbmProvider` abstraction + MockEbmProvider; async fiscalization + retry; EBM receipts; purchase registration
**Frontend / UI**
- [ ] "Route via insurance" at POS; claims queue + adjudication; manifests; receivables aging; EBM error/retry queue
**Workspace**
- [ ] **Notification pipeline** (events→rules→recipients→channels), **preferences**, **in-app real-time bell**
- [ ] Co-pay calculator (reuses the sale engine)
**Exit:** an insured, fiscalized sale flows end-to-end vs the mock provider in the UI; EBM errors surface for retry; notifications fire.

## Phase 5 — People / HR & Payroll  ⬜
**Backend**
- [ ] Employees, licenses (dispensing-rights link), attendance, shifts, leave
- [ ] `statutory_rates` config (PAYE/RSSB), payroll runs/records, payslips, bank/momo remittance file
**Frontend / UI**
- [ ] Employees, attendance & shifts, leave approvals, **payroll run wizard**, payslips, license-expiry compliance
**Tools**
- [ ] Payroll / PAYE-RSSB what-if calculator
**Exit:** a monthly payroll run computes correct net pay with current Rwanda rates and generates payslips — in the UI.

## Phase 6 — Finance, Reporting & Collaboration  ⬜
**Backend**
- [ ] Chart of accounts, balanced immutable journals + auto-posting from ops, fiscal periods, receivables, expenses
- [ ] `daily_snapshots`, operational report queries; email/SMS notification channels wired
**Frontend / UI**
- [ ] Accounting screens; **role dashboards** (KPI cards + charts, validated palette — design 09);
      operational reports; **EOD closeout wizard**; **notification center + preferences screen**
**Workspace (full)**
- [ ] Direct/department **messaging**, **announcements**, **tasks**, **shift notes**, **knowledge base/SOPs**
- [ ] Remaining **tools/calculators** (dosage, conversions, reorder/EOQ, aging); email/SMS/desktop channels
**Exit:** EOD closeout locks an immutable snapshot; role dashboards render live KPIs; collaboration + notifications fully working.

## Phase 7 — Hardening, Certification & Launch  ⬜
**Integrations & infra**
- [ ] Real EBM adapter (OSDC/VSDC) + **RRA CIS certification**; real insurer integrations; SMS/momo adapters
- [ ] Observability (Sentry/OTel/Grafana), backups + restore drill, secrets management, deploy pipeline to prod
**Frontend polish**
- [ ] Responsive/tablet (GRN scanning), performance, **a11y audit (axe + manual keyboard)**,
      every screen has designed empty/loading/error states
**QA & launch**
- [ ] Security review, load/perf tests, e2e critical journeys, backup/restore drill
- [ ] Pilot at one depot + one retail branch; feedback loop
**Exit:** certified fiscalization live; pilot running on real transactions; go-live checklist
([08](docs/08-security-and-compliance.md#8-compliance-checklist-go-live-gates)) green.

---

## Cross-cutting workstreams (continuous, every phase — part of each phase's "done")
- **Design system:** apply & extend [docs/design](docs/design/README.md); no hardcoded colours/spacing.
- **Testing:** unit→integration→e2e; coverage gate; compliance tests (immutability/audit) where relevant.
- **Accessibility:** keyboard operable, visible focus, contrast ≥ 4.5:1, `prefers-reduced-motion`.
- **Security:** activity & access logging (every action), deny-by-default RBAC, rate
  limiting, encryption (transit/at-rest/field-level/device), hardening — every phase, per
  [docs/08](docs/08-security-and-compliance.md).
- **Compliance:** GDP immutability/audit, RRA rules, Rwanda FDA license tracking.
- **CI/CD:** keep CI green; make `lint`/`test`/`build`/`migrations` + **dependency/SAST scans** **required** on merge once the runner is unblocked.
- **Docs:** keep architecture, API, data model, design, and this roadmap current.

## Modules → phases
| Module | Slug | Phase |
|---|---|---|
| Identity & Access | `iam` | 0 (auth) → 1 (full) |
| Design system (implementation) | — | 1 (+ upkeep) |
| Catalog | `catalog` | 1 |
| Inventory | `inventory` | 1 |
| Distribution | `distribution` | 2 |
| Documents | `documents` | 2 |
| Retail POS + Desktop | `retail` | 3 |
| Insurance | `insurance` | 4 |
| EBM / Fiscalization | `ebm` | 4 |
| **Collaboration, Notifications & Tools** | `workspace` | 2 (comments) → 4 (notifications) → 6 (full) |
| People / HR | `hr` | 5 |
| Finance | `finance` | 6 |
| Reporting & dashboards | `reporting` | 6 |
| Hardening / certification / launch | — | 7 |

See the module detail in [docs/](docs/README.md) and the collaboration/tools design in
[docs/10-collaboration-notifications-and-tools.md](docs/10-collaboration-notifications-and-tools.md).

## Explicitly out of scope (v1)
Patient-facing e-commerce/app, manufacturing/production, courier GPS hardware, external
chat federation, and AI clinical decision support beyond basic interaction/duplication checks.
