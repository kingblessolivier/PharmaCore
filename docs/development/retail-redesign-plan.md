# Retail redesign

**Status:** in progress · **Started:** 2026-08-07 · **Owner:** Claude

Brief: *"go on retail and redesign all screens and its logic according to what is
now being used in modern technology."*

The screens are the smaller half. A pharmacy till has a specific shape — scan,
keyboard, never stop for the network — and this one has none of it. Below is what
the code actually does, measured the same way the finance audit was.

---

## 1. Diagnosis

### R1 — The till cannot scan

`catalog.ProductBarcode` exists as a model. `PosPage.tsx` contains **zero**
references to barcode or scanning: products are found by typing a name into a
search box and clicking a result.

Every pharmacy counter in the world runs on a barcode scanner. A scanner is a
keyboard that types very fast and presses Enter — the till has to be listening for
that, resolve the code to a product, and add a line without anyone touching a
mouse. None of that exists.

### R2 — The till cannot be driven from the keyboard

**Zero** key handlers in the POS screen. Every action is a click. A cashier serving
a queue works by touch and muscle memory: focus the scan field, F-keys for tender,
Enter to complete. A mouse-only till is slower than the paper it replaced.

### R3 — Offline-first is a documented decision with no implementation

`docs/19-platform-architecture-decisions.md` §2 is titled **"Offline-first at the
counter (Retail POS)"**. The frontend contains no service worker, no IndexedDB, no
`navigator.onLine` — **nothing**.

So when the connection drops, the pharmacy stops selling. In a Kigali pharmacy that
is not a hypothetical, and it is the single most consequential gap here: everything
else degrades the experience, this one stops the business.

### R4 — The controlled-drugs register is filled in by hand

`ControlledSubstanceRegister` appears in serializers and URLs and **nowhere in
`complete_sale`**. It is a manual data-entry screen sitting beside the till.

It is a statutory running-balance record. Asking a pharmacist to dispense a
controlled drug and then separately retype it into another screen guarantees the
register disagrees with the stock, and the register is the legal document.

### R5 — Promotions are stored and never applied

`POSPromotion` is never referenced in `apps/retail/services.py`. Campaigns, coupon
codes, BOGO bundles and min-spend thresholds can all be configured, and **no
checkout ever consults them**.

This is the same defect shape as the old `Budget.actual_amount`: a feature that
exists as data with no engine behind it, so the screen implies a capability the
system does not have.

### R6 — Retail sales are never fiscalised

`complete_sale` posts the journal and generates a receipt. It never creates a
`TaxRecord` — the EBM record, with SDC id, MRC number and the RRA QR payload.

EBM fiscalisation is a legal requirement for Rwandan retail. The model is built and
the till does not call it.

### R7 — Dispensing does not touch the prescription

`Dispensing.prescription_reference` is a `CharField` — free text, with no foreign
key to `Prescription` anywhere.

So dispensing never decrements a refill counter, never advances a prescription's
status, and never records which sale filled it. One script can be dispensed
against indefinitely; the lifecycle the model describes cannot happen.

*(Correction: the first draft of this said the field was on `SaleItem`. It is on
`Dispensing`. The defect is the same, the fix lands in a different place.)*

### R8 — Every screen is on the pre-standard pattern

| Screen | Lines | DataGrid | `<table>` | `<Modal>` |
|---|---|---|---|---|
| PosPage | 770 | 0 | 0 | 3 |
| ClinicalServicesPage | 354 | 0 | 2 | 2 |
| ControlledSubstancesPage | 247 | 0 | 1 | 1 |
| PrescriptionsPage | 230 | 0 | 1 | 1 |
| PromotionsPage | 217 | 0 | 1 | 1 |

---

## 2. Plan

Logic before appearance, for the same reason as the finance redesign: a faster
screen over a till that cannot scan, cannot work offline and does not write the
statutory register is a worse product, not a better one.

| # | Work | Gate |
|---|---|---|
| **R-A** | **Scan + keyboard till.** Barcode resolution against `ProductBarcode`, scanner-as-keyboard capture, F-key tender, Enter to complete, focus management | A sale can be rung up end to end without a mouse |
| **R-B** | **Offline-first counter.** Queue completed sales in IndexedDB, sync on reconnect, idempotent server-side so a replay cannot double-sell | Pull the network mid-sale and the till keeps trading |
| **R-C** | **Wire the logic `complete_sale` skips.** Controlled register written automatically, EBM `TaxRecord` created, promotions applied at checkout, prescription linked and refills decremented | Each has a test proving the till, not a human, records it |
| **R-D** | **Rebuild the five screens** on `DataGrid` + `RecordKit`, and the POS on a till layout rather than a form | No `<Modal>`, no hand-rolled `<table>` left in retail |

