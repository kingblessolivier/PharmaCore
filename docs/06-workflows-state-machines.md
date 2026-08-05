# PharmaCore — Workflows & State Machines

> **Alignment note — foundational (early) doc.** PharmaCore is now framed as a **workspace of subsystems**; the research-backed specs [docs 12–19](README.md) and the [ROADMAP](../ROADMAP.md) **supersede or extend** anything here (each cites its sources). Key deltas: backend is **Django + DRF** (ADR-006, not FastAPI); the depot→retail transfer shipped as the **lean flow** — place → **approve = ship** → **receive = land**, auto-listing at the destination — with picking / driver / per-item-count logistics deferred to the Warehouse phase; and much of this is **already built** (see ROADMAP status). Verified Rwanda/international facts live in [13](13-regulatory-licensing-and-documents-rwanda.md) / [14](14-international-operational-standards.md) / [17](17-insurance-and-government.md) / [18](18-rwanda-integrations-and-statutory.md).

> The behavioural design: the state machines and process flows that operate on the
> data model. These are the rules the services must enforce.
>
> Version 0.1 · 2026-08-03

---

## 1. Stock lifecycle (the spine)

A quantity of a product is always in exactly one conceptual pool. Transitions are
recorded as immutable `stock_movements`.

```
 SUPPLIER ──INTAKE──► [DEPOT STOCK] ──TRANSFER_OUT──► [IN-TRANSIT] ──TRANSFER_IN──► [RETAIL STOCK] ──SALE──► SOLD
                          │  ▲ RESERVE/RELEASE            (locked)        (GRN)            │
                          │  └─ order allocation                                          ├─ WASTAGE ─► DISPOSED
                          └─ ADJUSTMENT (physical count)                                  └─ RECALL ──► QUARANTINE
```

**Invariants**
- `quantity_available >= 0` always (DB CHECK); oversell is hard-blocked online,
  and flagged as a conflict when detected at offline sync.
- Every transition writes one signed `stock_movement` with `reference_type/id`.
- Reserved quantity is not sellable; cancelling an order releases it.

---

## 2. B2B order status

```
DRAFT ─submit─► PENDING ─approve─► APPROVED ─pick─► PICKING ─dispatch─► IN_TRANSIT ─receive─┬─► DELIVERED
   │                │                                                                        └─► PARTIALLY_RECEIVED
   └─cancel─► CANCELLED  ◄── (allowed until dispatch; releases reservations)
```

| Transition | Guard / side-effect |
|---|---|
| submit | PO document generated |
| approve | batches allocated + reserved (RESERVE movements) |
| pick | packing slip generated |
| dispatch | delivery note/waybill generated; depot stock deducted (TRANSFER_OUT); shipment created |
| receive (GRN finalize) | retail stock inserted (TRANSFER_IN); invoice/credit note generated; ledger posted |
| cancel | only pre-dispatch; reservations released |

---

## 3. Retail sale — dual state machine

A sale carries **two** independent status fields.

### 3a. `payment_status`
```
DRAFT ─save (cash/momo)────────────────────────► PAID
   │
   └─save (insurance)──► PENDING_INSURANCE ─adjudicate─► AWAITING_COPAY ─collect copay─► PAID
                                │
                                └─insurer rejects──► AWAITING_COPAY (100% patient-due) ─pay─► PAID
   (any pre-fiscalization state) ─void─► CANCELLED
```

### 3b. `ebm_status` (runs in parallel, async)
```
PENDING_CLAIM ─(amount locked)─► READY_FOR_EBM ─worker picks up─► SENT_TO_EBM ─success─► FISCALIZED
                                                       │
                                                       └─error/timeout─► EBM_ERROR ─retry─► SENT_TO_EBM
```

**Rules**
- The counter is never blocked on `ebm_status`; fiscalization is a background job.
- A cash sale goes `PENDING_CLAIM → READY_FOR_EBM` immediately; an insured sale
  becomes `READY_FOR_EBM` only once the payable amount is locked (post-adjudication).
- EOD closeout requires **no sale left in `EBM_ERROR`** before the day can lock.

---

## 4. Insurance claim flow
```
sale(PENDING_INSURANCE) ─create claim─► SUBMITTED ─insurer response─┬─► FULLY_APPROVED
                                                                     ├─► PARTIALLY_APPROVED ─► balance to patient co-pay
                                                                     └─► REJECTED ─► 100% patient-due (+optional SMS)
   approved/partial ─group─► CLAIM_MANIFEST(period, scheme) ─submit─► receivable opened ─paid─► settled
```
Coverage math at sale time: `covered = min(price, formulary.max_price) × coverage_pct if drug ∈ scheme.formulary else 0`; `copay = payable − covered`.

---

## 5. Document generation triggers
| Document | Trigger event | Async? |
|---|---|---|
| Purchase Order | order submitted | yes |
| Packing Slip / Picking List | order approved/picking | yes |
| Delivery Note / Waybill | shipment dispatched | yes |
| Goods Received Note | GRN finalized | yes |
| Tax Invoice / Credit Note | GRN finalized | yes |
| Retail Receipt / Pro-Forma | sale saved (local first) | local now, EBM later |
| EBM Fiscal Receipt | fiscalization success | yes (worker) |
| Dispensing Label | dispense line | local/print |
| Payslip | payroll approved | yes |
| Wastage Note | wastage logged | yes |
All finalized docs: numbered from `document_sequences`, hashed (SHA-256), stored write-once.

---

## 6. Payroll run flow
```
OPEN RUN ─► aggregate attendance (pro-rate absences) ─► inject commissions/overtime
   ─► apply statutory_rates (PAYE brackets, RSSB pension/medical/maternity/CBHI)
   ─► compute taxable income (after deductible employee contributions) & net
   ─► HR review ─► Finance APPROVE ─► generate payslips + remittance file ─► post payroll journals ─► PAID
```
Guard: pharmacists with `license.status = EXPIRED` are flagged (not paid-blocked, but reported).

---

## 7. End-of-Day (EOD) closeout wizard
```
START ─► [1] Count drawer ──variance?──► flag to auditor
      ─► [2] Sync pending insurance claims ──► manual adjustments
      ─► [3] Trigger pending EBMs ──errors?──► auto-retry; must reach 0 errors
      ─► [4] LOCK DAY ─► write immutable daily_snapshot (sales, COGS, profit, cash, stock value)
```
Once locked, the day's figures cannot be edited — only adjusted via new-dated entries.

---

## 8. Offline sync flow (device ⇄ server)
```
DEVICE                                   SERVER
  sale committed locally
  → append to sync_outbox (PENDING)
  → [online] push events in order  ───►  validate + idempotent upsert by UUID
                                         replay stock_movements
                                         ├─ ok ──────────────► ACK ──► outbox=ACKED
                                         └─ would oversell ──► record + sync_conflict(OVERSELL) ──► notify manager
  pull catalog/price/stock deltas ◄───   server deltas since last_seen
  resolve STALE_UPDATE if local edit clashes
```
Idempotency key = `(origin_device_id, outbox.event_id)`. Every applied event is
also written to `audit_log`.

---

## 9. Permission/state guards (cross-cutting)
- Terminal login requires an **active shift** (attendance clocked-in).
- Rx-only sale line requires a **verified prescription** by a licensed pharmacist.
- Restricted-drug approval requires a **valid (non-expired) license**.
- Posting a journal requires **Σdebits = Σcredits**.
- Locking a day requires **0 EBM errors** and drawer reconciliation acknowledged.
