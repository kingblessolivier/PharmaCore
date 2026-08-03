# PharmaCore — Software Requirements Specification (SRS)

> Structured after IEEE-830. This is the "system analysis" document: what the
> system must do (functional) and how well (non-functional), independent of how
> it is built. Design lives in [05-architecture.md](05-architecture.md).
>
> Version 0.1 · 2026-08-03 · Status: Draft for review

---

## 1. Introduction

### 1.1 Purpose
Define the complete requirements for **PharmaCore**, a unified pharmaceutical ERP
for Rwanda covering wholesale depot→retail distribution, retail dispensing/POS,
transport & reception documentation, RRA EBM tax compliance, multi-insurer
claims, HR/payroll, and finance — on one database with an offline-capable POS.

### 1.2 Scope
PharmaCore serves three organization types: **HQ**, **Depot (wholesaler)**, and
**Retail pharmacy**. It manages a medicine's full life — from depot intake,
through B2B transfer, to retail sale to a patient — plus the people, money, and
compliance around it. Out of scope (v1): e-commerce patient app, manufacturing/
production, and courier GPS hardware integration.

### 1.3 Definitions
| Term | Meaning |
|---|---|
| **FEFO** | First-Expired-First-Out picking |
| **GRN** | Goods Received Note |
| **EBM** | Electronic Billing Machine (RRA fiscalization) |
| **VSDC/OSDC** | Virtual/Online Sales Data Controller (RRA integration) |
| **CBHI** | Community-Based Health Insurance (Mutuelle, via RSSB) |
| **GDP** | Good Distribution Practice |
| **Batch** | A lot of a product with one lot number + expiry |

### 1.4 References
[00-research-findings.md](00-research-findings.md), [01-key-decisions.md](01-key-decisions.md),
[02-data-model.md](02-data-model.md).

---

## 2. Overall Description

### 2.1 Product perspective
A new, self-contained modular system (modular monolith backend + web frontend +
offline desktop POS). Integrates externally with RRA EBM, insurers (RSSB and
others), SMS/email gateways, and mobile-money.

### 2.2 User classes
| Class | Description | Technical skill |
|---|---|---|
| System admin | Configures orgs, roles, integrations | High |
| Org admin / manager | Runs a depot or branch, sees reports | Medium |
| Pharmacist (licensed) | Verifies Rx, dispenses, checks interactions | Medium |
| Cashier | Rings up sales, manages drawer | Low |
| Warehouse clerk / picker | Receives & picks stock | Low |
| Dispatcher / driver | Loads and delivers shipments | Low |
| Insurance clerk | Reconciles claims | Medium |
| Accountant | Ledger, receivables, tax | High |
| HR manager | Staff, attendance, payroll | Medium |

### 2.3 Operating environment
Web app (modern browsers) for back-office; **desktop app (Tauri/Electron) with a
local datastore** for the retail counter; backend on Linux server / cloud +
PostgreSQL. Intermittent connectivity assumed at retail sites.

### 2.4 Constraints
- Must comply with **RRA EBM** (certified integration) and **Rwanda FDA / GDP**.
- Financial and legal records are **immutable** (append-only, void-not-delete).
- Retail POS **must operate offline** and reconcile on reconnect (ADR-001).
- Statutory rates and insurance rules are **configuration, not code**.

### 2.5 Assumptions & dependencies
RRA CIS certification obtained before go-live; insurers provide claim formats;
each branch has a supported device for the POS; a mobile-money API is available.

---

## 3. Functional Requirements

> IDs: `FR-<MODULE>-<n>`. Priority: **M** (must), **S** (should), **C** (could).

### 3.1 Identity & Access (IAM)
- **FR-IAM-1 (M):** Register organizations (HQ/Depot/Retail) with TIN and Rwanda FDA license.
- **FR-IAM-2 (M):** Create users scoped to an organization and department.
- **FR-IAM-3 (M):** Role-based access control; a user has ≥1 role, roles grant permissions.
- **FR-IAM-4 (M):** Authenticate via username/email + password; support session expiry; optional MFA.
- **FR-IAM-5 (M):** Every state-changing action writes an immutable `audit_log` row (who/what/when/before/after).
- **FR-IAM-6 (S):** Store and track license expiry for orgs and staff; alert before expiry.
- **FR-IAM-7 (M):** Deny access to terminals unless the user is clocked in for an active shift (POS/warehouse tools).

### 3.2 Catalog
- **FR-CAT-1 (M):** Maintain a medicine master with generic/brand, form, strength, pack, ATC, GTIN, tax class, Rx flag, controlled flag, storage condition.
- **FR-CAT-2 (M):** Map products to active ingredients (for interaction/duplication checks).
- **FR-CAT-3 (M):** Store multiple barcodes per product at different packaging levels.
- **FR-CAT-4 (S):** Maintain a drug-interaction reference (licensed dataset or basic duplication rules).

