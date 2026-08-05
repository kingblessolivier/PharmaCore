# PharmaCore — Analysis, Design & Research Documentation

The document set for **PharmaCore by Medlink** — a pharmacy operations **workspace**
(a Google‑Workspace‑style suite of subsystems) serving **depots, single retail
pharmacies, and HQ+branch chains** in Rwanda. See the [ROADMAP](../ROADMAP.md) for the
subsystem map and current build status.

> **Reading order.** Docs **00–11** are the *foundational* analysis (written first);
> docs **12–19** are the *research‑backed completeness + decisions* layer (each cites
> its sources); the [design blueprint](design/12-application-blueprint.md) is the
> layout. Where they differ, **12–19 + the ROADMAP win** — the early docs are kept for
> history and carry an alignment note pointing forward.

### Foundational analysis (00–11)
| # | Document | What it answers |
|---|----------|-----------------|
| 00 | [Research findings](00-research-findings.md) | How existing systems (ERPs, PMS, GDP, RRA EBM, insurance) do this |
| 01 | [Key decisions (ADRs)](01-key-decisions.md) | The shaping choices (incl. ADR‑006 Django, offline‑first, multi‑insurer, EBM‑abstracted) |
| 02 | [Data model](02-data-model.md) | Tables & fields across the modules |
| 03 | [Software Requirements Spec (SRS)](03-srs.md) | What the system must do + non‑functional |
| 04 | [Use cases & user stories](04-use-cases-and-stories.md) | Actors, use cases, end‑to‑end flows |
| 05 | [Architecture](05-architecture.md) | Components, offline‑first, tech stack, deployment |
| 06 | [Workflows & state machines](06-workflows-state-machines.md) | Behavioural rules: stock, sale, transfer, insurance, EBM, payroll, sync |
| 07 | [API design](07-api-design.md) | REST surface per module + the offline sync API |
| 08 | [Security & compliance](08-security-and-compliance.md) | AuthN/Z, encryption, audit/immutability, RRA/GDP |
| 09 | [Technology stack](09-technology-stack.md) | Every technology per layer (React, Tauri, Django + DRF, Postgres) |
| 10 | [Collaboration, notifications & tools](10-collaboration-notifications-and-tools.md) | Internal comms, notification pipeline, utility tools/calculators |

### Research‑backed completeness, standards & decisions (12–19)
| # | Document | What it answers |
|---|----------|-----------------|
| 12 | [Field, document & approval requirements](12-requirements-fields-documents-approvals.md) | Every field/document (Finacle‑grade) + the reusable approval engine |
| 13 | [Rwanda regulatory & required documents](13-regulatory-licensing-and-documents-rwanda.md) | Exact Rwanda FDA / NPC / RDB / RRA licences & documents to operate |
| 14 | [International operational standards](14-international-operational-standards.md) | INN/ATC/DDD, GS1 GTIN/GLN/EPCIS, DrugBank severity, FIP/WHO GPP + GDP |
| 15 | [Competitive landscape & differentiation](15-competitive-landscape-and-differentiation.md) | Real systems, their persistent problems, our answers |
| 16 | [Operational playbooks](16-operational-playbooks.md) | How operators do transport, finance, HR, OTC, online |
| 17 | [Insurance & government](17-insurance-and-government.md) | Claims lifecycle + Rwanda schemes & 2025‑26 reforms |
| 18 | [Rwanda integrations & statutory](18-rwanda-integrations-and-statutory.md) | EBM, Mobile Money, PAYE/RSSB/CBHI rates, data‑protection law |
| 19 | [Platform architecture decisions](19-platform-architecture-decisions.md) | Multi‑tenancy + RLS, offline sync, permission matrix, missing entities |

## Companion documentation sets
- **Design system** → [design/](design/README.md) — brand + subsystem **logo family**,
  tokens, navigation, components, dashboards/charts, motion, UX writing, and the
  **[application blueprint](design/12-application-blueprint.md)** (full layout).
- **Development & process** → [development/](development/README.md) — git workflow,
  coding standards, testing, CI/CD, releases, environments, onboarding, ADR process.
- **Governance (repo root)** → [ROADMAP](../ROADMAP.md) · [CONTRIBUTING](../CONTRIBUTING.md)
  · [CHANGELOG](../CHANGELOG.md) · [SECURITY](../SECURITY.md) · [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md)

## Status (current)
**Building, not design‑phase.** Foundations + Catalog + the depot→retail Distribution
core are shipped; Retail POS, Finance, Connect, and Inventory are partially built
(~50+ backend PRs merged to `staging`, ~105 backend tests green). The product is
framed as a **workspace of subsystems** — see the [ROADMAP](../ROADMAP.md) for the
per‑subsystem status and the module‑oriented delivery phases.

**Key deltas vs. the early docs (00–11):**
- Backend is **Django + DRF** (ADR‑006), not the initial FastAPI skeleton.
- The depot→retail transfer shipped as the **lean flow** (place → **approve = ship** →
  **receive = land**, auto‑listing at the destination). The picking / driver / per‑item
  count steps described in 02/03/04/06 are the **future full‑logistics** target
  (Warehouse depth on the ROADMAP), not the current build.
- Organisation is a single `Organization` with a parent link (HQ→branch); a formal
  companies↔branches split remains optional ([doc 19](19-platform-architecture-decisions.md)).
- **We build in parallel and mark ✅ only when API + UI are both ready and role‑verified**
  ([Definition of Done](development/definition-of-done.md)); every job is completed on **one page**
  (search → pick → act, [design/05](design/05-single-page-workflow.md)).
- The **admin is a true super‑admin** — sees & does everything across all branches/users, can
  **view‑as (impersonate)** any user to verify RBAC, and monitors activity/performance/logs
  (all audited) ([ROADMAP → Admin](../ROADMAP.md)).

## Open decisions — now largely resolved (see the cited docs)
1. EBM provider → **OSDC (cloud)** via an `EbmProvider` abstraction ([doc 18](18-rwanda-integrations-and-statutory.md), [19](19-platform-architecture-decisions.md)).
2. Tax class → **B = 18% VAT** default per RRA classes ([doc 14](14-international-operational-standards.md)); confirm per‑drug at build.
3. Drug‑interaction data → structured, **DrugBank severity** scale + RxNorm/SNOMED/ICD‑10 codes ([doc 14](14-international-operational-standards.md)).
4. Insurer rollout → claims‑based module, RSSB/CBHI first ([doc 17](17-insurance-and-government.md)).
5. Offline policy → **outbox + idempotency + LWW**, server re‑runs FEFO on sync ([doc 19](19-platform-architecture-decisions.md)).
6. Tenancy/hosting → **multi‑tenant shared schema + Postgres RLS, hosted in Rwanda** (data residency, [doc 18](18-rwanda-integrations-and-statutory.md) §4).
