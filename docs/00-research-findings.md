# PharmaCore — Research Findings: How Existing Systems Do It

> Purpose: ground PharmaCore's design in how real pharmaceutical ERPs, pharmacy
> management systems, distribution-practice regulations, and Rwanda's specific
> tax/insurance rules actually work — **before** we design or code.
>
> Date compiled: 2026-08-03. Sources listed at the end.

---

## 1. Wholesale / distribution ERPs (the depot side)

**What existing systems do**
- **Batch/lot as the atomic unit.** Stock is never tracked as a flat quantity —
  every unit belongs to a *batch* with lot number, manufacture date, and expiry.
- **FEFO dispatch (First-Expired-First-Out)**, not FIFO. Picking is driven by
  expiry, with alerts for short-dated stock so it moves before it expires.
- **GRN creates the batch.** When goods are received, the Goods Received Note
  lines are what *generate* the batch records (lot + mfg + expiry). Receiving is
  the moment stock enters the ledger.
- **Cold-chain logging**, expiry analytics, targeted **recall** by batch,
  barcode-driven warehouse ops.
- **Audit trails + electronic signatures** on every stock movement (modeled on
  FDA 21 CFR Part 11 / DSCSA serialization in mature markets).

**Implications for PharmaCore**
- Confirms our "spine": inventory is batch-first, FEFO everywhere. ✅
- The GRN isn't paperwork bolted on at the end — it is the **write event** that
  moves stock from in-transit into retail/depot inventory. Design the GRN and the
  inventory insert as one transaction.
- Add batch-level **recall** capability early (cheap if designed in, expensive to
  retrofit) — one query: "which retail pharmacies received batch X, and how much
  is still on shelves / already sold to whom."

---

## 2. Good Distribution Practice (GDP) — the regulatory backbone

**What the regulations require** (WHO / EMA / Rwanda FDA all align here)
- **Complete, legible, traceable, retrievable records** with defined retention
  periods — full traceability of every medicinal product through the chain.
- **Validated computerised systems** with access control + audit trails and "good
  data integrity practices" (records can't be silently edited/deleted).
- Temperature mapping/monitoring, deviation records + CAPA, training logs.

**Implications for PharmaCore**
- **Immutability is a hard requirement, not a nice-to-have.** Finalized documents
  (GRN, delivery note, EBM receipt) and daily snapshots must be append-only /
  write-once. Design an audit-log table and immutable document storage from day 1.
- Every state change is stamped with **who + which department + when**. This is
  why the identity/roles module is the true foundation.
- Rwanda FDA licenses premises for wholesale vs retail separately, and inspects
  storage/documentation/staffing → the system must hold **license records** for
  both organizations and staff, and surface expiry.

---

## 3. Pharmacy management systems vs. plain POS (the retail side)

**What existing systems do**
- A real **Pharmacy Management System (PMS) is more than a POS.** POS = checkout +
  payment + inventory sync. PMS adds the *clinical* layer:
  - guided **dispensing workflow** from prescription → hand-off;
  - automated **drug–drug / drug–allergy / dosage** checks against a patient
    profile;
  - **patient profiles** with medication history.
- **Insurance adjudication** is a first-class subsystem: real-time eligibility,
  co-pay/deductible calculation, electronic claim submission to the payer/PBM,
  and **claims tracking + resubmission** of denials.

**Implications for PharmaCore**
- Separate **dispensing** (clinical, licensed pharmacist) from **cashier**
  (financial) — matches your "departments" instinct and the real division of duty.
- Interaction checking needs a **drug interaction reference dataset**; decide
  early whether to license one or start with a basic same-active-ingredient /
  duplication check. (Scope decision — flagged below.)
- Our **sale state machine** (saved → pending insurance → awaiting co-pay →
  completed) is exactly how adjudication-heavy systems decouple the counter from
  slow payer responses. ✅ Because in Rwanda adjudication is often *offline/delayed*,
  our version submits/reconciles later rather than real-time PBM calls.

---

## 4. Rwanda EBM (RRA electronic invoicing) — the tax spine

**What the RRA system requires** (EBM 2.1)
- Sales must be **fiscalized** through a Sales Data Controller. Two flavors:
  - **VSDC** — a local **Java** application on a PC at the premises (established,
    but a single point of failure: PC down = no legal receipts).
  - **OSDC** — cloud-native; your software talks directly to RRA's OSDC API over
    HTTPS. No local hardware dependency.
- The billing software must be **RRA CIS-certified** (vendor has a Developer ID).
- A valid fiscal receipt must contain **~9 elements**: taxpayer **TIN**, **SDC ID**,
  sequential **receipt number**, **receipt type code**, **date/time**, **itemized
  lines** (qty + unit price), **tax breakdown by class**, **QR code** (resolves to
  RRA verification), and the **cryptographic signature** from the SDC.
- **Item registration + classification codes**: every product is registered with
  RRA and mapped to a **tax class**.
- **Purchase/import registration**: incoming stock is also declared to EBM — it
  isn't only a sales system, it tracks stock in/out for VAT.
- **Tax classes**: **A = exempt (0%)**, **B = standard 18% VAT**, **C = zero-rated
  (0%, incl. specific pharmaceuticals)**, **D = special**. ⚠️ *Which class each
  medicine falls under must be confirmed with an accountant / RRA — do not
  hard-code; treat tax class as per-product configurable data.*
- **Penalties** for non-compliance are severe (10×–20× evaded VAT, possible
  closure). "Tengamara" gives customers a 10% VAT refund for verifying receipts.

**Implications for PharmaCore**
- **Target OSDC (cloud API) as primary**, keep VSDC as a fallback adapter. Build an
  `EbmProvider` abstraction so the two are swappable and testing doesn't need RRA.
