# PharmaCore — System Architecture

> High-level design, component structure, the offline-first deep dive, tech-stack
> rationale, deployment, and trade-offs. Follows the system-design framework.
>
> Version 0.1 · 2026-08-03

---

## 1. Context & goals
Deliver one system spanning wholesale distribution, retail POS, compliance, and
HR/finance for Rwandan pharmacies. Hard drivers (from [01-key-decisions.md](01-key-decisions.md)):
- **Offline-capable retail POS** (sell without internet, sync later).
- **Multi-insurer** claims with configurable coverage.
- **RRA EBM** fiscalization behind a swappable provider.
- **Immutability & audit** for GDP/tax compliance.
- Small team, phased delivery → favour **simplicity over premature microservices**.

---

## 2. Architecture style — Modular Monolith + Offline Clients

**Decision:** A single deployable **modular monolith** backend (FastAPI) with
clear internal module boundaries, one PostgreSQL database, background workers for
async work, and an **offline-first desktop client** for the POS.

**Why not microservices (yet):** the team is small, the modules share a tightly
coupled core (inventory ↔ orders ↔ sales), and distributed transactions across
services would add cost with little early benefit. Boundaries are enforced *in
code* (module packages) so extraction later is cheap if needed.

```
                     ┌────────────────────────────────────────────┐
                     │                 CLIENTS                      │
   Back-office web ──┤  React web app (depot, HR, finance, admin)   │
   Retail counter  ──┤  Desktop POS (Tauri/Electron) + LOCAL DB     │──┐ offline
                     └────────────────────────────────────────────┘  │ outbox
                                     │ HTTPS (REST/JSON, JWT)         │
                                     ▼                                │
                     ┌────────────────────────────────────────────┐  │
                     │            API Gateway / Backend             │◄─┘ sync API
                     │              (FastAPI monolith)              │
                     │                                              │
                     │  iam · catalog · inventory · distribution ·  │
                     │  documents · retail · insurance · ebm ·      │
                     │  hr · finance · reporting · sync             │
                     └───────┬───────────────┬───────────────┬──────┘
                             │               │               │
                     ┌───────▼─────┐  ┌──────▼──────┐  ┌─────▼───────────┐
                     │ PostgreSQL  │  │ Task queue  │  │ Object storage  │
                     │ (source of  │  │ (Celery/RQ  │  │ (S3-compatible, │
                     │  truth)     │  │ + Redis)    │  │  immutable docs)│
                     └─────────────┘  └──────┬──────┘  └─────────────────┘
                                             │ workers
              ┌──────────────────────────────┼───────────────────────────┐
              ▼                ▼              ▼             ▼              ▼
        PDF worker      EBM worker      Claims worker   Notify worker   Sync worker
       (WeasyPrint)   (EbmProvider)   (manifests)     (SMS/email)    (reconcile)
                           │
                    ┌──────▼───────┐   ┌──────────┐   ┌──────────┐
                    │ RRA EBM      │   │ Insurers │   │ Momo/SMS │  external
                    │ (OSDC/VSDC)  │   │          │   │          │
                    └──────────────┘   └──────────┘   └──────────┘
```

---

## 3. Components

| Component | Responsibility |
|---|---|
| **Backend (FastAPI)** | REST API, business logic, module packages, RBAC, audit |
| **PostgreSQL** | Single source of truth; ACID for stock transfers & journals |
| **Task queue (Celery/RQ + Redis)** | Async: PDF generation, EBM fiscalization, claim manifests, notifications, sync reconciliation |
| **Object storage (S3-compatible)** | Write-once document PDFs + content hash |
| **Web app (React)** | Back-office UIs (depot, distribution, HR, finance, admin, reporting) |
| **Desktop POS (Tauri/Electron)** | Retail counter; **local datastore (SQLite)**; offline sell + outbox |
| **Sync service** | Reconcile offline outbox → server; detect/raise conflicts |
| **Adapters** | `EbmProvider`, `InsurerClient`, `SmsClient`, `MomoClient`, `StorageClient` — all mockable |

**Module boundaries (backend packages):** `iam, catalog, inventory, distribution,
documents, retail, insurance, ebm, hr, finance, reporting, sync`. Cross-module
calls go through service interfaces, not direct table reads.

---

## 4. Data flow (two canonical paths)

**B2B transfer (online):** Retail PO → depot approve (reserve batch, ACID txn) →
dispatch (deduct depot, generate docs async) → GRN finalize (insert retail stock,
ACID txn, generate invoice async) → journals posted.

**Retail sale (offline):** POS local txn (deduct local batch, save sale UUID,
enqueue outbox) → [reconnect] → sync API upserts sale server-side → EBM worker
fiscalizes (retry) → claim worker tracks insurance → reporting reads server truth.

---

## 5. Offline-first deep dive (ADR-001)

