# Inventory redesign plan

**Status:** I-A to I-E built and verified; I-F partially done · **Date:** 2026-08-07

## How this differs from Finance, Retail and Distribution

Those three had models with no engine behind them. Inventory is the opposite: 24
models and six service modules (`services`, `warehouse_services`, `coldchain`,
`serialisation`, `analytics`, `gs1`), most of them genuinely wired. Put-away,
wave picking, cold-chain excursions, EPCIS serialisation and reorder analytics
all have real logic and real tests.

So the defects here are not "nothing happens". They are **the wrong thing
happening in the two places where being wrong hurts a patient**, plus a
consistent architectural drift.

## What the domain actually requires

Researched against how these functions work in practice, because the code cannot
be judged complete without it:

* **Quarantine and release (GDP).** Goods arrive, sit in quarantine, and become
  saleable only when a competent person releases them. Release is a *decision*
  with a name against it, and the person who received the goods must not be the
  person who releases them.
* **Recall (WHO GDP / Rwanda FDA).** A recall is not a freeze. It is: identify
  every unit of *that product* in *that batch*, freeze what is still held, then
  **trace where the rest went** — which pharmacies received it, and for a Class I
  recall, which patients were dispensed it. Freezing on-hand alone catches only
  the stock that did not move, which is the least dangerous part.
* **Destruction.** Expired or recalled stock is destroyed under witness, and the
  destruction must remove the units from stock *and* write the loss off to the
  P&L. A certificate with no stock movement behind it is a document that lies.
* **Physical counts.** A variance adjusts stock and posts to the ledger. It must
  be impossible to post the same variance twice.

## Defects

Each verified against the code, not assumed.

| # | Defect | Evidence |
|---|--------|----------|
| **I1** | **A recall freezes unrelated medicines.** `execute_freeze` filters `InventoryBatch.objects.filter(batch_number=recall.batch_number)` — batch number alone, across every organization. `BatchRecall` carries a `product` FK and it is ignored. The uniqueness constraint is `(organization, product, batch_number)`, so the same batch string legitimately exists on different products. Recalling paracetamol "A123" would freeze amoxicillin "A123" everywhere. *(Latent on current data — 10 batches, no collision yet — but the schema permits it and manufacturers reuse batch formats.)* | `views.py:288-291`, `models.py` constraint `uniq_org_product_batch` |
| **I2** | **A recall never traces where the stock went.** It freezes on-hand and stops. Nothing identifies which pharmacies received the batch or which patients were dispensed it — although the data exists (`ShipmentItem`, `GRNLine`, `InTransitStock` and retail `Dispensing` all carry batch). The most dangerous units are precisely the ones that already left. | no tracing code |
| **I3** | **A stock count can be approved twice**, adjusting stock twice and posting the GL twice. `approve_count` has no status guard — a double-click or a retry corrupts both inventory and the ledger. | `views.py:316-343` |
| **I4** | **"Confirm destruction" destroys nothing.** It sets a status and a timestamp. No stock is removed, no `StockMovement` is written, no write-off reaches the P&L — so destroyed stock stays on the books as sellable and the loss never lands. | `views.py:358-364` |
| **I5** | **`StockDisposal` has no lines.** It records witnesses, a method and a certificate number, but *not what was destroyed* — no batch, no quantity. It cannot remove stock even in principle, because the model does not know what to remove. | `models.py:569+`, no FK targets it |
| **I6** | **No segregation of duties on release or adjustment.** `pass_qc` lets whoever received the goods release them; `approve_count` lets the counter approve their own count. Both are the controls those steps exist to provide. | `views.py:262-269`, `perform_create` on both |
| **I7** | **Business logic lives in views.** QC pass/fail, recall freeze, count approval and disposal all mutate state inside `views.py`, against the convention this codebase states explicitly ("Every state change that matters lives here — never in a serializer or view", `procurement/services.py`). It is why none of the above are reachable from a management command or testable without HTTP. | `views.py` |
| **I8** | **`pass_qc` / `fail_qc` have no state machine.** A failed check can be re-passed, a passed one re-failed, with no reason captured on failure and no `update_fields`. | `views.py:262-280` |

