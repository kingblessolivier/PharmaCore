# PharmaCore — Use Cases & User Stories

> Actors, the use cases each performs, and detailed flows for the critical ones.
> Complements the SRS ([03-srs.md](03-srs.md)).
>
> Version 0.1 · 2026-08-03

---

## 1. Actor catalog

| Actor | Belongs to | Primary goals |
|---|---|---|
| **System Admin** | HQ | Configure orgs, roles, integrations, tax/insurance rules |
| **Org Admin / Branch Manager** | Depot/Retail | Oversee operations, run EOD, view reports |
| **Purchasing Clerk** | Depot | Log supplier intake, verify factory batches |
| **Warehouse Clerk / Picker** | Depot | Receive, store, pick stock by FEFO |
| **Dispatcher** | Depot | Assign shipments, attach transport docs |
| **Driver** | Depot/Logistics | Deliver shipments, capture proof of delivery |
| **Pharmacist (licensed)** | Retail | Verify Rx, dispense, check interactions |
| **Cashier** | Retail | Ring up sales, take payment, manage drawer |
| **Insurance Clerk** | Retail | Reconcile claims, submit manifests |
| **Accountant** | HQ/Retail | Ledger, receivables, tax reconciliation |
| **HR Manager** | HQ | Employees, attendance, payroll |
| **External: RRA EBM** | system | Fiscalize sales/purchases |
| **External: Insurer** | system | Adjudicate claims |

---

## 2. Use-case inventory (by module)

**IAM:** Register organization · Manage users & roles · Sign in / MFA · Assign departments · Track licenses · Review audit log
**Catalog:** Add/edit medicine · Map ingredients · Manage barcodes · Maintain interactions
**Inventory:** Receive supplier intake · Adjust stock (physical count) · Log wastage · View expiry forecast · Recall batch · Internal department transfer
**Distribution:** Place purchase order · Approve & allocate order · Pick & pack · Dispatch shipment (multi-stop) · Receive goods (GRN) · Raise discrepancy claim
**Documents:** Generate document · View document vault · Verify by QR
**Retail POS:** Open drawer · Search & add medicine · Select batch (FEFO) · Attach prescription · Take payment (split) · Route via insurance · Complete sale offline · Close drawer
**Insurance:** Configure scheme & formulary · Compute co-pay · Reconcile claim · Submit manifest · Report aging
**EBM:** Configure provider · Register item/purchase · Fiscalize sale · Retry failed EBM
**HR:** Add employee · Clock in/out · Request/approve leave · Run payroll · Generate payslips
**Finance:** Maintain chart of accounts · Post journal · Auto-post from operations · Close fiscal period
**Reporting:** Run EOD closeout · View dashboards · View departmental reports · Manage notifications

---

## 3. Detailed use cases (the critical paths)

### UC-01 — Place & fulfil a B2B stock order (depot → retail)
**Actors:** Retail Manager, Depot Warehouse Clerk, Dispatcher, Driver, Receiving Pharmacist
**Precondition:** Retail org has an account and the depot has stock.
**Main flow:**
1. Retail Manager browses the depot's catalog (FEFO-sorted) and adds items+quantities.
2. System creates `stock_order` = `PENDING`; generates **Purchase Order** doc.
3. Depot Clerk reviews, approves, and the system **allocates specific batches** and reserves them (`stock_movement: RESERVE`). Order = `APPROVED`→`PICKING`.
4. System generates **Packing Slip / Picking List** (bin locations, batches, expiry).
5. Dispatcher assigns the order to a **shipment** (+ vehicle, driver, optional multi-stops), generates **Delivery Note / Waybill** with QR; order = `IN_TRANSIT`; depot stock deducted (`TRANSFER_OUT`).
6. Driver delivers; Receiving Pharmacist scans the QR → opens **GRN** intake checklist.
7. Pharmacist counts; enters received/damaged per line. System flags discrepancies.
8. On **finalize GRN**: stock inserted into retail inventory (`TRANSFER_IN`), order = `DELIVERED` (or `PARTIALLY_RECEIVED`); **GRN** doc finalized (immutable); **Tax Invoice** (and **Credit Note** if short) generated.
**Alt flows:** shortage/damage → `discrepancy_claim` + credit note; order cancelled before dispatch → reservations released.
**Postcondition:** Stock is live in retail POS; documents archived; ledgers posted.