The single most important architectural piece.

**Local datastore.** The POS device runs an embedded DB (SQLite) holding a
**working subset**: its branch catalog, retail pricing, its own on-hand batches,
open drawer, and unsynced sales.

**ID strategy.** All client-created records use **UUIDv4/v7 minted on the device**.
No offline record ever waits for a server-assigned number. Human-facing document
numbers that must be gapless (EBM receipt no.) are assigned **server-side at
fiscalization**, after sync — the local receipt shows a provisional/pro-forma id.

**Outbox pattern.** Every offline mutation (sale, payment, stock deduction,
claim intent) is appended to `sync_outbox` as an ordered event. A background sync
worker on the device pushes events when online; the server acknowledges each.

**Stock contention (the hard part).** Two offline terminals can both sell the last
pack of a batch. Mitigations, in order:
1. **Soft allocation:** optionally pre-allocate batch quantity per terminal at
   start of day so offline sells draw from a private pool.
2. **Server reconciliation:** on sync, the server replays movements; if a batch
   would go negative it records the sale but raises a `sync_conflict = OVERSELL`
   for a manager to resolve (matches the physical-count-mismatch guardrail). Sales
   are never silently dropped — money was taken.
3. **Idempotency:** sync is idempotent by record UUID + event id, so retries don't
   double-apply.

**Conflict types:** `OVERSELL` (stock), `STALE_UPDATE` (price/catalog changed
server-side while offline). Resolution is logged in `sync_conflicts` with
server/device state snapshots.

**Consistency model:** central PostgreSQL is authoritative; devices are eventually
consistent. EBM/insurance were already async, so offline merely widens the queue
window — no new consistency class is introduced for them.

---

## 6. Tech stack & rationale

| Layer | Choice | Rationale | Trade-off |
|---|---|---|---|
| Backend | **Python 3.12 + FastAPI** | Async, typed (Pydantic), fast to build, great for the doc/EBM workers | Less raw throughput than Go/Java — fine at this scale |
| ORM/migrations | **SQLAlchemy 2.0 + Alembic** | Mature, explicit, versioned schema | Verbosity |
| DB | **PostgreSQL 16** | ACID for transfers/journals, JSONB, partitioning, strong integrity | Ops overhead vs. managed service (use managed) |
| Async | **Celery/RQ + Redis** | Decouple PDF/EBM/claims/notify from request path | Extra moving part |
| Docs | **WeasyPrint (HTML→PDF)** | Clean template-driven PDFs, easy layout changes | CPU-bound → run in worker |
| Web | **React + TypeScript** | Ecosystem, hiring, component reuse | SPA complexity |
| Desktop POS | **Tauri (preferred) / Electron** | Wrap the web app; local SQLite; smaller footprint (Tauri) | Native build/signing effort |
| Storage | **S3-compatible + object-lock** | Write-once immutability for legal docs | Vendor choice |
| AuthN | **JWT (OAuth2 password flow)** | Standard, stateless, works offline-then-sync | Token rotation care |

---

## 7. Deployment topology
- **Central:** backend + workers (containers), managed PostgreSQL, Redis, object
  storage — one region (Rwanda/EU) with daily encrypted backups + PITR.
- **Branch:** desktop POS per counter; back-office via browser.
- **Environments:** dev (SQLite/mock EBM) → staging (mock/sandbox RRA) → prod
  (certified EBM). CI runs migrations + tests; feature flags gate new modules.

---

## 8. Scale & reliability
- **Load:** dominated by retail sale writes and stock movements; both append-heavy
  → index by `(organization_id, product_id, batch_number)` and time-partition
  `stock_movements`, `retail_sales`, `audit_log`.
- **Failover:** managed PG with replica + PITR; workers idempotent & retried;
  external outages (EBM/insurer/momo) degrade gracefully via queue.
- **Observability:** structured logs, request tracing, worker dashboards, alerts
  on EBM error rate, sync backlog, drawer variance.

---

## 9. Trade-offs & what we'll revisit
- **Monolith → services:** revisit if a module (e.g. EBM or distribution) needs
  independent scaling or a separate team; boundaries already isolate them.
- **Offline scope:** POS is offline-first; back-office is online-only (acceptable —
  managers can wait). Revisit if depots also need offline.
- **Drug-interaction data:** start basic (duplication/same-ingredient), revisit a
  licensed clinical dataset when clinical safety scope grows.
- **Sync engine:** custom outbox now; revisit an off-the-shelf sync framework
  (e.g. ElectricSQL/PowerSync) if device count grows large.

---

## 10. Related documents
[03-srs.md](03-srs.md) · [02-data-model.md](02-data-model.md) ·
[06-workflows-state-machines.md](06-workflows-state-machines.md) ·
[07-api-design.md](07-api-design.md) · [08-security-and-compliance.md](08-security-and-compliance.md)
