# Distribution redesign — the wholesale marketplace

**Status:** in progress · **Date:** 2026-08-07

## What distribution is for

A wholesale pharmacy publishes what it is willing to sell. Retail pharmacies see
that storefront and order from it. Two things follow that the current build does
not do:

1. **The wholesaler decides what to show.** It may hold 5,000 units and publish
   800, or hold stock and publish nothing. Withholding is a first-class operation,
   not an accident of low stock.
2. **Demand can precede supply.** A retailer orders something the depot does not
   stock. That order is not a failure — it is the demand signal the depot imports
   against. Today it is refused and lost.

Everything below is measured against those two sentences.

## Defects found

Each was verified against the code, not assumed.

| # | Defect | Evidence |
|---|--------|----------|
| **D1** | **The storefront governs nothing.** Order pricing reads `PharmacyProduct.wholesale_price` from *inventory*. `DepotProductListing` — the marketplace record carrying price, offered qty, buffer, min order qty, segment and `is_published` — is never consulted at order time. Two competing "what the depot offers" concepts exist and ordering uses the wrong one. | `serializers.py:199-207` |
| **D2** | **`available_for_order` ignores physical stock.** It returns `offered_qty - buffer_qty` and never looks at a batch. A depot can publish 10,000 units it does not hold, and nothing reconciles the two. | `models.py:285-287` |
| **D3** | **The depot can reserve and ship expired stock.** `_reserve_item` filters `status=ACTIVE` only. Retail's `_fefo_consume` filters `expiry_date__gte=today` with the comment "never sell expired stock". The till refuses expired goods; the depot ships them. | `services.py:150-156` vs `retail/services.py:85` |
| **D4** | **No way to order what the depot does not stock.** No backorder, indent or demand capture anywhere. An unmet line is rejected outright, so the depot never learns what its customers wanted. The import engine has no demand input. | no such model |
| **D5** | **Tender contracts are decorative.** `contract_price`, `total_committed_qty`, `drawn_qty` are read by no service. An awarded price is never applied to an order; drawn volume is never incremented. | `grep TenderContract services.py` → 0 |
| **D6** | **Customer returns produce nothing.** `credit_note_amount` is a number a human types. No restock, no credit note document, no ledger posting. | `grep CustomerReturn services.py` → 0 |
| **D7** | **`VanStock` has no API and no service.** Zero views, zero services. Field sales cannot load a van, sell from it, or reconcile it. | 0 views / 0 services |
| **D8** | **Reps, journey plans and visit logs are CRUD only.** `monthly_sales_target` and `commission_rate_pct` drive no calculation. *(Correction: my first pass said visits link to no order. Wrong — `SalesVisitLog.order` and `sales_amount` both exist. The link is there; nothing reads it.)* | 0 services |
| **D9** | **Seven of nine screens are off-standard**, using raw `<table>` + modal instead of `DataGrid` + `RecordKit`. | see table below |

```
PurchaseOrdersPage        584 lines  grid=2 tbl=1     DepotListingsPage        218  grid=0 tbl=1
InstitutionalTendersPage  220 lines  grid=0 tbl=1     CustomerReturnsPage      184  grid=0 tbl=1
B2BOrderingPortalPage     169 lines  grid=0 tbl=0     FieldSalesPage           166  grid=0 tbl=1
DistributionHome          190 lines  grid=0 tbl=0     GrnPage 86 / InTransit 69  grid=2
```

D1–D4 are the marketplace. D5–D8 are models shipped without engines — the same
defect class as `Budget.actual_amount` and `POSPromotion` before those were fixed.

## What already exists and must be reused

`apps/procurement` is a complete, wired import engine: `PurchaseRequisition` →
`RequestForQuotation` → `SupplierQuote` → `PurchaseOrder` → `ImportConsignment` →
`GoodsReceipt` → `SupplierInvoice` → landed cost, with `consolidate_requisitions`
already collapsing many requisitions into one PO per supplier. **D4 needs a bridge
into it, not a new engine.**

## Phases

### D-A — Storefront engine (`marketplace.py`)

Available to promise is the only number the buyer may act on:

```
physical_free = Σ(quantity_available − quantity_reserved) over ACTIVE, unexpired batches
sellable      = max(0, physical_free − buffer_qty)   # buffer is held back for the depot
atp           = min(offered_qty, sellable)           # never promise beyond what is published
```

- `is_published=False` removes the product from the storefront entirely.
- `min_order_qty` and `customer_segment` are enforced, not advisory.
- **The listing price is authoritative**, superseded only by an active tender price.
- ATP is enforced at order creation, inside the same transaction as the credit check.

### D-B — Expiry guard

`_reserve_item` gains `expiry_date__gte=today`, matching retail. Pinned with a
regression test that stocks an expired batch and asserts it is never reserved.

### D-C — Demand-driven import (the bridge)

New `BackorderLine`: depot, retail, product, quantity, status
`OPEN → SOURCING → FULFILLED / CANCELLED`, with the originating order.

- A line that exceeds ATP, or names an unlisted product, is **captured as a
  backorder instead of being rejected** — the order proceeds with what is available.
- `demand_board(depot)` aggregates open backorders by product: total qty,
  distinct retailers, oldest request.
- `raise_requisition_from_demand(depot, products)` creates a
  `PurchaseRequisition` at the depot with a line per product, moves the
  backorders to `SOURCING`, and hands off to the existing procurement flow.
- When the import lands, `settle_backorders_for(product)` closes them.

### D-D — Returns engine

`approve_return` → inspect → restock accepted units into a batch at the depot →
issue a credit note document → post to the ledger. Rejected units never re-enter
saleable stock.

### D-E — Tenders

