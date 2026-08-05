# Field, Document & Approval Requirements (completeness spec)

Built to **Finacle‑grade completeness**: this document enumerates *every* field and
document each core object can require, and the approval engine that governs changes.
Legend for each attribute: **R** = always required · **O** = optional · **C** =
conditional (required only when a trigger applies, e.g. cold‑chain temps only when
storage = refrigerated). "✔ built" marks what already exists in the data model; the
rest is the target.

> Principle: build as if no one will ever come back to fill the gap. A field that is
> "sometimes needed but not always" is added now and marked **C** — never omitted.

---

## 1. Medicine / Catalog (`Product`)

### 1.1 Identity & classification
| Field | R/O/C | Notes |
|---|---|---|
| generic_name (INN) | R ✔ | International non‑proprietary name |
| brand_name | O ✔ | |
| manufacturer | R ✔ | FK Manufacturer |
| marketing_authorization_holder | O | licence holder (may differ from maker) |
| dosage_form | R ✔ | tablet/capsule/syrup/injection/… |
| strength | R ✔ | e.g. 500 mg |
| route_of_administration | R ✔ | oral/IV/IM/topical/… |
| atc_code | O ✔ | WHO ATC classification |
| therapeutic_class | O | e.g. "Antibiotic – penicillins" |
| pharmacologic_class | O | mechanism family |
| gtin / barcode(s) | O ✔ | + `ProductBarcode` per packaging level ✔ |
| pack_size (text) + units_per_pack (int) | R ✔ | |
| unit_of_measure | R ✔ | tablet, ml, vial |

### 1.2 Regulatory & legal
| Field | R/O/C | Notes |
|---|---|---|
| fda_registration_number (Rwanda FDA) | R ✔ | product registration |
| registration_expiry_date | C | required if registered |
| rra_item_code (EBM) | O ✔ | |
| tax_class | R ✔ | A/B/C/D (VAT) |
| requires_prescription (Rx) | R ✔ | |
| is_controlled_substance | R ✔ | |
| controlled_schedule | C ✔ | required if controlled (e.g. "Schedule 2") |
| narcotic / psychotropic flags | C | sub‑classes of controlled |
| hsn_customs_code | O | imports |
| country_of_origin | O | |

### 1.3 Clinical safety (the "ALL" the user emphasised)
| Field | R/O/C | Notes |
|---|---|---|
| indications | O | what it treats |
| **contraindications** | O | conditions where it must NOT be taken |
| **drug_interactions** | O | structured list: interacts‑with product/ingredient + severity + note |
| **warnings_precautions** | O | boxed/black‑box warnings, cautions |
| **side_effects / adverse_reactions** | O | common/serious |
| **dosage_instructions** | O | adult/child/renal/hepatic |
| max_daily_dose | O | overdose guard |
| overdose_management | O | |
| **pregnancy_category** | O | e.g. A/B/C/D/X |
| lactation_safety | O | |
| pediatric_use / geriatric_use | O | |
| driving_machinery_warning | O | |
| storage_after_opening / shelf_life_after_opening | O | e.g. syrups |
| counseling_points | O | what the pharmacist tells the patient |

