# Regulatory, Licensing & Required Documents (Rwanda)

Research‑backed. **Everything below is sourced from the official regulators** — the
Rwanda FDA licensing guidelines (Doc. **FDISM/FDIC/GDL/005**, Rev 4, effective
15/04/2023), the National Pharmacy Council (NPC), and RDB/RRA. Where a requirement
is *not* verified from a primary source it is marked **[verify]** rather than
stated as fact. This drives the `OrganizationDocument` / `UserDocument` requirement
lists in [doc 12](12-requirements-fields-documents-approvals.md).

> Ground rule: we only encode as **required** what the regulator lists as required.
> Fees and exact wording change — treat amounts as indicative and re‑confirm at build.

---

## 1. Who licenses what (the four bodies)
| Body | Issues | PharmaCore relevance |
|---|---|---|
| **RDB** (Office of the Registrar General) | Company/enterprise registration certificate + **TIN** (RDB↔RRA integrated) | Every org needs it; captured as `registration_number` + `tin` |
| **RRA** (Rwanda Revenue Authority) | Tax registration; **VAT** registration; **EBM** obligation | VAT if turnover > RWF 20M/yr or 5M/quarter → **EBM mandatory** |
| **Rwanda FDA** | **Premises licence** to operate as manufacturer / distributor / **wholesale** / **retail** pharmacy, after site inspection | The operating licence; `rwanda_fda_license_no` + expiry |
| **National Pharmacy Council (NPC)** | **Registration + licence to practise** for pharmacists & pharmacy technicians | The "authorized person" / pharmacist‑in‑charge each pharmacy must have |

A pharmacy business therefore needs **all four**: RDB registration + TIN → RRA (VAT/EBM if applicable) → a **licensed pharmacist** (NPC) → the **premises licence** (Rwanda FDA).

---

## 2. Documents to license a **premises** (Rwanda FDA)
From FDISM/FDIC/GDL/005 Rev 4. These are the exact application attachments. In
PharmaCore these become `OrganizationDocument` types, **required** for the matching
org type before the org can be marked *operational*.

### 2.1 Human **retail** pharmacy (§6.7)
1. Application letter addressed to the Director General
2. Duly filled **application form** (premises licensing of medical products)
3. **Certificate of domestic company registration (RDB)** or equivalent/local‑government recommendation
4. **Lease/rent contract** of the premises (or other relevant proof)
5. **Evidence of payment** of prescribed fees to Rwanda FDA
6. **Notarized copy of degree** (+ equivalence if applicable) of the **authorized person**, with **≥2 months** community‑pharmacy experience
7. **Notarized valid Licence to Practise Pharmacy** issued by the **National Pharmacy Council**
8. **Curriculum vitae** of the authorized person
9. **Professional agreement** between the Managing Director and the authorized person (if the MD is not the authorized person)
10. **Copy of ID/passport** of both the Managing Director and the authorized person
11. **Written commitment of the technician** to respect pharmacy laws/regulations
12. Signed **resignation letter / proof of service** from the authorized person's last employer, *if applicable*
13. **Copy of the valid contract** between authorized person and Managing Director

### 2.2 Human **wholesale** pharmacy (§6.2)
Same list as retail, except item 6 requires **≥2 months' experience in supply‑chain
management** (not community pharmacy). All other attachments (RDB cert, lease,
fee proof, notarized degree, NPC practise licence, CV, professional agreement,
IDs, technician commitment, resignation letter, contract) are identical.

### 2.3 **Distributor** of medical products (§6.1)
As wholesale, **plus**:
- **Agreement between the Distributor and the Manufacturing Facility** it represents (if applicable)
- **Valid GSP/GDP‑compliant premises licence** issued by Rwanda FDA
- *(Note: a Distributor may have multiple distribution points, each meeting wholesale minimums, and may distribute **to wholesale pharmacies only**.)*

### 2.4 **Renewal** of a premises licence (§7)
1. Application letter to the Director General · 2. Application form · 3. **Recent
premises licence** issued by the Authority · 4. Evidence of prescribed fees ·
5. **Valid licence to practise** of the authorized person.

> Implication for PharmaCore: premises licence + pharmacist licence **expiry dates**
> must be tracked and alerted (renewal needs the *current* licence + practising licence).

---

## 3. Premises **minimum floor space & height** (Rwanda FDA §4.4)
Verified minimums (m² / height). These inform the (future) Warehouse module's
facility/zone records and the licensing checklist.

