# Platform Architecture Decisions (research-backed)

The build‑shaping technical decisions and the data‑model gaps a builder must resolve.
Where research informs a choice it's cited; each ends with a **decision** (a sensible
default to confirm).

---

## 1. Deployment & tenancy
**How it's done (2026 best practice):** the default for a multi‑tenant SaaS is a
**shared schema (Pool) database + PostgreSQL Row‑Level Security (RLS)** as a safety
net — it scales to thousands of tenants with the lowest operational overhead.
**Non‑negotiable rule:** every tenant‑specific table has a **`tenant_id`**, and *all*
data access filters by it; cross‑tenant leaks come from a **single missed filter** (a
query or a background worker running without tenant context). **RLS moves that filter
into the database** so the engine blocks what the code misses.

**Where we are:** PharmaCore already enforces tenant scoping at the **application
layer** (`organizations_visible_to`). What's missing is the **DB‑level safety net**.

**Decision:** **central multi‑tenant SaaS, shared schema, org‑scoped**, and **add
PostgreSQL RLS** on tenant tables as the safety net (Postgres is already our prod DB).
A **very large chain** can be given its own database (silo) if it demands isolation.
Combined with **data residency** ([doc 18 §4](18-rwanda-integrations-and-statutory.md)),
host **in Rwanda** (or hold an NCSA offshore certificate).

## 2. Offline‑first at the counter (Retail POS)
**How it's done:** **local SQLite + the outbox pattern + a background sync worker =
zero data loss.** A durable **outbox queue** (`SyncQueueItem`) holds each local change;
a **SyncWorker** pushes pending items **in order**, marks acknowledged ones SYNCED, and
**retries** failures. Each event carries a unique **idempotency key** so a retried push
is applied **exactly once** server‑side. Concurrent edits resolve by **Last‑Write‑Wins**
(timestamp/version), with merge or manual strategies where LWW is unsafe.

**Decision (Phase 3 remainder):** **Tauri desktop** wrapping the React POS + **encrypted
local SQLite**; an **outbox + idempotency‑key** sync API (**push** local sales/returns,
**pull** catalog/price/stock deltas); **oversell reconciliation** on the server (the
authoritative FEFO check re‑runs on sync — a sale made offline against stale stock is
flagged/adjusted, never silently oversold). Money/stock events are **append‑only**, so
sync is replay‑safe.

## 3. Access control — from coarse roles to a permission matrix
**Where we are:** RBAC exists but is coarse (SYS_ADMIN / ORG_ADMIN / PHARMACIST /
CASHIER) — the UI mostly distinguishes "admin vs not."
**Target:** a **permission matrix** = `permission = resource × action`, roles are
**bundles of permissions**, checks are per‑permission (not per‑role). Least‑privilege.

Indicative roles → scope (full matrix built with the modules):
| Role | Can (summary) |
|---|---|
| **Cashier** | POS sell/return, own drawer; no pricing, no admin |
| **Pharmacist** | + dispense Rx/controlled, verify online Rx, counsel, catalog view |
| **Pharmacy technician** | + stock counts, intake support (depot), receive |
| **Warehouse/Storekeeper** | put‑away, picking, transfers, quarantine |
| **Procurement officer** | supplier POs, imports, supplier invoices |
| **Finance officer** | AP/AR, payments, reconciliation, reports; no dispensing |
| **HR officer** | employees, payroll, leave, training; no stock/finance |
| **Branch manager** | approvals for their branch, branch dashboards |
| **HQ executive** | all branches (read + high‑level approvals), consolidation |
| **System admin** | tenant config, users/roles, everything |

**Decision:** introduce a `Permission` catalogue + `Role→Permission` mapping; keep the
current role names as seed bundles; gate every action by permission. Feeds the
**approval engine** (who may approve what, [doc 12 §4](12-requirements-fields-documents-approvals.md)).

## 4. Data‑model gaps to add (first‑class entities we still lack)
- **Customer / Patient** — required by OTC counselling, insurance, online, loyalty:
  name, national ID/passport, DOB, gender, phone, address, **allergies**, **chronic
  conditions/notes**, **insurer + member/card number + policy tier**, loyalty id, and
  **consent** (per [doc 18 §4](18-rwanda-integrations-and-statutory.md)). Walk‑in stays
  anonymous; registered patients unlock interaction checks & claims.
- **Prescriber / Doctor** — for prescriptions & the controlled‑drug register: name,
  **professional licence no. + issuing council**, facility, contact.
- **Prescription** — link patient + prescriber + items + image/upload + verification
  status (used by dispensing gate & Online).
- **Warehouse structures** — `StorageZone` (ambient / **2–8 °C** / −20 °C…) + `Bin/
  Location` + optional **temperature‑log device**; put‑away by product storage
  condition ([doc 14 §4](14-international-operational-standards.md)).
- **OrganizationDocument / UserDocument / EmployeeProfile** — per the completeness spec
  ([doc 12](12-requirements-fields-documents-approvals.md)), with the **Rwanda required
  sets** ([doc 13](13-regulatory-licensing-and-documents-rwanda.md)).

## 5. Money, localisation, retention (small but must-decide)
- **Currency/rounding:** internal money keeps 2 decimals (cost precision); **customer‑
  facing amounts round to whole RWF** (francs are used without cents in practice).
- **Localisation:** **UI in English**; **patient‑facing** output (receipts, SMS, the
  online store) available in **Kinyarwanda + French** too (Rwanda is trilingual).
- **Retention & e‑signatures:** keep an explicit **retention policy** per document type
  (fiscal/GDP records often ≥ 5–10 years); **approval decisions are e‑signed** (actor +
  timestamp + immutable audit) — sufficient for internal authorisation; legally‑binding
  external signatures (contracts) go through the document engine.

## 6. Assets & external prerequisites (not code — must be procured/decided)
- **Brand SVGs** for PharmaCore + each subsystem tile (spec exists in
  [design/02](design/02-brand-and-logo-system.md); files don't) — *can be generated.*
- **EBM (OSDC) onboarding, MoMo/Airtel merchant + API access, SMS + card gateway,
  RSSB claim channel** — external applications with lead time ([doc 18](18-rwanda-integrations-and-statutory.md)); build against **mocks** meanwhile.
- **Pilot partner** (one depot + one retail/chain) for validation.
- **Seed data**: Rwanda FDA **registered‑products list** + **ATC** codes to seed the
  catalog; Rwanda locations already seeded.

---

### Sources
- Multi‑tenancy / RLS: [Clerk – multi‑tenant SaaS design](https://clerk.com/blog/how-to-design-multitenant-saas-architecture), [Microsoft Learn – multitenant SaaS patterns](https://learn.microsoft.com/en-us/azure/azure-sql/database/saas-tenancy-app-design-patterns?view=azuresql), [DZone – RLS multi‑tenant](https://dzone.com/articles/multi-tenant-data-isolation-row-level-security)
- Offline‑first / outbox / conflict: [SaleFlex – offline‑first POS](https://saleflex.dev/offline-first-pos/), [EDUCBA – offline‑first outbox/idempotency](https://www.educba.com/offline-first/), [Sachith – offline sync & conflict patterns (2026)](https://www.sachith.co.uk/offline-sync-conflict-resolution-patterns-architecture-trade%E2%80%91offs-practical-guide-feb-19-2026/)
</content>