> Drug interactions & contraindications are **structured**, not free text:
> `ProductInteraction(product, interacts_with_product | interacts_with_ingredient,
> severity[minor/moderate/major], effect, management)` and
> `ProductContraindication(product, condition, severity, note)`. This lets the POS
> **warn at dispensing** ("interacts with X the patient is also buying", "contra‑
> indicated in pregnancy").

### 1.4 Logistics, storage & handling
| Field | R/O/C | Notes |
|---|---|---|
| storage_condition | R ✔ | ambient/cold‑chain/frozen |
| min_temp_c / max_temp_c | C ✔ | required if cold‑chain/frozen |
| light_sensitive / humidity_sensitive | O | handling |
| hazardous / cytotoxic | O | special handling |
| weight / volume / dimensions | O | warehouse & shipping |
| image_url, leaflet_url | O ✔ | patient info leaflet |

### 1.5 Commercial (per‑pharmacy, on `PharmacyProduct`)
| Field | R/O/C | Notes |
|---|---|---|
| retail_price / wholesale_price | C ✔ | by org type |
| avg_cost, margin | derived ✔ | |
| reorder_level / reorder_quantity / min_stock_level | O ✔ | |
| max_stock_level | O | over‑stock guard |
| shelf/bin location | O | (warehouse phase) |

**New models to add:** `ProductInteraction`, `ProductContraindication`, and
optional clinical fields on `Product`. Catalog form gains a **Clinical** tab.

---

## 2. Organization / Pharmacy (`Organization`) — registration + documents

### 2.1 Fields
| Field | R/O/C | Notes |
|---|---|---|
| legal_name / trade_name | R | (currently single `name` ✔) |
| type | R ✔ | depot / retail / HQ |
| parent (HQ) | C ✔ | required for a branch of a chain |
| registration_number (RDB) | R (C for sub‑branch) ✔ | |
| tin (RRA) | R ✔ | |
| rwanda_fda_license_no + expiry | R ✔ | premises operating licence |
| pharmacist_in_charge (user) + licence | R | a pharmacy must have a responsible pharmacist |
| currency | R ✔ | |
| contact_person, phone, email | R ✔ | |
| province→district→sector→cell→village | R ✔ | cascading selection |
| address_line, GPS lat/long | O ✔ | |
| logo_url | O ✔ | on documents |
| operating_hours | O | |
| bank_account / MoMo details | O | for settlements/payroll |
| is_active | R ✔ | |

### 2.2 Documents required to operate (`OrganizationDocument`)
Each = file + number + issue/expiry date + verified flag. Required vs optional
**by org type**:

| Document | Depot | Retail | HQ |
|---|---|---|---|
| Premises operating licence (Rwanda FDA) | R | R | O |
| Wholesale / distribution licence | R | — | O |
| Retail pharmacy licence | — | R | — |
| RDB company registration certificate | R | R | R |
| RRA tax registration (VAT/TIN) | R | R | R |
| Pharmacist‑in‑charge professional licence | R | R | O |
| Import licence | C (if importing) | — | O |
| Controlled‑substances handling permit | C | C | — |
| Cold‑chain / GDP compliance certificate | C | O | — |
| Tenancy / premises ownership proof | O | O | O |
| Insurance (liability) | O | O | O |

**New model:** `OrganizationDocument(organization, doc_type, number, file,
issue_date, expiry_date, is_verified)`. Registration wizard blocks activation until
**R** documents for that type are present; expiry feeds the licence‑alert system.

---

## 3. User / Employee (`User` + `EmployeeProfile`)

**Who may create users:** SYS_ADMIN, HR, or a pharmacy **ORG_ADMIN** only. No self
sign‑up. Creation of privileged roles (pharmacist, org‑admin) routes through the
**approval engine** (§5).

### 3.1 Identity & account
| Field | R/O/C |
|---|---|
| first_name, last_name | R ✔ |
| username, email | R ✔ |
| password (set/reset) | R ✔ |
| phone | O ✔ |
| national_id / passport | R |
| date_of_birth, gender | O |
| photo | O |
| organization + branch | R ✔ |
| department | O ✔ |
| roles (RBAC) | R ✔ |
| reports_to (supervisor) | O | drives approval routing |
| is_active | R ✔ |

### 3.2 Employment (`EmployeeProfile`, for HR)
| Field | R/O/C |
|---|---|
| employee_number | R |
| job_title, employment_type (full/part/contract) | R |
| hire_date, probation_end, contract_end | R / C |
| salary / pay grade, pay frequency | C (staff) |
| bank account / MoMo for payroll | C |
| RSSB number, PAYE status | C |
| next_of_kin (name, relation, phone) | R |
| emergency_contact | R |
| address | O |
| professional_licence (link to `License`) | C (pharmacist) |

### 3.3 Documents captured at creation (`UserDocument`)
| Document | R/O/C |
|---|---|
| National ID / passport | R |
| Professional/pharmacist licence | C (dispensing roles) |
| Academic/qualification certificates | O |
| Employment contract (signed) | R (staff) |
| Police clearance / good‑conduct | O |
| Medical fitness certificate | O |
| Signed SOP acknowledgements | C (see HR training) |
| Bank/MoMo proof | C (payroll) |

**New models:** `EmployeeProfile`, `UserDocument`. User‑create wizard = Identity →
Role & scope → Employment → Documents → (approval if privileged).

---

## 4. Approval engine (reusable, cross‑module)

One engine, used by user creation, POs/transfers, price changes, payroll runs,
leave, write‑offs, recalls, etc. — **not** per‑feature approvals.

### 4.1 Model
- `ApprovalRequest(id, type, entity_type, entity_id, requested_by, organization,
  status[PENDING/CLAIMED/APPROVED/REJECTED/RETURNED/ESCALATED], claimed_by,
  claimed_at, sla_due_at, decided_by, decided_at, decision_note, current_step)`
- `ApprovalStep` / `ApprovalPolicy(type, org, levels[])` — defines who approves
  what (by role/level) and the SLA per level.
- `ApprovalEvent(request, actor, action, at, note)` — full audit.

### 4.2 Rules (user‑specified)
1. **Central inbox** — one "Pending approvals" screen aggregates everything a user
   is eligible to approve.
2. **No self‑approval** — the requester's approver is their `reports_to` supervisor
   or a senior at the required level; the requester can never approve their own.
3. **Claim‑to‑lock** — an approver **claims** an item; it then shows only to them
   (peers no longer see it), preventing double‑handling.
4. **SLA timer** — each item has `sla_due_at`; a scheduled job (reuse
   `run_scheduler`) checks expiries.
5. **Timeout → return** — on expiry, unclaim + set **RETURNED** to the requester to
   **resend** (re‑submit restarts the clock). Escalation policies may instead bump
   to the next level.
6. **Senior oversight** — senior leaders see **all** pending approvals in their
   scope and can **forward/reassign** an item to themselves or another approver.
7. **Audit** — every claim/approve/reject/return/forward is logged.

### 4.3 UI
- **Approvals inbox** (Connect/Admin): tabs *To act* (claimable/claimed by me),
  *Watching* (senior: all pending), *Mine* (requests I raised). Each row shows type,
  requester, age, **SLA countdown**, claim/approve/reject/forward actions.
- A bell notification on new/returned/escalated approvals.

---

## 5. Module operation catalogues (what each module must do — in full)

### 5.1 People / HR (deep)
Full employee lifecycle:
1. **Recruitment** — requisition → job posting → applicants → shortlist →
   interviews (scheduling + scorecards) → offer (approval) → acceptance.
2. **Onboarding** — create user+profile, documents checklist, asset issue,
   SOP/training assignment, orientation checklist.
3. **Employee records** — the §3 profile + documents + licence/dispensing rights.
4. **Attendance & time** — clock in/out (or shift roster), timesheets, overtime,
   absence.
5. **Shifts & rostering** — schedule per branch/department, swaps, coverage.
6. **Leave** — types (annual/sick/maternity/unpaid), balances, request → approval →
   calendar.
7. **Training & competency** — SOP library, assign training, **read‑&‑sign**
   acknowledgement, competency assessments, **controlled‑drug assurance checks**,
   re‑assessment every N months, certificates, expiry alerts.
8. **Payroll** — statutory config (PAYE, RSSB), payroll run (approval), payslips,
   bank/MoMo remittance file, deductions/advances.
9. **Performance** — reviews, goals, appraisals.
10. **Disciplinary & grievances**, **offboarding** (exit checklist, access
    revocation, final pay, licence hand‑back).

### 5.2 Finance (deep — "many things")
- **AP** (supplier bills, aging, payment runs) · **AR** (buyers, insurers, aging ✔).
- **General ledger** — chart of accounts, **balanced immutable journals**,
  auto‑posting from ops (sale, transfer, intake, payroll), fiscal periods.
- **Banking & cash** — cash‑drawer reconciliation, bank/MoMo reconciliation,
  petty cash, expenses/claims.
- **Tax** — VAT returns, **EBM** fiscalization, withholding.
- **Budgeting & forecasting**, **EOD closeout** (immutable daily snapshot).
- **Consolidation** — HQ rollup across branches.
- **Documents**: invoices, credit notes ✔, receipts ✔, statements, payslips,
  purchase orders, remittance advices, **financial statements** (P&L, balance
  sheet, cash flow, trial balance).
- **Charts**: revenue/margin trends, cash position, receivables/payables aging,
  expense breakdown, branch comparison, budget vs actual.

### 5.3 Retail — over‑the‑counter selling (great UX)
- Manual product search (name/barcode) → add to cart; **as items are added the
  running total, VAT, and per‑line prices update in clean increments**, itemised,
  never cluttered.
- FEFO batch auto‑pick ✔, expired block ✔, **Rx/controlled dispensing gate** ✔,
  **interaction/contraindication warning** at add‑time (from §1.3).
- Split payment (cash/MoMo/card/insurance), change, cash‑drawer session, hold/park,
  returns ✔ + credit note ✔, reprint, **offline‑first**.
- Fast keyboard flow; large touch targets for a busy counter.

### 5.4 Online selling
- Patient storefront (browse OTC, search), **prescription upload** for Rx items
  (pharmacist verifies before fulfilment), cart, delivery / click‑&‑collect,
  order tracking, online payment, links to the same stock/price engine.

### 5.5 Leader / executive dashboard
- KPI cards (sales, margin, cash, receivables, stock value, service level),
  **multi‑branch** comparison, trend charts, **pending‑approvals** summary,
  alerts (expiry/licence/low‑stock/overdue), drill‑down to a branch. Role‑aware
  (branch manager vs HQ executive).

### 5.6 Logistics & documents
- Every movement produces the right document: **PO, proforma, commercial invoice,
  packing slip, delivery note ✔, waybill, GRN ✔, tax invoice ✔, credit note ✔,
  receipt ✔, bill of lading / customs (imports)** — all numbered, hashed, QR‑verifiable,
  in the vault ✔.

---

## 6. Build order (so completeness lands incrementally)
1. **Approval engine** (§4) — cross‑cutting; unblocks user‑creation & every module.
2. **Catalog clinical completeness** (§1.3) — interactions/contraindications +
   POS warnings; and **Organization/User documents** (§2.2, §3.3) with the
   registration/creation wizards.
3. Then per‑module depth: **HR**, **Finance GL/closeout**, **OTC polish**,
   **Online**, **Leader dashboard** — each built to the catalogues above.

Nothing here is a stub target: each item is added with all its fields/documents and
its required/optional/conditional rule, the first time it is built.