---

## 3. Progress log

- **2026-08-07** — Audit run against the code: no scan handling (R1), no key handlers
  (R2), no offline anything (R3), `ControlledSubstanceRegister` absent from
  `complete_sale` (R4), `POSPromotion` absent from services (R5), no `TaxRecord` on
  sale (R6), `prescription_reference` is free text (R7).

- **2026-08-07 — R-C shipped (the logic the till skipped).** `apps/retail/counter.py`,
  called from `complete_sale`, each piece idempotent on the sale.
  - **Controlled register** written by the till, with the running balance reconciled to
    physical stock. **A bug the tests caught:** the register is written *after* FEFO has
    already deducted, so opening a new register at current on-hand and then subtracting
    the quantity again understated it by exactly the first dispensing. A product with no
    register history now takes the physical on-hand as its closing balance.
  - **EBM fiscalisation** on every completed sale. `TenantSettings` gained `ebm_sdc_id`
    and `ebm_mrc_number` — they did not exist, and the first draft read them through
    `getattr(..., "")`, which would have stamped "UNREGISTERED" on every receipt forever
    without anyone noticing. An unregistered till still sells (refusing would close the
    shop) but gets no QR, because a verification link that resolves to nothing is worse
    than none.
  - **Promotions** evaluated at checkout — percentage, flat and BOGO, with effective
    dates and minimum spend enforced, capped so a discount can never exceed the basket.
    Every rejection carries a reason: *"expired on 30 June"*, *"spend 3,000 more"*. A till
    that silently ignores a coupon the customer is holding starts an argument.
  - **Prescriptions** linked by a real FK (`Dispensing.prescription`), with the refill
    counter decremented and the script moved to FULFILLED on its last fill.
  - 21 tests.

- **2026-08-07 — model completeness audit (asked for alongside the screen work).**
  Four gaps, each one a screen sitting on data that could not support it:

  | # | Gap | Why it mattered |
  |---|---|---|
  | **M1** | `Sale` had no `discount_amount` or `promotion` | The promotion engine computed a discount with nowhere to put it. Every basket charged full price however many coupons were configured. |
  | **M2** | No `PrescriptionItem` | A prescription recorded the patient, prescriber and refill count but **not the medicine**. Nothing could check that what was dispensed matched what was written, a script could not be part-filled, and the screen could not show the pharmacist what to hand over. |
  | **M3** | `ClinicalServiceRecord` had `fee_charged` and no link to a sale or the ledger | Vaccinations, screenings and consultations were **billed and never banked**. `4300 Services Revenue` — an account created for exactly this — had never been used. |
  | **M4** | `POSPromotion` had no redemption tracking | A coupon could be redeemed for ever. No cap, no count. |

  All four closed, with `Sale.total` now netting the discount (`gross_total` keeps the
  pre-discount figure) and redemption counted **at completion, not application**, so an
  abandoned or voided basket does not burn one of a limited coupon's uses.
  Clinical fees post `Dr 1100 Cash / Cr 4300 Services revenue`, idempotent per encounter.
  **Two bugs the tests caught**, and the second was serious:
  - The new `total` handed `_money()` the field default `0` — an int, which cannot be
    quantized — so every unsaved `Sale` raised. Coerced.
  - **Netting the discount into `total` broke the ledger.** The till debited the
    discounted amount (1,800) and still credited full revenue (2,000), so *any*
    discounted sale failed to post: `Journal entry does not balance`. Fixed with a
    `4900 Discounts Allowed` contra-revenue account, and the discount split back across
    net and VAT in proportion — **VAT is due on the consideration actually received**, so
    charging it on the pre-discount amount would have overstated output VAT on every
    promotion, and that figure is filed with the RRA.