### 3.3 Inventory
- **FR-INV-1 (M):** Track stock at **batch level** (lot, mfg, expiry, qty, cost) per organization.
- **FR-INV-2 (M):** Suggest batches by **FEFO** during picking and dispensing.
- **FR-INV-3 (M):** Record every quantity change as an immutable `stock_movement` linked to its cause.
- **FR-INV-4 (M):** Reserve/lock batch quantity when allocated to an order/sale; release on cancel.
- **FR-INV-5 (M):** Prevent quantity from going negative; hard-block oversell with a clear message.
- **FR-INV-6 (S):** Alert on low stock (reorder level), near-expiry (60/90/180 days), and cold-chain items.
- **FR-INV-7 (M):** Log wastage (expired/damaged) and remove from sellable stock, generating a wastage document.
- **FR-INV-8 (S):** Batch-level **recall**: identify all locations/sales holding a given batch.
- **FR-INV-9 (S):** Support internal transfers between departments (backroom → counter) with approval.

### 3.4 Wholesale / B2B Distribution
- **FR-DST-1 (M):** Retail pharmacy places a purchase order to a depot from that depot's FEFO catalog.
- **FR-DST-2 (M):** Depot approves and allocates specific batches, reserving them.
- **FR-DST-3 (M):** Generate transport docs (packing slip, delivery note/waybill) on dispatch.
- **FR-DST-4 (M):** Support multi-stop shipments (one truck → several pharmacies).
- **FR-DST-5 (M):** Retail receives via **GRN**: scan/enter counts vs. manifest; the finalized GRN moves stock into retail inventory.
- **FR-DST-6 (M):** Capture discrepancies (shortage/damage/wrong/expired) before ownership is accepted.
- **FR-DST-7 (S):** Record cold-chain temperature logs against a shipment.
- **FR-DST-8 (S):** Auto-generate draft POs from reorder rules when retail stock is low.

### 3.5 Documents
- **FR-DOC-1 (M):** Generate PDF documents (PO, packing slip, delivery note, GRN, invoice, credit note, receipt, dispensing label, payslip, wastage) from templates.
- **FR-DOC-2 (M):** Assign gapless per-organization document numbers.
- **FR-DOC-3 (M):** Store finalized documents **write-once** with a content hash; never overwrite/delete.
- **FR-DOC-4 (M):** Embed a QR code on transport & fiscal documents.
- **FR-DOC-5 (S):** Generate documents asynchronously (background worker) so the UI never blocks.

### 3.6 Retail POS & Dispensing
- **FR-POS-1 (M):** Cashier finds medicines by **manual live-search** (name/generic), not required to scan.
- **FR-POS-2 (M):** On selection, require choosing a **batch**; highlight the FEFO (oldest) batch; hide expired batches from cashier.
- **FR-POS-3 (M):** Block checkout of Rx-only drugs until a valid prescription is attached/verified by a licensed pharmacist.
- **FR-POS-4 (M):** Support the sale **state machine**: draft → (pending insurance) → awaiting co-pay → paid; and EBM sub-state.
- **FR-POS-5 (M):** Accept split payments (cash / mobile money / card / insurance).
- **FR-POS-6 (M):** **Operate fully offline** — capture the sale locally, deduct local batch stock, queue EBM + claim for later sync.
- **FR-POS-7 (M):** Manage a cashier cash drawer session with opening float and end-of-shift count/variance.
- **FR-POS-8 (S):** Print a dispensing label (dosage instructions, pharmacy license, expiry).
- **FR-POS-9 (S):** Warn on drug interactions/duplications across the basket / patient history.

### 3.7 Insurance
- **FR-INS-1 (M):** Maintain multiple insurance schemes, each with coverage rules and a covered-drug formulary.
- **FR-INS-2 (M):** Compute insurance-covered vs. patient co-pay per sale from *(scheme, formulary, coverage %)* — never hard-coded.
- **FR-INS-3 (M):** Create a claim per insured sale; track status (submitted→approved/partial/rejected).
- **FR-INS-4 (M):** Group claims into periodic per-scheme manifests for submission.
- **FR-INS-5 (S):** On rejection, convert the balance to patient-due; optionally notify the patient by SMS.
- **FR-INS-6 (S):** Report insurer aging receivables (30/60/90+ days).

### 3.8 EBM / Fiscalization
- **FR-EBM-1 (M):** Integrate with RRA via a pluggable **EbmProvider** (OSDC/VSDC/Mock).
- **FR-EBM-2 (M):** Register items and purchases with EBM; fiscalize sales and obtain SDC id, receipt number, signature, QR.
- **FR-EBM-3 (M):** Run fiscalization **asynchronously with retry**; never block the sale; surface EBM errors for retry.
- **FR-EBM-4 (M):** Store each fiscal receipt immutably with tax breakdown by class.
- **FR-EBM-5 (M):** Correctly classify each line by product **tax class** (A/B/C/D).