`resolve_contract_price` applied during order pricing; `drawn_qty` incremented on
dispatch; call-offs refused past `valid_until` or beyond `total_committed_qty`.

### D-F — Van stock & rep performance

Load/sell/return-to-depot van operations with a real API, and rep performance
computed from actual orders against target and commission rate.

### D-G — Screens

All nine on `DataGrid` + `RecordKit`, plus a storefront-shaped B2B ordering portal
showing ATP, min order qty, and a "request anyway" path that files a backorder.

## Method

Logic before UI. Every phase ships with tests. A live HTTP walkthrough at the end —
on this project it has caught bugs in every single phase that the unit tests missed.

## Found during the screen sweep (after the engine was built)

Auditing all twelve navigation entries for "wired and on standard" turned up three
more defects that no test covered:

| # | Defect | Evidence |
|---|--------|----------|
| **D10** | **The Goods Received Notes screen loaded nothing, ever.** Both `GrnPage` and the overview tile called `/api/distribution/grn/`; the route is `/grns/`. It 404'd silently — an empty grid looks identical to "no GRNs yet". | walkthrough |
| **D11** | **`?status=` was silently ignored.** The overview asked for `?status=PENDING` and got every order back, so "pending approval" was really the all-time total. An ignored filter is worse than a rejected one, because the number looks plausible. | walkthrough |
| **D12** | **The demand headline did not match the button.** `summary()` added OPEN and SOURCING demand into one figure, but sourcing only picks up OPEN — so the board advertised 1,745 units and then raised a requisition for 35. | walkthrough |

Also corrected: the B2B order builder read `PharmacyProduct` directly, so it showed
prices and quantities the server would not honour — it now reads the storefront,
the same authority the order is priced against.

Fixes: `/grns/` on both callers; `status`/`payment_status`/`depot`/`retail` filters
on `StockOrderViewSet` with a 400 on an unknown value; `units_open` vs
`units_sourcing` reported separately, with the tile bound to the actionable one.
All three are pinned by tests, including one that walks every endpoint the twelve
nav entries load.

### Screen status

| Screen | State |
|---|---|
| Distribution Overview | Rebuilt — storefront health, demand, returns, needs-attention panel |
| Depot Offered Listings | Rebuilt — publish/withhold, buffer, ATP vs on-hand |
| B2B Ordering Portal | Rebuilt — storefront with "request anyway" backorder path |
| Unmet Demand | New — demand board and one-click sourcing into procurement |
| Field Sales & Reps | Rebuilt — van manifest, performance vs target, commission |
| Customer Returns | Rebuilt — inspection, restock, credit note |
| Institutional Tenders | Rebuilt — `DataGrid`/`RecordKit`, drawdown and validity surfaced |
| B2B Purchase Orders | Repointed at the storefront; `DataGrid` already in place |
| Goods Received Notes | Endpoint fixed (was 404) — `DataGrid`, read-only registry |
| In-Transit Stock | Verified — `DataGrid`, read-only registry |
| Suppliers | Verified — `DataGrid` |
| Dashboard | The global app home, not distribution-specific — out of scope |

---

## Outcome

**Status: shipped.** Backend suite 660 passing (exit 0), 31 new tests, frontend
typecheck and build clean.

### The two offers, and which wins

Ordering used to price from `PharmacyProduct.wholesale_price` in *inventory*.
Making `DepotProductListing` the sole authority would have silently orphaned every
depot that never published one, so the resolution is an explicit hierarchy:

- **`DepotProductListing`** — the storefront offer. Carries price, offered quantity,
  buffer, minimum order, segment and publication state. **Supersedes everything.**
- **`PharmacyProduct.wholesale_price`** — the implicit legacy offer. Still honoured
  when no listing exists, but now capped by physical stock, which it never was.

Either way availability is `min(offered, free_unexpired_stock − buffer)`.

### What the walkthrough caught that 660 unit tests did not

1. **`?buyer=None` returned HTTP 500.** A stringified null reached the ORM and
   raised `ValueError`. Now absent reads as absent; only real garbage is refused.
2. **The second sourcing run crashed with `IntegrityError`.** `requisition_number`
   is unique with a blank default, so the first requisition was created with *no
   number at all* and the second collided on `""`. Now numbered through
   procurement's own gapless sequence. Identical to the `sale_number` collision
   found in retail — worth watching for anywhere a unique field has a blank default.

Both are pinned with regression tests.

### Verified end to end over HTTP

A depot holding 198 units published 30 with 10 held back. The buyer saw exactly 30
and could not see the 198. Ordering 100 placed 30 and captured 70 as demand. The
demand board aggregated it across buyers, and sourcing it produced a real
`PurchaseRequisition` (`PR-2026-00002`) that Procurement confirmed — with the second
attempt correctly refused. Cross-tenant writes returned 403 both ways. 18/18 calls.

### Screens

`B2BOrderingPortalPage` was **broken**, not merely dated — it posted
`supplier`/`lines`/`quantity_requested` to an API expecting
`depot`/`items`/`quantity_ordered`, so it can never have placed an order. Rebuilt as
a real storefront that shows availability before committing and separates "shipping
now" from "to be sourced" in the basket. `DepotListingsPage`, `CustomerReturnsPage`
and `FieldSalesPage` rebuilt on `DataGrid` + `RecordKit`; `DemandBoardPage` is new.

### Not done

- **The screens have not been rendered in a browser.** No browser tool is available
  in this environment. Typecheck, lint and production build pass, and every endpoint
  behind them is exercised over HTTP, but nothing visual is confirmed.
- `PurchaseOrdersPage`, `InstitutionalTendersPage`, `GrnPage`, `InTransitPage` and
  `DistributionHome` still use their existing patterns; the tender *engine* is wired
  (price lock and drawdown) but its screen does not yet surface contract balances.