- The EBM step is **asynchronous** (background worker + retry) — never block the
  cashier on RRA availability. Matches our state machine (`READY_FOR_EBM` → `SENT`).
- Product master needs `tin`-less product-level **tax class** + RRA **item code**;
  organization needs its **TIN** and **SDC/Developer** credentials.
- We must also feed **purchases** (the depot→retail transfer / supplier intake)
  into EBM, not just retail sales.
- Certification is a **business/legal prerequisite** before go-live — flag to the
  owner now; it affects timeline, not just code.

---

## 5. Rwanda health insurance — the co-pay reality

**What exists**
- **CBHI / Mutuelle de Santé** (administered by **RSSB**) covers **~85%**, patient
  pays **~15%** — but only at facilities that have a **signed agreement with RSSB**,
  and only for **drugs on the agreed/covered list (formulary)**.
- Other schemes exist (RSSB-RAMA for formal sector, MMI, private insurers like
  Radiant/MUA/Britam…) each with **different coverage splits** and formularies.

**Implications for PharmaCore**
- **Do NOT hard-code 85/15.** Model an `insurance_scheme` with a configurable
  coverage %/rules, and a **covered-drug formulary** per scheme. The sale engine
  computes: covered amount vs. patient co-pay based on the scheme + whether the
  drug is on that scheme's list.
- A pharmacy has agreements with *several* insurers → many-to-many
  (organization ↔ scheme) with per-agreement terms.
- Claims are **batched and submitted periodically** (weekly/monthly manifests),
  not real-time per sale → reinforces the async claims dashboard.

---

## 6. Reference implementations we can learn from

- **ADPharmacy / ADFinance (on Odoo)** — a *real* Rwanda/Africa pharmacy ERP:
  sales, purchases, inventory, quality/regulatory, **RRA EBM integration
  ("24/7/365 compliance")**, **insurance eligibility → billing → reimbursement**,
  stock optimization to cut expiry, import-data auto-load into inventory. This is
  essentially a commercial version of what PharmaCore aims to be → validates the
  module set and the "one system, wholesale+retail+tax+insurance" thesis.
- **PharmaSpot** (open source, **Electron**) — pharmacy POS as a **desktop app**
  with expiry tracking/alerts. Directly relevant to our "web + desktop" decision:
  Electron/Tauri wrapping a web app is the proven pattern for an offline-tolerant
  counter POS.
- Various open-source PMS (PHP/MySQL, Python/Tkinter) — confirm the *minimum*
  feature floor (inventory, expiry, billing, purchase records) but none handle
  Rwanda EBM/insurance or B2B distribution — that's PharmaCore's differentiator.

---

## 7. Open decisions surfaced by the research

These are business/scope choices that change the design — worth deciding before build:

1. **EBM: OSDC (cloud) vs VSDC (local Java)** as the primary integration — and who
   owns the **RRA CIS certification / Developer ID**?
2. **Medicine tax classes** — confirm with an accountant which drugs are A/B/C.
3. **Drug-interaction data** — license a clinical dataset, or start with a basic
   duplication/same-ingredient check?
4. **Insurance schemes to support first** — CBHI/RSSB only, or multi-insurer from
   the start (affects the formulary/agreement model)?
5. **Desktop offline tolerance** — must the POS keep selling when internet drops
   (queue EBM/claims), or is it always-online? (Big architectural impact.)

---

## Sources

- LogicERP — Pharma distribution ERP / expiry & stock loss: https://www.logicerp.com/blog/how-pharma-distribution-erp-software-reduces-expiry-stock-losses/
- Ximple — Pharma wholesale/distribution ERP, traceability/DSCSA: https://www.ximplesolution.com/industries/pharma-wholesale-software-erp/
- ECA Academy — What is Good Distribution Practice (GDP): https://www.gmp-compliance.org/gmp-news/what-is-good-distribution-practice-gdp
- EAW Logistics — GDP compliance checklist: https://www.eawlogistics.com/good-distribution-practice-gdp-compliance-made-practical-a-comprehensive-checklist-for-pharmaceutical-distribution/
- IntuitionLabs — Pharmacy Management Systems guide: https://intuitionlabs.ai/articles/pharmacy-management-systems-guide
- DatascanPharmacy — PMS vs basic POS: https://datascanpharmacy.com/how-does-pharmacy-management-software-differ-from-a-basic-point-of-sale-system/
- RRA — EBM / Electronic Billing Machine: https://www.rra.gov.rw/en/ebm-electronic-billing-machine
- RRA — VSDC specification (PDF): https://www.rra.gov.rw/fileadmin/user_upload/vsdc_specification_document_v1.0.4__2022.pdf
- Paybill — RRA EBM compliance, OSDC vs VSDC, tax classes: https://paybill.ke/blogs/rra-ebm-compliance/
- EDICOM — Mandatory e-invoicing in Rwanda (EIS): https://edicomgroup.com/blog/mandatory-einvoicing-rwanda-eis
- RSSB — CBHI / Service Delivery Standards: https://www.rssb.rw/index.php?id=17
- Borgen Project — Mutuelle de Santé (85/15 coverage): https://borgenproject.org/mutuelle-de-sante/
- Rwanda FDA — Licensing guidelines (manufacturers/distributors/wholesalers/retailers): https://rwandafda.gov.rw/wp-content/uploads/2023/04/
- ADFinance — ADPharmacy / Odoo RRA integration: https://www.adfinance.co/adfinance-odoo-integration/
- PharmaSpot — open-source Electron pharmacy POS: https://github.com/drkNsubuga/PharmaSpot