- **2026-08-07 — R-D part one (four screens rebuilt).** On `DataGrid` + `RecordKit`,
  each one surfacing the thing its domain actually turns on rather than listing rows:
  - **Controlled drugs register** — current running balance per product at the top, with
    the note that it must equal what is in the cabinet and a difference is a discrepancy
    to investigate, not a number to correct. Manual entry is scoped to receipts and
    witnessed disposals, since dispensing is now written by the till.
  - **Promotions** — status is computed from today (`Live`, `Scheduled`, `Expired`,
    `Fully redeemed`) rather than read off the `is_active` flag, because a promotion can
    be switched on and out of date, which is exactly how a dead coupon keeps being
    offered. Redemption progress against the cap is shown.
  - **Prescriptions** — the new line items are editable on creation and shown as
    dispensed-vs-prescribed with what is still owed, so a part-fill is legible. Scripts
    past their expiry are flagged as lapsed even while the stored status still reads
    ACTIVE.
  - **Clinical services** — encounters and the service catalogue in one screen, with an
    explicit banner for money **performed and not yet taken to the ledger**, and a
    one-click "take payment" that posts it to `4300`.
  - Counter API added: `/api/retail/counter/` with `scan`, `promotions`,
    `apply-promotion`, `clear-promotion` and `bill-clinical-service`.

- **2026-08-07 — R-A, R-B and R-D part two (the counter itself).**
  - **The POS is a till now, not a form.** The scan field is the home position and
    everything that steals focus gives it back, because the next scan otherwise lands in
    the wrong box. A scanner is a keyboard that types fast and presses Enter, so Enter in
    that field resolves the barcode and adds the line — and a **carton barcode adds the
    carton**, not one tablet, which is the difference between correct pricing and
    undercharging by the case. F2/F3/F4 tender cash, mobile money and card to the exact
    outstanding amount; F8 clears; F9 pays. A sale can be rung up end to end without a mouse.
  - **Offline-first (R-B), closing the gap `docs/19` §2 has described since the start.**
    A completed sale is written to IndexedDB **first and sent second** — the other order
    loses sales. Each carries a till-generated `client_reference`; `Sale` gained that field
    with a per-org unique constraint, and `/api/retail/offline/sync/` treats a repeat of a
    key as a no-op returning the original. Without it the server cannot tell a replay from
    a second customer buying the same thing, so a flaky connection would deduct the stock
    and charge the customer twice.
    The queue drains on reconnect *and* on a 30-second timer, because the browser's
    `online` event fires when the interface comes up, not when the server is reachable.
    A sale that cannot be replayed is kept and its error recorded rather than dropped —
    it is money that left the shelf and needs a person.
    Connection state and queue depth are always on screen: a cashier must not have to go
    looking to find out the till is holding sales.
  - **Retail overview** gained a *counter readiness* panel — is a drawer open, is anything
    held offline, is there clinical work performed and never banked, are there prescriptions
    past their expiry still marked active. The tiles above it report yesterday; this
    answers whether the shop can trade today.

- **2026-08-07 — live HTTP walkthrough. It found three bugs the 600-test suite did not.**

  | # | Bug | Why the tests missed it |
  |---|---|---|
  | 1 | **A failed replay reported success forever.** Any existing `Sale` row short-circuited the idempotency check, so a replay that could not complete (no pharmacist on shift) left a row holding the key and every retry returned `replayed: true` for a sale that never happened. The till would drop it from the queue and **the sale would vanish** — worse than the double-sell the key exists to prevent. | The unit tests only exercised the success path. |
  | 2 | **`sale_number` is unique with a blank default**, so the second offline sale collided on the constraint. `SaleViewSet` assigns `SALE-{pk:06d}` after create; the offline endpoint never did. | Only one offline sale was ever created in a test. |
  | 3 | **Every successful scan 500'd** — `PharmacyProduct` was imported from `catalog`; it lives in `inventory`. The price field is `retail_price`, not the `selling_price` a `getattr` fallback was silently swallowing. | The first walkthrough only scanned an *unknown* barcode, which returns before that line. |

  Fixed: only a **COMPLETED** sale short-circuits a replay, and a failed one is kept OPEN
  and marked `retryable` so it can be replayed once the reason is fixed; offline sales are
  numbered on create; the scan import and price field read the real thing.
  Four regression tests pin all three.

  Verified live: 25/25 endpoint calls, and the replay contract end to end — three replays
  of one queued sale produce **one** sale and deduct stock **once**; three replays of a
  sale that cannot complete return 400 every time, never claim success, and move no stock.

**R-A, R-B, R-C and R-D delivered and verified over the wire.** Still not done: rendering
the screens in an actual browser. Focus management, the F-key handlers and IndexedDB are
exactly the class of thing that typechecks and misbehaves visually.
