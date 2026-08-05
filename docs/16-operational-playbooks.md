# Operational Playbooks — how operators do it (Transport, Finance, HR, OTC, Online)

For each domain: **how the people who actually do it operate** (verified, cited),
then **how PharmaCore does / will do it** (✔ = already shipped). This drives the
depth of the Distribution/Logistics, Finance, People, Retail, and Online subsystems.

---

## 1. Transport & logistics (getting stock there safely)
**How it's done:**
- **Last mile is the hardest, most vulnerable leg** — "a shipment that maintained
  perfect temperature for 2,000 miles can fail in the final 20" if the last carrier
  lacks refrigerated equipment/training.
- **Cold chain** = keep temperature‑sensitive products in a narrow band (commonly
  **2–8 °C**) with **documented handling, continuous temperature monitoring, and
  clear accountability at every handoff**.
- **Real‑time GPS + temperature monitoring** in transit; digitalisation & smart
  packaging give customers transparency/visibility. (Market $22.75B→$44.1B by 2033.)

**PharmaCore:**
- ✔ **Dispatch** records driver + vehicle; ✔ **in‑transit ledger** holds the stock
  between ship and receive (accountability at the handoff); ✔ **proof of delivery**
  via GRN on receipt; ✔ cold‑chain min/max on the product.
- ⬜ **Temperature log per shipment/leg** + **excursion flag** on receipt (accept/
  quarantine), optional **GPS/route** capture, delivery‑confirmation signature.
- Design: every handoff is an **event on the ledger** (EPCIS‑shaped, [doc 14](14-international-operational-standards.md)),
  so "who held it, where, at what temperature" is answerable.

## 2. Finance (running the business by the numbers)
**How it's done — the metrics operators actually track:**
- **Gross profit margin = (net sales − COGS) / net sales**; **Operating Expense
  Ratio = OpEx / Revenue**, ideal **< 19%**.
- **Inventory** is ~**78% of operating costs** → track **inventory valuation** and
  **inventory turnover** (how often stock sells & is replaced; higher = leaner).
- **Operating cash flow** as the health signal; standardised **bookkeeping,
  reconciliation, reporting**; **monthly reports** (income, expenses, cash flow) to
  spot trends/risks/gaps.

**PharmaCore Finance module:**
- ✔ **Margin** per product; ✔ **aged receivables/payables**; ✔ **settlement**.
- ⬜ **Inventory valuation** (on‑hand × cost) + **turnover**, **GP margin** &
  **OpEx ratio** KPIs, **cash‑flow** view, **daily cash‑drawer reconciliation**,
  **monthly financial statements** (P&L, balance sheet, cash flow, trial balance),
  **chart of accounts + auto‑posting journals**, **EOD closeout**, **consolidated HQ**.
- KPI dashboard = the operator's real metrics, not vanity numbers.

## 3. HR / People (the workforce & its compliance)
**How it's done:**
- **Credential/compliance is the hard part** — professional **licences** (per
  jurisdiction; in Rwanda, **NPC** — [doc 13](13-regulatory-licensing-and-documents-rwanda.md)),
  technician certification, **immunisation/CPD tracking**, expiry maintenance.
- **Chronic shortages & turnover** (pharmacist vacancy 10–15%, technician turnover
  30–40%) → **scheduling for full shift coverage** matters.
- **Payroll spans mixed pay structures** (pharmacists / technicians / front‑end) on
  one deadline. **Hiring** is hard (≈70% struggle to fill); **onboarding** goes
  beyond admin (orientation, safety protocols, culture); **background checks**
  verify **licences, credentials, employment history**.

**PharmaCore People module:**
- ✔ **Licence tracking + expiry alerts** (pharmacist‑in‑charge).
- ⬜ **Recruitment → onboarding** (checklist, background/licence verification),
  **employee records + documents** ([doc 12 §3](12-requirements-fields-documents-approvals.md)),
  **scheduling/rostering** with coverage, **leave**, **attendance**, **payroll**
  (multi pay‑structure, PAYE/RSSB, payslips, remittance), **training + competency**
  (SOP read‑&‑sign, controlled‑drug assurance checks, CPD credits), **offboarding**.

## 4. Over‑the‑counter selling (the counter done well)
**How it's done:**
- **One clean flow** for **Rx pickup + OTC + split payments + returns + notes** —
  prescription pickup and OTC in the **same sale**; staff need **quick product
  search, fast customer lookup, clean payment** to keep lines moving.
