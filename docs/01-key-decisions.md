# PharmaCore — Key Architectural Decisions (ADR log)

Decisions that materially shape the design. Recorded as we settle them.

---

## ADR-001 — Retail POS must keep selling offline (local-first + sync)

**Decision:** The retail counter must continue selling when the internet drops.
Sales are captured locally and synchronized (including EBM fiscalization and
insurance claims) once connectivity returns.

**Status:** Accepted (2026-08-03)

**Consequences (this is the heaviest decision in the system):**
- The POS is a **desktop app with a local datastore** (Tauri/Electron + local DB,
  e.g. SQLite), not just a browser talking to a server. → confirms "web + desktop".
- We need a **sync engine**: local → central reconciliation, with:
  - **Conflict-free IDs** — sales/receipts get **UUIDs** generated on the device
    (never rely on a central auto-increment while offline).
  - **Batch stock is the contention point.** Two offline counters could both sell
    the last pack of a batch. Mitigate with per-terminal stock allocation and a
    server-side reconciliation that flags oversell for a manager (matches the
    "physical count mismatch" guardrail).
  - An **outbox pattern**: offline actions (sale, EBM submit, claim) are queued
    events, replayed in order when online.
- **EBM and insurance are inherently deferred** anyway → aligns perfectly with the
  async state machine. Offline just extends the queue window.
- Reporting/EOD closeout must tolerate **not-yet-synced** terminals (show pending).
- Central server remains the **source of truth**; the device holds a **working
  subset** (its own stock, catalog, pricing, open sales).

**Rejected alternative:** always-online POS (simpler single-DB design) — rejected
because Rwandan retail connectivity isn't reliable enough to stop selling.

---

## ADR-002 — Multi-insurer from day one

**Decision:** Support multiple insurance schemes from the start, not just CBHI.

**Status:** Accepted (2026-08-03)

**Consequences:**
- Model `insurance_scheme` (CBHI/RSSB, RAMA, MMI, private insurers…) each with its
  own **coverage rule** (e.g. 85/15) and **covered-drug formulary**.
- `organization` ↔ `insurance_scheme` is **many-to-many** (a pharmacy holds
  agreements with several insurers), with per-agreement terms.
- The sale engine computes coverage as a function of *(scheme, drug on formulary?,
  coverage rule)* — never a hard-coded percentage.
- Patient/customer record can carry a **policy/membership number** per scheme.
- Claims are grouped into **per-scheme periodic manifests** for submission.

---

## ADR-003 — Abstract the EBM integration (`EbmProvider`), choose OSDC/VSDC later

**Decision:** Build an `EbmProvider` interface now; defer the OSDC-vs-VSDC choice
until RRA certification details are confirmed.

**Status:** Accepted (2026-08-03)

**Consequences:**
- Define a provider contract: `register_item`, `register_purchase`, `sign_sale`,
  returning {SDC ID, receipt number, signature, QR}.
- Ship a **MockEbmProvider** for development/testing (no RRA dependency).
- Real adapters (`OsdcProvider`, `VsdcProvider`) implement the same contract;
  swap via config. Product master carries **tax class + RRA item code**;
  organization carries **TIN + SDC/Developer credentials**.
- **Business prerequisite (not code):** obtain RRA **CIS certification / Developer
  ID** before go-live. Track as a project milestone.

---

## ADR-004 — English-only user interface

**Decision:** The PharmaCore UI is **English only**. No bilingual/Kinyarwanda UI,
translation catalog, or language switcher is in scope.

**Status:** Accepted (2026-08-03)

**Consequences:**
- One string source, one voice — simpler copy, terminology, and QA.
- Copy is kept **plain and ESL-friendly** (many users are English-as-second-language);
  domain/legal terms follow official RRA / Rwanda FDA English forms.
- Money/date/quantity still use Rwandan conventions (RWF, `dd MMM yyyy`).
- UI strings are still **externalized into one catalog** (good practice + leaves the
  door open if another language is ever requested later) — not a bilingual commitment.
- See design doc [11-ux-writing-and-terminology.md](design/11-ux-writing-and-terminology.md).

## ADR-005 — Product naming: "PharmaCore" (by Medlink)

**Decision:** The unified platform is named **PharmaCore**. **Medlink** is the
**company** (vendor). Sub-systems are named **PharmaCore {Subsystem}** — PharmaCore
Distribution, Inventory, Retail, Insurance, Finance, People, Insights, Admin.

**Status:** Accepted (2026-08-03)

**Context:** "Medlink" alone is the company; the product needed its own name that (a)
signals a single unified platform and (b) makes the pharmacy domain obvious. The name
had to contain "Pharma".

**Consequences:**
- Brand hierarchy: **Medlink** (company) › **PharmaCore** (platform) › **PharmaCore
  {Subsystem}** (modules). Lockup: "PharmaCore" wordmark, optionally "by Medlink".
- The [brand & logo system](design/02-brand-and-logo-system.md) uses **PharmaCore** as
  the master wordmark; the sub-system logo family relabels to **PharmaCore {Subsystem}**
  (tiles/hues/glyphs unchanged).
- On generated documents, **PharmaCore by Medlink** appears as the system-of-record in
  the footer (Medlink is the vendor of record).
- The **repository directory** stays `Medlink` (harmless — it's the folder, not the brand).
- Docs are being updated to distinguish company (Medlink) from product (PharmaCore);
  where older docs say "Medlink" as the *system*, read it as *PharmaCore*.

## Still open (deferred, not yet decided)

- Drug-interaction dataset: license clinical data vs. basic duplication check.
- Exact medicine **tax-class** mapping (A/B/C) — confirm with accountant/RRA.
- Which insurers to onboard *first* operationally (schema supports all; rollout order TBD).
