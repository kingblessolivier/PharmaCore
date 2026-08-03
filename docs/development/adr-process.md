# PharmaCore — Architecture Decision Record (ADR) Process

We record significant technical decisions so future engineers know *why*, not just
*what*. The living log is [docs/01-key-decisions.md](../01-key-decisions.md).

---

## When to write an ADR
Write one for a decision that is **hard to reverse** or **shapes multiple modules**:
- choosing/replacing a technology (DB, queue, EBM approach),
- a cross-cutting pattern (offline sync, immutability, auth model),
- a scope decision with architectural impact (multi-insurer, English-only),
- anything you'd want explained when someone asks "why is it built this way?".

Skip ADRs for routine, easily-reversible choices (a helper's name, a local refactor).

## Where they live
- The **ADR log** is `docs/01-key-decisions.md` — one numbered entry per decision
  (`ADR-001`, `ADR-002`, …). Keep them in that single file while the set is small;
  split into `docs/adr/` if it grows large.

## Format (matches the existing log)
```markdown
## ADR-00X — <short title>

**Decision:** <what we're doing, in one or two sentences>

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-00Y
**Date:** YYYY-MM-DD

**Context:** <the situation and forces at play>

**Options considered:** <A / B / C with pros-cons or a small table>

**Consequences:**
- <what becomes easier>
- <what becomes harder>
- <what we'll revisit and when>
```
(For richer trade-off tables, the [architecture skill](../05-architecture.md) format
is a fine template.)

## Lifecycle
1. **Propose** in a PR (the ADR entry + any code) → discussed in review.
2. **Accept** when merged; status `Accepted`, dated.
3. **Supersede** rather than edit history: a reversed decision gets a new ADR that
   marks the old one `Superseded by ADR-00Y`. Don't delete the original — the trail matters.

## Current ADRs (see the log for detail)
- **ADR-001** — Offline-first retail POS (local-first + sync)
- **ADR-002** — Multi-insurer from day one
- **ADR-003** — Abstract the EBM integration (`EbmProvider`); choose OSDC/VSDC later
- **ADR-004** — English-only UI

## Relationship to other docs
An ADR captures the *decision*; the *design* it implies lives in the architecture,
data-model, and workflow docs. Link between them so a reader can go from "why" to "how".
