# PharmaCore — API Design

> REST API surface across modules, conventions, and the offline sync endpoints.
> Endpoint list is indicative (v1) and traces to the SRS functional requirements.
>
> Version 0.1 · 2026-08-03

---

## 1. Conventions
- **Style:** REST/JSON over HTTPS. Base path `/api/v1`.
- **Auth:** `Authorization: Bearer <JWT>`. Token from `POST /auth/login`; refresh via `POST /auth/refresh`.
- **Tenancy:** organization derived from the token; cross-org access requires explicit permission and is checked server-side.
- **IDs:** UUIDs (client-mintable for offline resources).
- **Pagination:** cursor-based — `?limit=&cursor=`; responses include `next_cursor`.
- **Filtering/sorting:** `?filter[field]=&sort=-created_at`.
- **Idempotency:** mutations accept `Idempotency-Key` header (required for POST sale/payment) → safe retries.
- **Errors:** RFC-7807 problem+json: `{ "type", "title", "status", "detail", "errors": [...] }`.
- **Versioning:** URL-versioned (`/v1`); additive changes only within a version.
- **Audit:** all mutations recorded server-side in `audit_log`.

---

## 2. Auth & IAM
```
POST   /auth/login                 → tokens
POST   /auth/refresh               → new access token
POST   /auth/logout
GET    /me                         → current user + roles + permissions

GET    /organizations              POST /organizations
GET    /organizations/{id}         PATCH /organizations/{id}
GET    /organizations/{id}/departments   POST .../departments
GET    /users     POST /users      PATCH /users/{id}   POST /users/{id}/suspend
GET    /roles     POST /roles      PUT  /roles/{id}/permissions
GET    /licenses  POST /licenses   GET  /licenses/expiring?days=30
GET    /audit-log?entity_type=&entity_id=&user_id=
```

## 3. Catalog
```
GET    /products?search=&form=&rx=            (live-search for POS)
POST   /products      GET /products/{id}      PATCH /products/{id}
GET    /products/{id}/ingredients   POST .../ingredients
GET    /products/{id}/barcodes      POST .../barcodes
GET    /manufacturers   POST /manufacturers
GET    /suppliers       POST /suppliers
GET    /interactions?ingredient_a=&ingredient_b=
```

## 4. Inventory
```
GET    /inventory/batches?product_id=&expiring_before=&status=
POST   /inventory/intake            (supplier intake → batches + EBM purchase)
GET    /inventory/fefo?product_id=  (FEFO-ordered sellable batches)
POST   /inventory/adjustments       (physical count correction; needs approval)
POST   /inventory/wastage
GET    /inventory/recall?batch_number=   (where is batch X — all orgs/sales)
POST   /inventory/transfers         (internal department transfer)
GET    /inventory/movements?product_id=&from=&to=
GET    /inventory/alerts            (low stock / near expiry / cold chain)
```

## 5. Distribution (B2B)
```
GET    /depots/{id}/catalog?search=        (FEFO-sorted depot stock for retail)
POST   /orders                              (retail places PO)
GET    /orders?status=   GET /orders/{id}
POST   /orders/{id}/approve                 (depot allocates+reserves batches)
POST   /orders/{id}/pick
POST   /orders/{id}/cancel
POST   /shipments                           (assign orders, vehicle, driver, stops)
POST   /shipments/{id}/dispatch             (→ delivery note/waybill; deduct depot)
POST   /shipments/{id}/temperature          (cold-chain log)
POST   /grns                                (open GRN from a delivered order)
POST   /grns/{id}/lines                     (counts vs manifest)
POST   /grns/{id}/finalize                  (→ retail stock in; invoice; immutable)
POST   /grns/{id}/discrepancies
```

## 6. Documents
```
GET    /documents?type=&reference_id=
GET    /documents/{id}              (metadata + signed file URL)
POST   /documents/generate          (enqueue generation; returns job id)
GET    /documents/verify/{qr_token} (public-ish QR verification)
```