| Facility | Total | Sales area | Storage area | Height |
|---|---|---|---|---|
| Manufacturer / large facility | 180 m² | 30 m² | 150 m² | — |
| **Wholesale pharmacy** | 90 m² | 30 m² | 60 m² | 2.5 m |
| Medical‑device wholesale (approx.) | 70 m² | 25 m² | 45 m² | 2.5 m |
| **Retail pharmacy** (Kigali & secondary cities) | single dispensing room **40 m²** | — | — | 2.5 m |
| **Retail pharmacy** (rest of country) | single dispensing room **30 m²** | — | — | 2.5 m |

---

## 4. Documents to license the **pharmacist / technician** (National Pharmacy Council)
The "authorized person" a pharmacy must have. From the NPC *Registration &
Requirements*. In PharmaCore these are `UserDocument` types on the pharmacist's
profile, **required** to assign the *pharmacist‑in‑charge* role.

**Nationals — required documents:** completed application form · **criminal
record** (competent Rwandan authority) · **certified pharmacy diploma/degree** ·
**certified academic transcripts** · **certified degree equivalence** (competent
Rwandan organ) · **certified A‑level certificate** · **proof of one‑year internship
completed in Rwanda** · valid **index number** proof · recent **passport photo** ·
**registration‑fee payment** proof · **ID/passport** copy · **pre‑registration exam
pass** proof · signed **CV** · prior professional‑council registration proof (if applicable).

**Non‑nationals — additionally:** home‑country pharmacy‑council registration proof ·
**good‑standing certificate** from home council · **work permit** (competent Rwandan
authority) · evidence the home country registers Rwandan professionals (reciprocity).

**Qualification baseline:** bachelor's degree in pharmacy + **one‑year professional
internship** in Rwandan settings. **CPD:** ≥15 credits/year (75 per 3‑year cycle).

**Fees (indicative — re‑confirm):** registration — nationals RWF 20,000 / EAC USD 30
/ non‑nationals USD 90. Licence — pharmacists RWF 65,000, technicians RWF 30,000 /
EAC USD 100 / non‑nationals USD 300. **Renewal = initial**, with **25% penalty per
3‑month delay.**

---

## 5. Ongoing compliance obligations (verified)
- **Controlled substances:** quarterly reports on the distribution of controlled
  substances must be submitted to the Authority; the authorized person must hold a
  copy of the premises licence and the licence to practise. *(Feeds the
  controlled‑drug register + a scheduled quarterly report in People/Compliance.)*
- **EBM (fiscalisation):** a VAT‑registered business **must** issue EBM invoices;
  any non‑EBM invoice attracts penalties. *(Finance/EBM module.)*
- **Licence lifecycle:** premises + practising licences expire and must be renewed;
  PharmaCore alerts before expiry (already surfaced on the dashboard/alerts).

---

## 6. How this maps into PharmaCore
- **`OrganizationDocument` required‑set** per org type = the §2 lists (retail vs
  wholesale vs distributor). Org **activation is blocked** until the **required**
  documents are attached with number + issue/expiry dates.
- **Pharmacist‑in‑charge**: an org must reference a `User` whose NPC **licence to
  practise** (a `UserDocument` / `License`) is on file and **not expired**.
- **Expiry alerts**: premises licence, pharmacist practising licence, and (imports)
  registration/permits all feed the existing licence‑expiry alerting.
- **Controlled‑substance quarterly report**: a scheduled job (reuse `run_scheduler`)
  compiles distribution of controlled items for the period.
- **EBM**: the Finance/EBM subsystem must fiscalise every VAT sale.

Everything here is encoded as **required / optional / conditional** exactly as the
regulator states — nothing invented.

---

### Sources
- Rwanda FDA — *Guidelines for licensing of public and private manufacturers,
  distributors, wholesalers and retailers of medical products*, Doc.
  FDISM/FDIC/GDL/005 Rev 4 (2023): [PDF](https://rwandafda.gov.rw/wp-content/uploads/2023/04/Guidelines%20on%20licensing%20of%20public%20and%20private%20manufacturers,%20distributors,wholesalers,retailers%20of%20medical%20products_Rev%204.pdf) · [Rwanda FDA](https://rwandafda.gov.rw/)
- National Pharmacy Council — *Registration & Requirements*: [pharmacycouncil.rw](https://pharmacycouncil.rw/registration-requirements/)
- RDB/RRA — business registration & TIN, VAT & EBM: [RRA – register a business](https://www.rra.gov.rw/en/domestic-tax-services/registration-de-registration/default-title)
- Context — establishing a pharmaceutical business in Rwanda: [Stabit Advocates](https://www.stabitadvocates.com/uncategorized/an-insight-on-what-it-takes-to-establish-a-pharmaceutical-business-in-rwanda/)
</content>
