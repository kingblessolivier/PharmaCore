# Rwanda Integrations & Statutory Reference (research-backed)

The external, Rwanda‑specific things a builder must integrate or compute against.
Verified & cited; amounts/rules change → treat figures as indicative and re‑confirm at
build. Feeds Finance/EBM, Retail, Online, People/Payroll, and hosting decisions.

---

## 1. Fiscalisation — RRA EBM (mandatory for every sale)
- Rwanda's **Electronic Invoicing System (EIS)** has been in force since **1 Jan 2021**.
  Under the **Tax Procedures Law (2023)**, **every transaction must generate a
  compliant fiscal receipt signed by an RRA‑authorised Sales Data Controller (SDC)** —
  regardless of business size. Penalties in 2025–26: **10× evaded VAT** (first offence),
  **20×** (repeat).
- **Methods:** EBM **v2.1** (Windows/tablet, Android), **Online EBM** (web), and the
  **VSDC** (Virtual Sales Data Controller). Two integration paths:
  - **VSDC** — an **on‑premise Java bridge** app running at the premises, relaying
    sales/purchase/receipt data between a private ERP and the RRA EBM server.
  - **OSDC** — the **cloud/SaaS** path, **no local box** required.
- **SDKs** exist for **Node.js, PHP, Python**; API specs published by RRA (`vsdc.io/docs`).

**PharmaCore:** an **`EbmProvider` abstraction** with a **MockEbmProvider** first
(build/test without RRA), then the real **OSDC (cloud)** path since we're SaaS. Every
sale — **including insured sales** — is fiscalised; we store the **fiscal receipt
number + SDC signature + QR** on the sale and in the document vault. Async with retry
(fiscalisation must not block the counter; failures queue for retry).

## 2. Payments — Mobile Money (MTN MoMo, Airtel Money)
- **MTN MoMo** is the dominant rail; API at `momoapi.mtn.co.rw` with a **developer
  portal + sandbox**. Two APIs: **Collections** (receive money from customers) and
  **Disbursements** (send money — payroll, refunds, settlements).
- **Request‑callback pattern**: initiate → customer prompted on phone → confirms →
  provider **callbacks** your server with the result (same shape as Airtel/M‑Pesa).
- **Airtel Money** offers an equivalent API; **aggregators** provide a **one‑API layer**
  across MTN + Airtel + cards.

**PharmaCore:** a **`PaymentProvider` abstraction** (MoMo/Airtel/card/cash). POS &
Online use **Collections** (with **idempotency keys** + callback verification);
**Payroll/settlements** use **Disbursements**. Never block the sale on a slow callback —
reconcile asynchronously.

## 3. Payroll & tax — statutory rates (2025/26)
Verified current rates for the People/Payroll module. Store as **versioned
`statutory_rates` config keyed by effective date** (they change yearly).

**PAYE (monthly bands):** 0–60,000 → **0%** · 60,001–100,000 → **10%** ·
100,001–200,000 → **20%** · above 200,000 → **30%**. *(PAYE is computed on **gross**;
employee RSSB is **not** deductible from the tax base.)*

**RSSB pension:** **12% total** (6% employer + 6% employee) since **Jan 2025**;
scheduled **+2%/yr from 2027 → 20% by 2030**.
**Maternity:** **0.6%** (0.3% employer + 0.3% employee).
**CBHI (payroll deduction):** **0.5% of NET pay**, mandatory.
**Note:** since 2025 the contribution base was **expanded to include transport
allowance** — factor it into the taxable/contributory base.

## 4. Data protection — Law N°058/2021 (affects hosting & patient data)
- Effective **15 Oct 2021**; applies to **anyone processing personal data in Rwanda**,
  incl. foreign companies serving Rwandan residents.
- **Consent (Art 6):** must be **freely given, specific, informed, unambiguous** before
  collecting/processing personal data.
- **Data residency:** **personal data must be stored *within Rwanda*** — or obtain a
  **certificate from the NCSA** (National Cyber Security Authority / Data Protection &
  Privacy Office) for **offshore storage**.
- **NCSA/DPO** oversees, maintains a **register of controllers/processors**, and issues
  offshore certificates.

**PharmaCore consequences:** **host in Rwanda** (or hold an NCSA offshore certificate);
**capture consent** for patient/customer data; register as a **controller/processor**;
support **data‑subject rights** (access/rectify/erase) on top of our audit log; encrypt
at rest/in transit. This makes the deployment/hosting decision a **compliance** matter,
not just ops.

## 5. Government touchpoints (integration hooks)
| Body | What we integrate/comply with | Status |
|---|---|---|
| **RRA** | **EBM** fiscal receipts (OSDC), VAT | Build against mock → OSDC |
| **RSSB** | Insurance **claims** (CBHI/RSSB); a **new digital system** is rolling out — until its API is public, support **manual claim manifests + reconciliation** | Manual first; API hook later |
| **NCSA / DPO** | Data‑protection registration + residency | Hosting + consent |
| **Rwanda FDA** | Licensing + controlled‑substance quarterly reports (doc 13) | Compliance module |
| **IremboGov** | Government e‑services rail (context for CBHI) | Reference only |

---

### Sources
- **EBM / VSDC / OSDC**: [RRA – VSDC](https://www.rra.gov.rw/en/ebm-electronic-billing-machine/content-under-ebm/virtual-sales-data-controller-vsdc), [VSDC developer docs](https://vsdc.io/docs), [EDICOM – Rwanda e‑invoicing](https://edicomgroup.com/blog/mandatory-einvoicing-rwanda-eis), [PayBill – OSDC vs VSDC](https://paybill.ke/blogs/rra-ebm-compliance/)
- **Mobile Money**: [MTN MoMo developer portal](https://momoapi.mtn.co.rw/), [McTaba – MoMo API integration Rwanda](https://www.mctaba.com/learn/rwanda/momo-api-integration-rwanda), [GBOX – MoMo integration](https://gbox.rw/en/blog/mtn-momo-api-integration-rwanda/)
- **Payroll/statutory (2025/26)**: [CountryTaxCalc – Rwanda PAYE 2026](https://www.countrytaxcalc.com/tax-guides/africa/rwanda-paye-guide-2026/), [Visions Africa – RSSB pension changes 2025 (PDF)](https://visionsafrica.com/wp-content/uploads/2024/12/241203-CHANGES-TO-RSSB-PENSION-CONTRIBUTIONS-IN-RWANDA-FOR-2025-1-1.pdf), [HeadOffice – Rwanda payroll tax](https://headoffice.app/rwanda/blog/rwanda-payroll-tax)
- **Data protection**: [RwandaLII – Law 058/2021](https://rwandalii.org/akn/rw/act/law/2021/58/eng@2021-10-15), [DLA Piper – Rwanda](https://www.dlapiperdataprotection.com/index.html?t=about&c=RW), [DPO Rwanda – FAQs](https://dpo.gov.rw/faqs)
</content>