## 7. Retail POS
```
POST   /pos/drawers/open            POST /pos/drawers/{id}/close
POST   /pos/sales                   (create sale; Idempotency-Key required)
POST   /pos/sales/{id}/items
POST   /pos/sales/{id}/route-insurance   (policy no → compute copay)
POST   /pos/sales/{id}/payments
POST   /pos/sales/{id}/complete
POST   /pos/sales/{id}/void
GET    /pos/prescriptions/{id}      POST /pos/prescriptions/{id}/verify
GET    /pos/interactions/check      (basket + patient history)
```

## 8. Insurance
```
GET    /insurance/schemes   POST /insurance/schemes
GET    /insurance/schemes/{id}/formulary   PUT .../formulary
POST   /insurance/agreements               (org ↔ scheme)
GET    /insurance/claims?status=           (claims queue)
POST   /insurance/claims/{id}/adjudicate   (approved amount + copay)
POST   /insurance/manifests                (group + submit periodic)
GET    /insurance/receivables/aging
```

## 9. EBM
```
GET    /ebm/config     PUT /ebm/config     (provider: OSDC/VSDC/MOCK, credentials)
POST   /ebm/sales/{sale_id}/fiscalize      (usually worker-driven; manual retry)
POST   /ebm/items/register
POST   /ebm/purchases/register
GET    /ebm/receipts/{sale_id}
GET    /ebm/errors                          (failed → retry queue)
```

## 10. HR & Payroll
```
GET    /employees   POST /employees   PATCH /employees/{id}
POST   /attendance/clock-in   POST /attendance/clock-out
GET    /attendance?employee_id=&from=&to=
POST   /leave-requests   POST /leave-requests/{id}/approve
GET    /shifts   POST /shift-assignments
GET    /statutory-rates   PUT /statutory-rates          (versioned config)
POST   /payroll/runs   POST /payroll/runs/{id}/calculate
POST   /payroll/runs/{id}/approve   GET /payroll/runs/{id}/payslips
GET    /payroll/runs/{id}/remittance-file
```

## 11. Finance
```
GET    /accounts   POST /accounts            (chart of accounts)
POST   /journal-entries                      (must balance; else 422)
POST   /journal-entries/{id}/post
POST   /journal-entries/{id}/reverse         (no edit — reversing entry)
GET    /fiscal-periods   POST /fiscal-periods/{id}/close
GET    /reports/receivables   GET /reports/expenses
```

## 12. Reporting
```
POST   /eod/start   POST /eod/{id}/count-drawer   POST /eod/{id}/lock
GET    /reports/{report_key}?org=&from=&to=   (supplier-perf, expiry-forecast,
        stock-valuation, order-fill-rate, cash-reconciliation, aging-receivables,
        ebm-reconciliation, dispensed-medication-log, labor-cost)
GET    /dashboards/summary?org=
GET    /notifications   POST /notifications/{id}/read
```

## 13. Offline sync API (the critical one)
```
POST   /sync/devices/register        → device token + last_seen watermark
POST   /sync/push                     (batch of outbox events; idempotent)
        body: [{ event_id, entity_type, entity_id(UUID), operation, payload,
                 client_created_at }]
        resp: [{ event_id, status: ACKED|CONFLICT, conflict?: {...} }]
GET    /sync/pull?since=<watermark>   → catalog/pricing/stock deltas for device
GET    /sync/conflicts                 POST /sync/conflicts/{id}/resolve
```
Push is **idempotent** by `(device_id, event_id)`; the server replays stock
movements and returns per-event ACK or CONFLICT (e.g. OVERSELL).

---

## 14. Standard error codes
| HTTP | Meaning (PharmaCore) |
|---|---|
| 400 | malformed request |
| 401 / 403 | not authenticated / lacks permission (RBAC) |
| 409 | conflict (e.g. oversell, duplicate document number) |
| 422 | validation (e.g. unbalanced journal, negative stock, expired-license dispense) |
| 423 | locked (posting into a locked fiscal period / closed day) |
| 503 | external dependency down (EBM/insurer) — client should queue & retry |