### 3.9 HR & Payroll
- **FR-HR-1 (M):** Maintain employee records incl. national ID, professional license, department, base salary.
- **FR-HR-2 (M):** Track attendance (clock-in/out) with IP/geo; mark late/absent/leave.
- **FR-HR-3 (M):** Manage shifts/rosters and leave requests with approval.
- **FR-HR-4 (M):** Run monthly payroll: aggregate hours, add commissions/overtime, apply statutory deductions from `statutory_rates`, compute net.
- **FR-HR-5 (M):** Apply Rwanda PAYE brackets and RSSB (pension/medical/maternity/CBHI/occupational) as **versioned configuration**.
- **FR-HR-6 (M):** Generate payslips and a bank/mobile-money remittance file.
- **FR-HR-7 (M):** **Auto-revoke** dispensing/approval permission when a pharmacist's license is expired.

### 3.10 Finance & Accounting
- **FR-FIN-1 (M):** Maintain a chart of accounts per organization.
- **FR-FIN-2 (M):** Post balanced double-entry journal entries; corrections are reversing entries (immutable).
- **FR-FIN-3 (S):** Auto-post journals for sales, COGS, purchases, payroll, wastage.
- **FR-FIN-4 (S):** Track receivables (insurer) and expenses; fiscal-period open/close/lock.

### 3.11 Reporting & Operations
- **FR-REP-1 (M):** End-of-Day closeout wizard: cash count → sync claims → trigger EBMs → lock day → immutable `daily_snapshot`.
- **FR-REP-2 (M):** Departmental reports (supplier performance, expiry forecast, stock valuation, order fill rate, cash reconciliation, aging receivables, EBM reconciliation, dispensed-medication log).
- **FR-REP-3 (S):** Manager dashboard of daily KPIs per branch/depot.
- **FR-REP-4 (S):** Notifications for low stock, expiry, license expiry, claim approval, EBM error, discrepancies.

---

## 4. Non-Functional Requirements

### 4.1 Performance
- **NFR-P1:** POS search returns suggestions in < 300 ms locally.
- **NFR-P2:** A retail sale commits locally in < 1 s regardless of network.
- **NFR-P3:** Document PDF generation completes async in < 30 s.

### 4.2 Availability & reliability
- **NFR-A1:** Retail POS availability is **independent of internet** (offline-first).
- **NFR-A2:** Central backend target uptime 99.5%; graceful degradation for EBM/insurer outages (queue + retry).
- **NFR-A3:** No data loss on sync: every offline action is durably queued (outbox) until acknowledged.

### 4.3 Scalability
- **NFR-S1:** Support many branches/depots (multi-tenant by `organization_id`).
- **NFR-S2:** Inventory and sales tables partition-friendly (batch-level, high volume).

### 4.4 Security & privacy
- **NFR-SEC-1:** Encryption in transit (TLS) and at rest (AES-256) incl. credentials.
- **NFR-SEC-2:** RBAC least-privilege; cashier cannot access payroll, etc.
- **NFR-SEC-3:** Patient data (allergies, Rx, insurance) access-controlled and logged.
- **NFR-SEC-4:** Full audit trail; sensitive records immutable.
See [08-security-and-compliance.md](08-security-and-compliance.md).

### 4.5 Compliance
- **NFR-C1:** RRA EBM-certified fiscalization for all retail sales.
- **NFR-C2:** GDP-grade traceability & data integrity across distribution.
- **NFR-C3:** Rwanda FDA license tracking for premises and staff.

### 4.6 Usability
- **NFR-U1:** POS usable by low-skill cashiers; core sale in ≤ 5 interactions.
- **NFR-U2:** Bilingual UI (English + Kinyarwanda) — *should*.

### 4.7 Maintainability & portability
- **NFR-M1:** Modular boundaries; each module owns its schema/routes.
- **NFR-M2:** External integrations behind adapter interfaces (EBM, insurer, SMS, momo).
- **NFR-M3:** Config-driven statutory/insurance rules (no redeploy for rate changes).

---

## 5. External Interfaces
| Interface | Direction | Purpose |
|---|---|---|
| RRA EBM (OSDC/VSDC) | out/in | fiscalize sales, register items/purchases |
| Insurer portals (RSSB & others) | out/in | claim submission & reconciliation (batch) |
| SMS / Email gateway | out | notifications (claim approved, co-pay due) |
| Mobile money API | out/in | POS payments |
| Mapping API | out | logistics routing (later) |
| Object storage (S3-compatible) | out | immutable document PDFs |

---

## 6. Requirements traceability
Each FR maps to a data-model area in [02-data-model.md](02-data-model.md), a
workflow in [06-workflows-state-machines.md](06-workflows-state-machines.md), and
one or more API endpoints in [07-api-design.md](07-api-design.md). A traceability
matrix will be maintained as build begins.
