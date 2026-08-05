# Insurance & Government (how pharmacies claim, and Rwanda's schemes + reforms)

How a pharmacy interacts with **insurers** and the **government payer**, the standard
**claims lifecycle** (international best practice), and **Rwanda's schemes + the
2025–2026 reforms** — all verified & cited. Drives the **Insurance** subsystem and its
ties to **Finance/EBM** and **Retail POS**.

---

## 1. The claims lifecycle (how a prescription becomes a paid claim)
Standard adjudication flow used everywhere; PharmaCore's Insurance module implements it.

1. **Capture** — enter patient + **insurance identifiers** (scheme/member/card no.,
   and in PBM markets BIN/PCN/group/cardholder/person code), **prescription** (drug
   code/NDC, quantity, days' supply, prescriber, DAW), and **pricing** (ingredient
   cost, dispensing fee, usual‑&‑customary price).
2. **Eligibility** — verify the member's **coverage** (active, formulary, deductible,
   co‑pay/co‑insurance, and any **prior authorization** needed).
3. **Adjudicate** — the payer scrutinises the claim: coverage, **formulary** match,
   cost‑sharing, PA — plus a **real‑time safety review** (drug‑drug interactions,
   duplicate therapy, allergies) that alerts the pharmacist **before dispensing**.
4. **Co‑pay split** — compute the **patient's share** (co‑pay/co‑insurance) vs the
   **insurer's share** (the claim amount).
5. **Outcome** — **Accepted** (insurer pays its part; patient pays co‑pay; dispense),
   **Declined** (usually billing/data errors → fix & resubmit), or **Reversed**.
6. **Settle** — payer issues an **EOB** (explanation of benefits) to the patient and
   an **EOP** (explanation of payment) to the provider; the pharmacy **posts &
   reconciles** payment against the claim.

> PharmaCore already does the **safety review** (interactions/contraindications,
> [doc 14](14-international-operational-standards.md)) and the **co‑pay split** shape
> exists in the sale model; the module adds **eligibility, adjudication, claims
> queue, EOB/EOP, and reconciliation** (this is our aged‑AR for insurers, [Finance](16-operational-playbooks.md#2-finance-running-the-business-by-the-numbers)).

---

## 2. Rwanda's schemes & the government's role
The **government is the dominant payer** through the **RSSB** (Rwanda Social Security
Board), which manages the community scheme.

| Scheme | Who | Notes |
|---|---|---|
| **CBHI / Mutuelle de Santé** | ~**93%** of the insured population | Solidarity scheme; **managed by RSSB since 1 July 2015** |
| **RSSB medical (formerly RAMA)** | Formal‑sector **workers** (~4.1%) | |
| **MMI** | Military | |
| **Private insurers** | Specific groups, limited coverage | |

- **Coverage is near‑universal: ~97.3%** of the population is insured.
- **Premiums by Ubudehe category** (indicative): Cat I **RWF 3,000** (gov/donor‑
  supported), Cat II & III **RWF 3,000/person**, Cat IV **RWF 7,000/person**.
- **Digital rails:** CBHI application/payment via **IremboGov** and mobile (**\*909#**);
  RSSB is rolling out a **new digital medical‑insurance system**.
- **Government touchpoints for a pharmacy:** RSSB (claims/payer), **Rwanda FDA**
  (licensing, [doc 13](13-regulatory-licensing-and-documents-rwanda.md)), **RRA**
  (VAT + **EBM** fiscal receipts — every insured sale still needs an EBM invoice),
  **NPC** (pharmacist licensing).

---

## 3. Recent enhancements (2025–2026) — what changed
Verified, current reforms (introduced via a **Prime Minister's order of 24 Feb**, with
Ministry of Health + RSSB follow‑ups):
- **Expanded coverage** — CBHI now covers **orthopaedic and neurosurgical procedures**
  (incl. brain surgery), and supports **kidney transplants, cancer treatment, and
  assistive devices/prostheses**.
- **Financing model shift** — public **primary healthcare** providers move from
  **retrospective fee‑for‑service** to **prospective capitation** (upfront funding to
  keep **medicines & supplies consistently available**, cutting invoicing/verification
  delays). **Piloted in Eastern Province health centres in Jan 2026**, rolling out
  nationwide.
- **Revised premiums & facility financing**; continued **digitalisation** of premium
  payment and claims.

> **Nuance for PharmaCore:** the **capitation** change targets **public primary
> healthcare facilities** — a **private retail/wholesale pharmacy still bills
> claims** to the insurer/RSSB per dispensed item. Our Insurance module is therefore
> **claims‑based**, but must be **scheme‑ and reform‑aware** (updated formularies,
> newly covered categories, and the RSSB digital‑system integration point).

---

## 4. What the PharmaCore **Insurance** subsystem must do
- **Insurers & schemes** — `InsuranceProvider` (RSSB/CBHI, RSSB‑medical, MMI, private)
  + `InsurancePolicy`/tier with **co‑pay %**, **formulary**, **prior‑auth** rules,
  reimbursement period.
- **At POS** — "route via insurance": capture member/card, verify eligibility, apply
  the **co‑pay split** (patient pays co‑pay by cash/MoMo/card; insurer portion → a
  **claim**), run the safety review, and still issue the **EBM** fiscal receipt.
- **Claims queue** — build claims from insured sales; **adjudication** status
  (accepted/declined/reversed) with reason; **prior‑authorization** capture; **resubmit**
  on rejection (via the **approval/return** engine).
- **Reconciliation** — monthly **claim manifests** per insurer, EOB/EOP posting,
  **aged insurer receivables** (Finance), payment matching on remittance.
- **Formulary & coverage upkeep** — maintain covered items/categories so the counter
  knows instantly what's covered (kept current with reforms like §3).
- **Government integration hooks** — designed to plug into the **RSSB digital system**
  and **EBM** when their APIs are available (mock provider first, per the roadmap).

Everything encoded here is sourced; scheme amounts/rules change — treat figures as
indicative and re‑confirm against RSSB/RRA at build.

---

### Sources
- Pharmacy claims adjudication (workflow, copay, outcomes, EOB/EOP): [Xevant – adjudication](https://www.xevant.com/glossary/pharmacy-claims-adjudication-process/), [Starlight – prescription to paid claim](https://starlightapi.com/blog/pharmacy-claims-processing-workflow), [freeCE – billing & reimbursement](https://www.freece.com/blog/navigating-landscape-pharmacy-billing-reimbursement/)
- Rwanda schemes (CBHI/RSSB/coverage/premiums): [RSSB – CBHI](https://www.rssb.rw/index.php?id=17), [IremboGov – Mutuelle FAQ](https://support.irembo.gov.rw/en/support/solutions/articles/47001205982-frequently-asked-questions-about-community-based-health-insurance-mutuelle-), [RRA – CBHI contribution](https://www.rra.gov.rw/en/domestic-tax-services/rssb-contributions/cbhi-contribution)
- 2025–2026 reforms (coverage expansion, capitation): [The New Times – Mutuelle reforms explained](https://www.newtimes.co.rw/article/33617/news/health/minister-habimana-clarifies-what-mutuellede-sante-reforms-mean-for-contributors/amp), [Africa Press – reforms](https://www.africa-press.net/rwanda/all-news/minister-habimana-explains-mutuelle-de-sante-reforms), [Capitation reform study (2026)](https://arxiv.org/html/2510.21851), [RSSB – new digital system](https://www.newtimes.co.rw/article/6185/news/health/new-digital-system-set-to-deliver-better-medical-insurance-rssb)
</content>