### UC-02 — Retail sale with insurance, **offline** (the hardest path)
**Actors:** Cashier, Pharmacist, (async) Insurer, RRA EBM
**Precondition:** Cashier has an open drawer; device holds local catalog + stock; internet may be down.
**Main flow:**
1. Cashier **manually searches** a medicine; picks it. If multiple batches, system highlights FEFO batch (expired hidden).
2. If Rx-only: system blocks until Pharmacist verifies/attaches a prescription.
3. Cashier repeats for all items; system shows interaction/duplication warnings.
4. Customer is insured → Cashier selects **Route via Insurance**, enters policy number. System computes covered vs. co-pay from the scheme's formulary.
5. Cashier takes the **co-pay** (cash/momo) and completes the sale. Locally: `retail_sale` (UUID) saved, local batch stock deducted, `payment_status = PENDING_INSURANCE` or `AWAITING_COPAY`→`PAID`, `ebm_status = PENDING_CLAIM/READY_FOR_EBM`. A **Pro-Forma/Receipt** prints from local data.
6. Actions queue in the **outbox**.
7. **On reconnect:** outbox syncs to server → server registers the claim, runs **EBM fiscalization** (async, retry) → `ebm_status = FISCALIZED`, EBM receipt stored; claim later reconciled by Insurance Clerk.
**Alt flows:** oversell detected at sync (two offline terminals) → `sync_conflict: OVERSELL` raised to manager; EBM error → surfaced for retry; insurer rejects → balance becomes patient-due (+SMS).
**Postcondition:** Sale recorded, fiscalized, claim tracked — with no dependence on connectivity at the counter.

### UC-03 — Supplier intake at the depot
**Actors:** Purchasing Clerk
1. Clerk logs an incoming manufacturer/importer shipment.
2. Enters products, **batch numbers, mfg/expiry, cost, quantities**; QA-checks cold-chain items.
3. System creates `inventory_batches` (`received_via = SUPPLIER_INTAKE`, `stock_movement: INTAKE`) and an **EBM purchase registration**.
**Postcondition:** Depot wholesale pool updated; purchase declared to EBM.

### UC-04 — Process & submit insurance claims
**Actors:** Insurance Clerk
1. Clerk opens the **Claims Queue** (`PENDING_INSURANCE` sales).
2. Reconciles each against the insurer's response; enters approved amount + co-pay.
3. System updates the sale (`AWAITING_COPAY`/`PAID`) and marks `ebm_status = READY_FOR_EBM`.
4. Clerk groups claims into a **manifest** per scheme and submits (periodic).
**Postcondition:** Receivables tracked; co-pays owed surfaced.

### UC-05 — Run monthly payroll
**Actors:** HR Manager, Finance
1. HR opens a **payroll run** for the period.
2. System aggregates attendance (pro-rates absences), injects commissions/overtime.
3. Applies **statutory deductions** from `statutory_rates` (PAYE brackets, RSSB pension/medical/maternity/CBHI).
4. HR reviews; Finance approves. System computes net, generates **payslips** + **bank remittance file**, posts payroll journals.
**Guardrail:** employees with expired licenses flagged.

### UC-06 — End-of-Day closeout
**Actors:** Branch Manager
1. Manager starts the **EOD wizard**.
2. **Count drawer** → variance vs. system flagged.
3. **Sync pending insurance claims**; review adjustments.
4. **Trigger pending EBMs**; auto-retry network errors; confirm 100% fiscalized.
5. **Lock day** → immutable `daily_snapshot` (sales, COGS, profit, cash, stock value). Cannot be edited retroactively.

---

## 4. User stories (sample backlog seeds)

- As a **cashier**, I can sell a medicine by typing its name so I don't need a scanner.
- As a **cashier**, I can complete a sale when the internet is down so customers aren't turned away.
- As a **pharmacist**, I must verify a prescription before an Rx-only drug is sold so we stay compliant.
- As a **warehouse clerk**, I'm shown the oldest-expiry batch to pick so stock doesn't expire.
- As a **receiving pharmacist**, I can record short/damaged quantities before accepting stock so we aren't billed for what we didn't get.
- As an **insurance clerk**, I can see all sales awaiting adjudication in one queue so nothing is missed.
- As an **accountant**, I can trust that no posted journal was silently edited so audits pass.
- As an **HR manager**, payroll applies the current PAYE/RSSB rates automatically so I don't compute them by hand.
- As a **branch manager**, I cannot close the day until every sale is fiscalized so we avoid RRA penalties.
- As a **system admin**, I can add a new insurer with its own coverage % and drug list without a code change.

---

## 5. Use-case → requirement traceability (excerpt)
| Use case | Key FRs |
|---|---|
| UC-01 | FR-DST-1..6, FR-DOC-1..4, FR-INV-3/4 |
| UC-02 | FR-POS-1..7, FR-INS-2/3, FR-EBM-1..4 |
| UC-03 | FR-INV-1, FR-EBM-2 |
| UC-04 | FR-INS-3/4/6 |
| UC-05 | FR-HR-4/5/6 |
| UC-06 | FR-REP-1, FR-EBM-3 |