## Phases

Logic first, then screens — each phase with tests, as in the previous three.

* **I-A — `quality.py`**: release/reject as services with a state machine, a
  captured reason, and four-eyes enforcement. Quarantined stock has one way out.
* **I-B — `recalls.py`**: scope the freeze to `(product, batch_number)`; add
  `trace_batch()` returning every downstream holder — pharmacies that received
  it, units still in transit, and dispensings against it — and a recall
  notice document per affected organization.
* **I-C — `DisposalLine` + destruction**: give disposal lines (batch, quantity),
  remove the stock on confirmation via `StockMovement.WASTAGE`, and post the
  write-off. Refuse destruction of a batch that is not quarantined or recalled.
* **I-D — count integrity**: status guard so a variance posts exactly once, and
  approver ≠ counter.
* **I-E — move logic out of views** into services, leaving views as transport.
* **I-F — screens**: audit all 15 against `DataGrid` + `RecordKit`, as with
  Distribution, and surface what the engine now knows (trace results, quarantine
  queue, destruction evidence).

## Method

Audit against real code → quantify → name defects with evidence → build logic
before UI → test → live HTTP walkthrough. The walkthrough has found bugs in every
phase of this project that the unit tests did not.


## What was built

| Phase | Delivered | Verified |
|---|---|---|
| **I-A** `quality.py` | Release/reject as services with a state machine, a required rejection reason, four-eyes enforcement on identity, and a quarantine queue ranked by age and expiry risk. | 5 tests |
| **I-B** `recalls.py` | Freeze scoped to `(product, batch_number)`; `trace_batch()` following the batch through on-hand, in-transit, GRN receipts and `SaleBatchAllocation` to named patients; close refused while recalled stock is still held. | 4 tests + live walkthrough |
| **I-C** `disposal.py` + `DisposalLine` | Disposals now carry lines (batch + quantity). Confirming removes the units, writes a `WASTAGE` movement and posts the write-off. Guarded: only withdrawn stock, two witnesses, and idempotent per line. | 6 tests |
| **I-D** `counting.py` | Approve-once status guard, approver ≠ counter, and a variance report shown before the irreversible post. | 3 tests |
| **I-E** | QC, recall, count and disposal logic moved out of `views.py` into services; views are transport. | full suite |

### Proven on live data

The recall walkthrough on the running server found the batch across two
organizations and reported `reached_patients=True` with two units dispensed —
the capability that did not exist in any form before. Closing was correctly
refused while stock was still held.

### Tests that asserted the defects

Four existing tests encoded the broken behaviour and were rewritten, not deleted:

* the QC workflow used one user as inspector *and* decider, decided the same
  check twice, and rejected with no reason;
* the recall test asserted `affected_batches`, a count of frozen rows that says
  nothing about the units already gone;
* the count test had one person count and approve;
* the disposal test confirmed a destruction with **no stock listed** — it
  "succeeded" while the goods stayed on the books.

### Screens

Rebuilt on `DataGrid` + `RecordKit`: **Quality Control** (queue with age and
expiry risk; rejection reason required — the old page posted none and would now
be refused), **Batch Recalls** (the trace, including patients to contact),
**Physical Counts** (variance shown before approval), **Stock Disposal**
(candidate stock, disposal lines, destruction evidence), and the **Inventory
overview** (needs-attention panel over `/api/inventory/overview/`).

## Still open

* **I-F is partial.** Nine inventory screens remain on `Modal` rather than
  `RecordKit`: Warehouses, Zones & Bins, Put-away Rules, Wave Picking,
  Replenishment, Track & Trace, Consignment/VMI, Temperature Logs, Cold-Chain
  Compliance. All are large (300–734 lines), already on `DataGrid`, and
  functional — this is a consistency gap, not a defect.
* **Nothing has been rendered in a browser** (no browser tool available).
