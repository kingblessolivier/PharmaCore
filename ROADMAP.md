# PharmaCore — Roadmap

Phased, dependency-ordered delivery. We build **foundation-first**: every phase
ships something usable and is a prerequisite for the next. Dates are relative
(no hard commitments here) — the *order* is the commitment.

Legend: ✅ done · 🚧 in progress · ⬜ planned

---

## Phase 0 — Foundations & scaffolding  ✅
Repo, tooling, and the walking skeleton everything else stands on.
- [x] Repo init, branch protection (staging/main), CI pipeline (lint→type→test→build)
- [x] Backend scaffold (Django + DRF, Django ORM + migrations), Postgres via docker-compose
- [x] Frontend scaffold (React + TS), design tokens wired from the design docs
- [x] Auth: JWT login (simplejwt), argon2 hashing, custom `User` model, `/api/auth/me`
- [x] `audit_log` (append-only) + base RBAC (`Role` + `HasRole`); roles seeded
**Exit criteria:** ✅ a user can log in; CI green locally on every check; migrations run clean.
> Note: GitHub Actions runners are blocked at the account level (email verification)
> — code is verified green locally.

## Phase 1 — Identity, Catalog & Inventory (the core)  🚧
The data foundation every module reads from.
- [ ] Organizations, departments, users, roles, permissions, licenses
- [ ] Product master (medicine fields, ATC/GTIN/tax class), ingredients, barcodes
- [ ] Batch inventory, `stock_movements` (immutable), FEFO queries
- [ ] Supplier intake, adjustments, wastage, expiry alerts
**Exit criteria:** stock can be received, counted, and viewed at batch level with FEFO.

## Phase 2 — Distribution & Documents (B2B)  ⬜
Depot→retail transfer with the paperwork.
- [ ] Purchase orders → depot approval/allocation → shipment/dispatch
- [ ] GRN intake (the stock write-event) + discrepancy claims
- [ ] Document engine (PDF worker, sequences, hashing, vault, QR)
- [ ] PO / packing slip / delivery note / GRN / invoice generation
**Exit criteria:** a full order → transfer → reception cycle produces immutable, verifiable documents.

## Phase 3 — Retail POS + Offline sync (the hard one)  ⬜
The counter, built offline-first (ADR-001).
- [ ] Desktop POS shell (Tauri/Electron) + local datastore
- [ ] Manual search, FEFO batch pick, cart, split payments
- [ ] Sale state machine (payment_status), cash drawer sessions
- [ ] Sync engine: outbox, UUID minting, pull deltas, oversell reconciliation/conflicts
- [ ] Prescriptions + dispensing (licensed-user gate), dispensing labels
**Exit criteria:** a sale completes with internet off and reconciles correctly on reconnect.

## Phase 4 — Insurance & EBM (compliance)  ⬜
Multi-insurer claims (ADR-002) + fiscalization (ADR-003).
- [ ] Insurance schemes, agreements, formulary; co-pay computation
- [ ] Claims queue, adjudication, manifests, receivables aging
- [ ] `EbmProvider` abstraction + MockEbmProvider; async fiscalization + retry
- [ ] EBM receipts (SDC id, signature, QR, tax by class), purchase registration
**Exit criteria:** an insured, fiscalized sale flows end-to-end against the mock provider; EBM errors surface for retry.

## Phase 5 — People / HR & Payroll  ⬜
- [ ] Employees, licenses (dispensing-rights link), attendance, shifts, leave
- [ ] `statutory_rates` config (PAYE/RSSB), payroll runs, payslips, remittance file
**Exit criteria:** a monthly payroll run computes correct net pay with current Rwanda rates and generates payslips.

## Phase 6 — Finance & Reporting  ⬜
- [ ] Chart of accounts, balanced immutable journals, auto-posting from ops
- [ ] Fiscal periods, receivables, expenses
- [ ] Dashboards (per-role), operational reports, EOD closeout + daily snapshots
- [ ] Notifications (low stock, expiry, license, EBM error, claims)
**Exit criteria:** EOD closeout locks an immutable snapshot; role dashboards render live KPIs.

## Phase 7 — Hardening, Certification & Pilot  ⬜
- [ ] Real EBM adapter (OSDC/VSDC) + **RRA CIS certification**
- [ ] Real insurer integrations; SMS/momo adapters
- [ ] Security review, load/perf, backup/restore drill, a11y audit
- [ ] Pilot at one depot + one retail branch; feedback loop
**Exit criteria:** certified fiscalization live; pilot running on real transactions; go-live checklist ([08](docs/08-security-and-compliance.md#8-compliance-checklist-go-live-gates)) green.

---

## Cross-cutting workstreams (continuous, every phase)
- **Compliance:** GDP immutability/audit, RRA rules, Rwanda FDA license tracking.
- **Design:** apply the design system ([docs/design](docs/design/README.md)) as UIs are built.
- **Testing:** unit→integration→e2e coverage grows with each module.
- **Docs:** keep architecture, API, and this roadmap current as scope evolves.

## Explicitly out of scope (v1)
Patient-facing e-commerce/app, manufacturing/production, courier GPS hardware,
AI clinical decision support beyond basic interaction/duplication checks.

## How this maps to the modules
See the module table in the root [README](README.md) and the technical design in
[docs/](docs/README.md). Each phase = one or more modules brought to "done" per the
[Definition of Done](docs/development/definition-of-done.md).