- Handle **split payments, partial balances, returns, exchanges, refunds** with **no
  workarounds**.
- A **patient profile** (medication history, allergies, insurance, contact) lets the
  pharmacist **check interactions and counsel** at checkout.
- **Upsell** via relevant recommendations (e.g. drug‑induced nutrient depletion);
  unify **POS + online** as one; reminders/outreach by buying behaviour.
- **Real‑time insurance + expiry tracking** cut wait times so the pharmacist can
  focus on safety/counselling.

**PharmaCore Retail:**
- ✔ Unified cart, **FEFO** pick, **split‑tender**, **returns + credit note**, fast
  search, **expired block**, **Rx/controlled dispensing gate**, **running total that
  updates cleanly as items are added**.
- ⬜ **Customer/patient profile** (history, allergies, insurance), **interaction/
  contraindication warning at add‑to‑cart** (from structured clinical data),
  **counselling prompts**, **upsell suggestions**, **cash‑drawer session**, loyalty/
  reminders, **offline‑first**.

## 5. Online pharmacy (selling beyond the counter)
**How it's done:**
- Customers **browse, upload a prescription** (PDF/JPG/PNG) at checkout or anytime,
  order, and choose **home delivery — under the pharmacy's own brand**.
- **Pharmacist verification before fulfilment**: the pharmacist confirms the
  prescription's authenticity, **approves or requests resubmission** via a
  pharmacist app; only then does the order proceed.
- **Fulfilment**: backend processes the order, prepares for shipping; pharmacist gets
  **real‑time notifications**; **delivery** is own‑fleet or a **3PL** partner.
- **Security/compliance**: encryption, MFA, **audit trails**, privacy (HIPAA/GDPR
  class controls).

**PharmaCore Online:**
- ⬜ **Patient storefront** (browse OTC, search) on the **same stock/price engine**,
  **prescription upload**, a **pharmacist verification queue** (routed through the
  **approval engine**, [doc 12 §4](12-requirements-fields-documents-approvals.md)),
  **delivery** (own or 3PL) with the transport playbook (§1), **online payment**,
  ✔ notifications, and the platform's existing **audit trail + security**.
- One inventory, one price list, one customer — **POS + online unified**, exactly as
  the best operators run it.

---

## Cross‑cutting takeaways (design consequences)
- **Patient/customer** becomes a first‑class entity (needed by OTC counselling,
  insurance, and Online).
- **Approval engine** powers online Rx verification, payroll, hiring, price changes —
  build it once, reuse everywhere.
- **One inventory/price/customer** across counter + online + branches — never a
  second silo.
- Everything is an **event on the ledger** (transport handoff, sale, dispense,
  return) — traceable, compliant, and analytics‑ready.

---

### Sources
- Transport/cold‑chain last mile: [Pharmaceutical Commerce – last‑mile cold chain](https://www.pharmaceuticalcommerce.com/view/scaling-security-and-speed-in-pharmaceutical-cold-chain-delivery-at-the-last-mile), [Tower Cold Chain](https://www.towercoldchain.com/how-to-win-in-last-mile-pharmaceutical-delivery/)
- Pharmacy finance/KPIs: [insightsoftware – pharma KPIs](https://insightsoftware.com/blog/15-best-pharma-kpis-and-metric-examples/), [Fleming Advisors – profitability playbook](https://www.fleming-advisors.com/post/the-pharmacy-profitability-playbook-understanding-key-metrics-and-margins), [DiversifyRx – cash‑flow KPIs](https://diversifyrx.com/3-critical-kpis-for-pharmacies-in-2024-boosting-cash-flow/)
- Pharmacy HR: [Netchex – pharmacy HR/payroll](https://netchex.com/pharmacy-hr-payroll-software/), [FrontLine – pharmacy staffing](https://www.frontlinesourcegroup.com/blog-pharmacy-staffing-how-to-attract-top-talent.html)
- OTC/POS workflow: [ConnectPOS – pharmacy POS](https://www.connectpos.com/pos-software-for-pharmacy/), [Celerant – pharmacy POS](https://www.celerant.com/industries/pharmacy/)
- Online pharmacy: [DigitalPharmacy.io – prescription upload](https://digitalpharmacy.io/why-prescription-upload-is-a-must-have-for-online-pharmacies/), [DigitalPharmacy.io – essential features](https://digitalpharmacy.io/10-essential-features-your-pharmacy-ecommerce-platform-must-have/)
</content>
