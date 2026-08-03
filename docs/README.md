# PharmaCore — Analysis & Design Documentation

The complete system analysis and design document set for **PharmaCore**, a unified
pharmaceutical ERP for Rwanda (wholesale distribution + retail POS + compliance +
HR/finance). Read in order; each builds on the last.

| # | Document | What it answers |
|---|----------|-----------------|
| 00 | [Research findings](00-research-findings.md) | How do existing systems (ERPs, PMS, GDP, RRA EBM, insurance) do this? |
| 01 | [Key decisions (ADRs)](01-key-decisions.md) | The shaping choices: offline-first, multi-insurer, EBM-abstracted |
| 02 | [Data model](02-data-model.md) | Every table & field across 12 modules (~55 tables) |
| 03 | [Software Requirements Spec (SRS)](03-srs.md) | What the system must do (functional) and how well (non-functional) |
| 04 | [Use cases & user stories](04-use-cases-and-stories.md) | Actors, use cases, and the critical end-to-end flows |
| 05 | [Architecture](05-architecture.md) | Components, offline-first design, tech stack, deployment, trade-offs |
| 06 | [Workflows & state machines](06-workflows-state-machines.md) | The behavioural rules: stock, sale, insurance, EBM, payroll, sync |
| 07 | [API design](07-api-design.md) | REST surface per module + the offline sync API |
| 08 | [Security & compliance](08-security-and-compliance.md) | AuthN/Z, encryption, audit/immutability, RRA/GDP compliance |
| 09 | [Technology stack](09-technology-stack.md) | Every technology per layer — React, Tauri desktop, FastAPI, Postgres, infra — with rationale |

## Companion documentation sets
- **Design system** → [design/](design/README.md) — brand, tokens, navigation,
  components, dashboards/charts, motion, UX writing (12 docs + 2 visual references).
- **Development & process** → [development/](development/README.md) — git workflow,
  coding standards, testing, CI/CD, releases, environments, onboarding, ADR process.
- **Governance (repo root)** → [ROADMAP](../ROADMAP.md) · [CONTRIBUTING](../CONTRIBUTING.md)
  · [CHANGELOG](../CHANGELOG.md) · [SECURITY](../SECURITY.md) · [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md)

## How the documents relate
```
00 research ─► 01 decisions ─► 02 data model
                     │              │
                     ▼              ▼
                 03 SRS ◄──────► 04 use cases
                     │
                     ▼
             05 architecture ─► 06 workflows ─► 07 API design
                     │
                     ▼
          08 security & compliance
```

## Status
Design phase. **No application code yet** — by decision, we're establishing full
shared understanding first. The build sequence (foundation-first: iam → catalog →
inventory → distribution → …) is in the root [README](../README.md) module table.

## Open decisions still to settle (business calls)
1. EBM primary provider: **OSDC (cloud)** vs **VSDC (local)** — and who owns RRA CIS certification.
2. Per-drug **tax class** (A/B/C) — confirm with an accountant/RRA.
3. **Drug-interaction dataset** — license clinical data vs. basic duplication checks.
4. Insurer **rollout order** (schema supports all from day one).
5. Offline **soft-allocation** policy — pre-allocate batch stock per terminal, or reconcile-only.
