# PharmaCore — Full Data Model (all entities, tables & fields)

> **Alignment note — foundational (early) doc.** PharmaCore is now framed as a **workspace of subsystems**; the research-backed specs [docs 12–19](README.md) and the [ROADMAP](../ROADMAP.md) **supersede or extend** anything here (each cites its sources). Key deltas: backend is **Django + DRF** (ADR-006, not FastAPI); the depot→retail transfer shipped as the **lean flow** — place → **approve = ship** → **receive = land**, auto-listing at the destination — with picking / driver / per-item-count logistics deferred to the Warehouse phase; and much of this is **already built** (see ROADMAP status). Verified Rwanda/international facts live in [13](13-regulatory-licensing-and-documents-rwanda.md) / [14](14-international-operational-standards.md) / [17](17-insurance-and-government.md) / [18](18-rwanda-integrations-and-statutory.md).

> The complete database blueprint across every module. Grounded in the research
> in [00-research-findings.md](00-research-findings.md) and the decisions in
> [01-key-decisions.md](01-key-decisions.md) (offline-first, multi-insurer,
> EBM-abstracted).
>
> This is a **design document**, not migrations. Types are PostgreSQL. Nothing
> here is code yet.


> **Current reference:** this is the *design* model as first drawn. What the system
> actually persists today — every entity, field, relation and constraint — is
> generated from the code into
> [docs/reference/data-model.md](reference/data-model.md) and checked in CI, so it
> cannot drift. Read this document for intent; read that one for truth.

---

## 0. Conventions (apply to every table)

| Concern | Rule |
|---|---|
| **Primary key** | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`. UUIDs (not serials) because offline terminals mint IDs before sync (ADR-001). |
| **Money** | `NUMERIC(14,2)`. Currency is RWF (no minor unit in practice) but we keep 2dp for generality; store `currency CHAR(3) DEFAULT 'RWF'` where cross-currency is possible. |
| **Timestamps** | `created_at`, `updated_at` = `TIMESTAMPTZ DEFAULT now()`. |
| **Audit** | `created_by UUID → users(id)`, `updated_by UUID`. Who did it, always. |
| **Soft delete** | `is_active BOOLEAN` / `archived_at TIMESTAMPTZ` on master data. **Transactional & legal records are never deleted** (GDP immutability) — they are voided/reversed. |
| **Sync (offline-first)** | Transactional tables carry `origin_device_id UUID`, `client_created_at TIMESTAMPTZ`, `synced_at TIMESTAMPTZ NULL`, `sync_status` ∈ (`pending`,`synced`,`conflict`). |
| **Enums** | Implemented as `VARCHAR` + `CHECK (... IN (...))` (portable, easy to migrate) or native PG `ENUM` — TBD at build. Listed here as value sets. |
| **Multi-tenant scope** | Almost every row is scoped by `organization_id` (a depot or a retail branch). |

---

## 1. Identity & Access (`iam`) — the foundation

### `organizations`
The depot(s) and retail pharmacies (and the parent company).
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| parent_id | UUID FK→organizations | branch → company hierarchy (nullable) |
| name | VARCHAR(255) | |
| type | VARCHAR(20) | `DEPOT` \| `RETAIL` \| `HQ` |
| tin | VARCHAR(20) | RRA taxpayer ID (needed for EBM) |
| rwanda_fda_license_no | VARCHAR(100) | premises license |
| license_expiry_date | DATE | surfaced for renewal alerts |
| phone, email | VARCHAR | |
| district, sector, cell | VARCHAR | Rwanda address hierarchy |
| address_line | TEXT | |
| latitude, longitude | NUMERIC(9,6) | for logistics/mapping |
| is_active | BOOLEAN | |

### `licenses` (generic license registry — orgs *and* people)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| holder_type | VARCHAR(20) | `ORGANIZATION` \| `EMPLOYEE` |
| holder_id | UUID | polymorphic → org or employee |
| license_type | VARCHAR(50) | `PREMISES`, `PHARMACIST`, `WHOLESALE`, `RETAIL`… |
| license_number | VARCHAR(100) | |
| issuing_authority | VARCHAR(100) | Rwanda FDA / Pharmacy Council |
| issue_date, expiry_date | DATE | drives auto-revocation (see HR guardrail) |
| status | VARCHAR(20) | `ACTIVE` \| `EXPIRED` \| `SUSPENDED` |
| document_url | TEXT | scan of the license |

### `departments`
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| organization_id | UUID FK | |
| code | VARCHAR(30) | `WAREHOUSE`,`DISPATCH`,`DISPENSING`,`CASHIER`,`INSURANCE`,`FINANCE`,`HR`,`PURCHASING` |
| name | VARCHAR(100) | human-readable |

### `users`
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| organization_id | UUID FK | home org |
| department_id | UUID FK | nullable |
| employee_id | UUID FK→employees | nullable (not every user is staff, e.g. sysadmin) |
| username | VARCHAR(100) UNIQUE | |
| email | VARCHAR(255) UNIQUE | |
| phone | VARCHAR(20) | |
| password_hash | TEXT | argon2 (Django hasher) |
| full_name | VARCHAR(200) | |
| status | VARCHAR(20) | `ACTIVE`\|`SUSPENDED`\|`DISABLED` |
| last_login_at | TIMESTAMPTZ | |
| mfa_secret | TEXT | nullable |

### `roles`
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| code | VARCHAR(50) UNIQUE | `SYS_ADMIN`,`ORG_ADMIN`,`PHARMACIST`,`CASHIER`,`WAREHOUSE_CLERK`,`DISPATCHER`,`INSURANCE_CLERK`,`ACCOUNTANT`,`HR_MANAGER`,`DRIVER` |
| name | VARCHAR(100) | |
| description | TEXT | |

### `permissions`
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| code | VARCHAR(100) UNIQUE | `inventory.adjust`, `sale.create`, `payroll.approve`, `prescription.dispense`… |
| description | TEXT | |

### `role_permissions` (M:N) — `role_id`, `permission_id`
### `user_roles` (M:N) — `user_id`, `role_id`, optional `organization_id` scope

### `audit_log` (append-only — GDP requirement)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK | actor |
| organization_id | UUID FK | |
| action | VARCHAR(100) | `CREATE`/`UPDATE`/`VOID`/`APPROVE`/`LOGIN`… |
| entity_type | VARCHAR(100) | table name |
| entity_id | UUID | |
| before_json | JSONB | prior state (nullable) |
| after_json | JSONB | new state |
| ip_address | INET | |
| created_at | TIMESTAMPTZ | never updated/deleted |

---

## 2. Catalog (`catalog`) — the medicine master data

### `manufacturers`
`id, name, country, contact_info(JSONB), is_active`

### `suppliers`
Who the depot buys from (importers/manufacturers).
`id, name, tin, contact_info(JSONB), lead_time_days, is_active`

### `active_ingredients`
`id, name, atc_code VARCHAR(10)` — ATC identifies the active substance (e.g. B01AC06).

### `products` (the medicine master)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| generic_name | VARCHAR(255) | e.g. Paracetamol |
| brand_name | VARCHAR(255) | e.g. Panadol (nullable) |
| manufacturer_id | UUID FK | |
| dosage_form | VARCHAR(50) | tablet/capsule/syrup/injection/ointment… |
| strength | VARCHAR(50) | e.g. 500mg, 250mg/5mL |
| pack_size | VARCHAR(50) | e.g. "100 tablets/bottle" |
| unit_of_measure | VARCHAR(20) | tablet, bottle, vial… |
| atc_code | VARCHAR(10) | classification |
| gtin | VARCHAR(14) | GS1 barcode (smallest pack) |
| ndc_or_local_code | VARCHAR(50) | national/local drug code |
| rra_item_code | VARCHAR(50) | code registered with RRA EBM |
| tax_class | CHAR(1) | `A`/`B`/`C`/`D` — VAT class (⚠ confirm per drug) |
| requires_prescription | BOOLEAN | |
| is_controlled_substance | BOOLEAN | narcotics register |
| storage_condition | VARCHAR(50) | `AMBIENT`\|`COLD_CHAIN`\|`FROZEN` |
| min_temp_c, max_temp_c | NUMERIC(4,1) | for cold chain |
| reorder_level | INT | default min stock trigger |
| image_url | TEXT | for POS/app UI |
| leaflet_url | TEXT | patient information |
| is_active | BOOLEAN | |

### `product_ingredients` (M:N products ↔ active_ingredients)
`id, product_id, active_ingredient_id, amount NUMERIC, unit VARCHAR` — for interaction/duplication checks.

### `product_barcodes`
Multiple packaging levels / scan codes.
`id, product_id, barcode VARCHAR, packaging_level VARCHAR (EACH/BOX/CASE), units_per_level INT`

### `drug_interactions` (optional clinical dataset — see open decision)
`id, ingredient_a_id, ingredient_b_id, severity (MINOR/MODERATE/SEVERE), description`

---

## 3. Inventory (`inventory`) — batches, expiry, FEFO, per-department stock

### `inventory_batches` (the atomic stock unit)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| organization_id | UUID FK | owning depot/branch |
| product_id | UUID FK | |
| batch_number | VARCHAR(100) | manufacturer lot |
| manufacture_date | DATE | |
| expiry_date | DATE | drives FEFO |
| quantity_available | INT | `CHECK >= 0` |
| quantity_reserved | INT | locked by open orders/sales |
| wholesale_cost | NUMERIC(14,2) | cost in |
| supplier_id | UUID FK | provenance |
| storage_location | VARCHAR(100) | bin/shelf/fridge |
| received_via | VARCHAR(20) | `SUPPLIER_INTAKE`\|`GRN_TRANSFER` |
| status | VARCHAR(20) | `ACTIVE`\|`QUARANTINE`\|`EXPIRED`\|`RECALLED` |
| UNIQUE | (organization_id, product_id, batch_number) | |

### `departmental_stock` (stock split across departments within a branch)
`id, department_id, product_id, batch_number, quantity INT CHECK>=0, UNIQUE(department_id,product_id,batch_number)` — e.g. backroom vs front counter.

### `stock_movements` (immutable ledger of every quantity change)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| organization_id | UUID FK | |
| product_id, batch_number | | |
| movement_type | VARCHAR(30) | `INTAKE`,`TRANSFER_OUT`,`TRANSFER_IN`,`SALE`,`WASTAGE`,`ADJUSTMENT`,`RESERVE`,`RELEASE`,`RECALL` |
| quantity_delta | INT | signed |
| reference_type | VARCHAR(50) | `stock_order`,`retail_sale`,`grn`,`wastage_log`… |
| reference_id | UUID | link to the causing document |
| department_id | UUID FK | nullable |
| occurred_at | TIMESTAMPTZ | |
| + sync fields | | |

### `stock_adjustments` (physical count corrections)
`id, organization_id, product_id, batch_number, counted_qty, system_qty, difference, reason, approved_by, created_at`

### `wastage_logs` (expired/damaged/contaminated)
`id, organization_id, product_id, batch_number, quantity, reason (EXPIRED/DAMAGED/CONTAMINATED/RECALL), disposal_ref, logged_by, document_id, created_at`

---

## 4. Wholesale / B2B Distribution (`distribution`)

### `stock_orders` (retail → depot purchase)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| order_number | VARCHAR(30) UNIQUE | human ref (see sequences) |
| depot_id | UUID FK→organizations | supplier |
| retail_id | UUID FK→organizations | buyer |
| status | VARCHAR(20) | `DRAFT`,`PENDING`,`APPROVED`,`PICKING`,`IN_TRANSIT`,`DELIVERED`,`PARTIALLY_RECEIVED`,`CANCELLED` |
| ordered_by, approved_by | UUID FK | |
| expected_delivery | DATE | |
| notes | TEXT | |
| total_amount | NUMERIC(14,2) | |

### `order_items`
`id, order_id FK, product_id, batch_number (nullable until allocated), quantity_ordered, quantity_approved, quantity_shipped, quantity_received, price_per_unit, line_total`

### `shipments` (a truck load; supports multi-stop)
`id, shipment_number, depot_id, driver_id UUID→users, vehicle_registration, dispatched_at, status (LOADED/IN_TRANSIT/COMPLETED), temperature_log JSONB (cold chain)`

### `shipment_stops` (multi-drop waybill — one truck → many pharmacies)
`id, shipment_id, order_id, retail_id, stop_sequence INT, arrived_at, status`

### `goods_received_notes` (GRN — the transfer write-event)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| grn_number | VARCHAR(30) UNIQUE | |
| order_id | UUID FK | |
| retail_id | UUID FK | receiver |
| received_by | UUID FK→users | receiving pharmacist |
| received_at | TIMESTAMPTZ | |
| status | VARCHAR(20) | `DRAFT`\|`FINALIZED` (finalized = immutable) |
| has_discrepancy | BOOLEAN | |
| signature_ref | TEXT | digital signature |

### `grn_items`
`id, grn_id, product_id, batch_number, expiry_date, quantity_expected, quantity_received, quantity_damaged, discrepancy_flag BOOLEAN`

### `discrepancy_claims`
`id, grn_id, order_item_id, type (SHORTAGE/DAMAGE/WRONG_ITEM/EXPIRED), quantity, resolution_status, credit_note_id, notes, created_at`

---

## 5. Documents engine (`documents`)

### `document_sequences` (gapless per-org numbering)
`id, organization_id, doc_type (PO/GRN/DN/INVOICE/RECEIPT…), prefix, next_number BIGINT, year` — atomic increment for legal numbering.

### `documents` (immutable generated-PDF registry)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| organization_id | UUID FK | |
| doc_type | VARCHAR(30) | `PURCHASE_ORDER`,`PACKING_SLIP`,`DELIVERY_NOTE`,`WAYBILL`,`GRN`,`TAX_INVOICE`,`CREDIT_NOTE`,`RECEIPT`,`DISPENSING_LABEL`,`PAYSLIP`,`WASTAGE`… |
| doc_number | VARCHAR(30) | from sequence |
| reference_type, reference_id | | source entity |
| file_url | TEXT | object storage (write-once) |
| content_hash | VARCHAR(64) | SHA-256 for tamper-evidence |
| qr_code_data | TEXT | transaction QR |
| generated_by | UUID FK | |
| generated_at | TIMESTAMPTZ | |
| is_finalized | BOOLEAN | once true → read-only |

---

## 6. Retail POS & Dispensing (`retail`)

### `customers` (patients — optional unless Rx/insurance)
`id, organization_id, full_name, phone, national_id (nullable), date_of_birth, allergies JSONB, notes` — for patient profile / interaction checks.

### `customer_insurance` (a patient's cards)
`id, customer_id, insurance_scheme_id FK, policy_number, valid_until, is_primary`

### `prescriptions`
`id, customer_id, prescriber_name, prescriber_license, issue_date, image_url, status (PENDING/VERIFIED/DISPENSED), verified_by UUID→users`

### `prescription_items`
`id, prescription_id, product_id, dosage_instruction, quantity_prescribed, quantity_dispensed`

### `cash_sessions` (drawer per cashier per shift — EOD reconciliation)
`id, organization_id, cashier_user_id, opened_at, opening_float, closed_at, expected_cash, counted_cash, variance, status (OPEN/CLOSED)`

### `retail_sales` (the state machine)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | UUID minted on device (offline) |
| sale_number | VARCHAR(30) | |
| organization_id | UUID FK | branch |
| cashier_user_id | UUID FK | |
| dispensed_by | UUID FK | licensed pharmacist (nullable for OTC) |
| customer_id | UUID FK | nullable |
| prescription_id | UUID FK | nullable |
| gross_amount | NUMERIC(14,2) | before tax/insurance |
| tax_amount | NUMERIC(14,2) | |
| insurance_covered_amount | NUMERIC(14,2) | |
| patient_copay_amount | NUMERIC(14,2) | |
| net_amount | NUMERIC(14,2) | payable now |
| payment_status | VARCHAR(25) | `DRAFT`,`PENDING_INSURANCE`,`AWAITING_COPAY`,`PAID`,`CANCELLED` |
| ebm_status | VARCHAR(20) | `PENDING_CLAIM`,`READY_FOR_EBM`,`SENT_TO_EBM`,`EBM_ERROR`,`FISCALIZED` |
| sold_at | TIMESTAMPTZ | |
| + sync fields | | offline-first |

### `retail_sale_items`
`id, sale_id FK, product_id, batch_number (manually picked, FEFO-suggested), quantity_sold, unit_price, line_tax, line_total, dispensing_label_id`

### `payments` (a sale may have several — split cash/momo/insurance)
`id, sale_id FK, method (CASH/MOBILE_MONEY/CARD/INSURANCE), amount, reference (momo txn id), received_at`

---

## 7. Insurance (`insurance`) — multi-insurer (ADR-002)

### `insurance_schemes`
`id, name (CBHI/RSSB, RAMA, MMI, Radiant…), scheme_type (COMMUNITY/PUBLIC/PRIVATE), default_coverage_pct NUMERIC(5,2), is_active`

### `organization_insurance_agreements` (pharmacy ↔ scheme, M:N)
`id, organization_id, insurance_scheme_id, agreement_number, coverage_pct_override, valid_from, valid_to, status`

### `scheme_formulary` (which drugs a scheme covers, at what rate)
`id, insurance_scheme_id, product_id, is_covered BOOLEAN, coverage_pct_override, max_price` — the sale engine reads this.

### `insurance_claims` (post-sale, batched)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| claim_number | VARCHAR(30) | |
| sale_id | UUID FK | |
| insurance_scheme_id | UUID FK | |
| customer_id | UUID FK | |
| amount_claimed | NUMERIC(14,2) | |
| amount_approved | NUMERIC(14,2) | |
| patient_copay | NUMERIC(14,2) | |
| status | VARCHAR(25) | `DRAFT`,`SUBMITTED`,`PARTIALLY_APPROVED`,`FULLY_APPROVED`,`REJECTED` |
| manifest_id | UUID FK | grouped submission |
| processed_at | TIMESTAMPTZ | |

### `claim_manifests` (periodic batch to an insurer)
`id, insurance_scheme_id, organization_id, period_start, period_end, total_amount, status, submitted_at, document_id`

---

## 8. EBM / Fiscalization (`ebm`) — abstracted (ADR-003)

### `ebm_configs` (per organization)
`id, organization_id, provider (OSDC/VSDC/MOCK), tin, sdc_id, developer_id, api_base_url, credentials_encrypted TEXT, is_active`

### `ebm_receipts` (fiscal record archive)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| sale_id | UUID FK | |
| ebm_invoice_number | VARCHAR(50) UNIQUE | govt serial |
| receipt_type | VARCHAR(10) | normal/refund/copy |
| sdc_id | VARCHAR(50) | |
| internal_data | TEXT | from SDC |
| signature | TEXT | cryptographic |
| qr_code_url | TEXT | verification |
| tax_breakdown | JSONB | per class A/B/C/D |
| status | VARCHAR(20) | `SIGNED`\|`ERROR` |
| generated_at | TIMESTAMPTZ | |

### `ebm_purchase_registrations` (EBM also tracks purchases in)
`id, organization_id, reference_type, reference_id (supplier intake / GRN), payload JSONB, status, registered_at`

---

## 9. HR & Payroll (`hr`) — with real Rwanda statutory rates

### `employees`
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK | login link (nullable) |
| organization_id | UUID FK | branch |
| department_id | UUID FK | |
| first_name, last_name | VARCHAR | |
| national_id | VARCHAR(20) UNIQUE | |
| professional_license_id | UUID FK→licenses | drives dispensing rights |
| job_title | VARCHAR(100) | |
| employment_type | VARCHAR(20) | `FULL_TIME`/`PART_TIME`/`CONTRACT` |
| employment_status | VARCHAR(20) | `PROBATION`/`ACTIVE`/`SUSPENDED`/`TERMINATED` |
| hire_date, end_date | DATE | |
| base_salary | NUMERIC(14,2) | gross monthly |
| bank_account, momo_number | VARCHAR | for remittance |

### `attendance_logs`
`id, employee_id, clock_in, clock_out, ip_address INET, geo_lat/geo_lng, status (PRESENT/LATE/ABSENT/LEAVE), shift_id FK`

### `shifts` & `shift_assignments`
`shifts: id, organization_id, name, start_time, end_time` · `shift_assignments: id, shift_id, employee_id, work_date`

### `leave_requests`
`id, employee_id, leave_type (ANNUAL/SICK/MATERNITY/UNPAID), start_date, end_date, days, status (PENDING/APPROVED/REJECTED), approved_by`

### `statutory_rates` (config, versioned — so 2025→2030 pension phasing is data, not code)
`id, country CHAR(2), rate_type (PAYE_BRACKET/PENSION_EMP/PENSION_ER/MEDICAL_EMP/MEDICAL_ER/MATERNITY/CBHI/OCCUPATIONAL), band_min, band_max, rate_pct, effective_from, effective_to`
> Seed (2025): PAYE 0/60k=0%, 60k–100k=10%, 100k–200k=20%, >200k=30%; Pension 6%+6%; Medical 7.5%+7.5%; Maternity 0.3%+0.3%; CBHI 0.5% (emp); Occupational 2% (employer).

### `payroll_runs`
`id, organization_id, period_start, period_end, status (DRAFT/APPROVED/PAID), approved_by, created_at`

### `payroll_records`
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| payroll_run_id | UUID FK | |
| employee_id | UUID FK | |
| gross_base | NUMERIC(14,2) | pro-rated for absences |
| overtime_commission | NUMERIC(14,2) | from sales/fulfillment targets |
| taxable_income | NUMERIC(14,2) | after deductible employee contributions |
| pension_employee, pension_employer | NUMERIC(14,2) | |
| medical_employee, medical_employer | NUMERIC(14,2) | |
| maternity_employee, maternity_employer | NUMERIC(14,2) | |
| cbhi_employee | NUMERIC(14,2) | |
| paye | NUMERIC(14,2) | |
| net_pay | NUMERIC(14,2) | |
| payment_status | VARCHAR(20) | `UNPAID`/`APPROVED`/`PAID` |
| payslip_document_id | UUID FK | |

### `salary_components` (allowances/bonuses/deductions definitions)
`id, employee_id, component_type (ALLOWANCE/BONUS/DEDUCTION), name, amount, is_recurring`

---

## 10. Finance & Accounting (`finance`) — immutable double-entry

### `accounts` (chart of accounts)
`id, organization_id, code VARCHAR, name, account_type (ASSET/LIABILITY/EQUITY/REVENUE/EXPENSE), normal_balance (DEBIT/CREDIT), parent_account_id (hierarchy), is_active`

### `fiscal_periods`
`id, organization_id, name, start_date, end_date, status (OPEN/CLOSED/LOCKED)`

### `journal_entries` (must balance; immutable once posted)
`id, organization_id, entry_number, entry_date, description, reference_type, reference_id, status (DRAFT/POSTED/REVERSED), posted_by, posted_at`

### `journal_lines`
`id, journal_entry_id FK, account_id FK, side (DEBIT/CREDIT), amount NUMERIC(14,2) CHECK>0`
> Rule enforced at DB/service level: **Σdebits = Σcredits per entry**. Corrections are new reversing entries, never edits.

### `receivables` (insurer aging — who owes the pharmacy)
`id, organization_id, insurance_scheme_id, claim_manifest_id, amount, due_date, amount_paid, status (OPEN/PARTIAL/PAID/OVERDUE)`

### `expenses`
`id, organization_id, category (RENT/UTILITY/SALARY/SUPPLIES…), amount, expense_date, vendor, document_url`

---

## 11. Reporting & operations (`reporting`)

### `daily_snapshots` (immutable EOD closeout archive)
`id, organization_id, snapshot_date, total_sales, total_cost, gross_profit, cash_collected, insurance_billed, ebm_fiscalized_count, stock_value, closed_by, created_at` — never modified retroactively.

### `eod_closeouts` (the wizard's audit record)
`id, organization_id, business_date, cash_variance, unsynced_claims_count, ebm_errors_count, status (IN_PROGRESS/LOCKED), performed_by, locked_at`

### `notifications`
`id, organization_id, user_id, type (LOW_STOCK/EXPIRY/LICENSE_EXPIRY/CLAIM_APPROVED/EBM_ERROR/DISCREPANCY), payload JSONB, is_read, created_at`

### `reorder_rules`
`id, organization_id, product_id, min_stock, max_stock, auto_generate_po BOOLEAN` — triggers draft POs to the depot.

---

## 12. Cross-cutting: offline sync

### `sync_devices`
`id, organization_id, device_name, device_type (POS/MOBILE), last_seen_at, app_version, is_authorized`

### `sync_outbox` (per-device queue of actions to replay)
`id, origin_device_id, entity_type, entity_id, operation (INSERT/UPDATE), payload JSONB, client_created_at, status (PENDING/SENT/ACKED/CONFLICT), server_ack_at`

### `sync_conflicts`
`id, entity_type, entity_id, device_id, conflict_reason (OVERSELL/STALE_UPDATE), server_state JSONB, device_state JSONB, resolution (PENDING/RESOLVED), resolved_by`

---

## 13. Collaboration, Notifications & Tools (`workspace`)
See [10-collaboration-notifications-and-tools.md](10-collaboration-notifications-and-tools.md).
The `notifications` table (in §11) stays as the in-app record; these add the rest.

### Communication
- **`comments`** — threaded, attach to any record: `id, organization_id, entity_type,
  entity_id, parent_id (thread), author_id, body, is_edited, is_struck, created_at`.
- **`comment_mentions`** — `id, comment_id, mentioned_user_id, notified_at`.
- **`conversations`** — `id, organization_id, type (DIRECT/GROUP/DEPARTMENT), title,
  department_id (nullable), created_by, created_at`.
- **`conversation_members`** — `id, conversation_id, user_id, last_read_at, muted`.
- **`messages`** — `id, conversation_id, sender_id, body, created_at` (+ sync fields for POS).
- **`message_receipts`** — `id, message_id, user_id, delivered_at, read_at`.
- **`announcements`** — `id, organization_id, audience (ORG/BRANCH/ROLE), audience_ref,
  title, body, requires_ack, created_by, created_at`; **`announcement_reads`**
  `id, announcement_id, user_id, read_at, acknowledged_at`.
- **`tasks`** — `id, organization_id, title, description, assignee_user_id,
  assignee_role, reference_type, reference_id, due_date, status (OPEN/DONE/CANCELLED),
  created_by, created_at`.
- **`shift_notes`** — `id, organization_id, business_date, body, author_id, created_at` (append-only).

### Notifications (handling)
- **`notification_preferences`** — `id, user_id, notification_type, channel
  (IN_APP/EMAIL/SMS/PUSH), enabled` (mandatory types can't be disabled).
- **`notification_deliveries`** — `id, notification_id, channel, status
  (QUEUED/SENT/FAILED), provider_ref, sent_at, error`.

### Tools (mostly stateless — few tables)
Calculators reuse core engines (co-pay, PAYE, pricing, FEFO) and store nothing.
Optional persisted pieces:
- **`knowledge_articles`** — `id, organization_id, title, body, category, is_published,
  author_id, updated_at` (SOP/wiki).
- (Scratchpad notes can be a single `user_notes` row per user, or client-local.)

---

## Entity map (how the big pieces connect)

```
organizations ─┬─< departments ─< users ─< user_roles >─ roles ─< role_permissions >─ permissions
               ├─< licenses
               ├─< inventory_batches >── products ──< product_ingredients >── active_ingredients
               │        │                   │
               │        │                   └── manufacturers, suppliers, product_barcodes
               │        └─< stock_movements (immutable) / departmental_stock / wastage_logs
               ├─< stock_orders ─< order_items         (retail ⇄ depot)
               │        └─< shipments ─< shipment_stops
               │        └─< goods_received_notes ─< grn_items ─< discrepancy_claims
               ├─< retail_sales ─< retail_sale_items ─→ inventory_batches
               │        ├─< payments
               │        ├─< insurance_claims ─> insurance_schemes ─< scheme_formulary
               │        └─< ebm_receipts        (via ebm_configs / EbmProvider)
               ├─< employees ─< attendance_logs / payroll_records >─ payroll_runs
               │        └─ statutory_rates (config)
               ├─< accounts ─< journal_lines >─ journal_entries
               └─< daily_snapshots / eod_closeouts / notifications
documents (immutable) + document_sequences  ← generated from many of the above
sync_devices / sync_outbox / sync_conflicts  ← offline-first plumbing
audit_log  ← writes for every state change
```

---

## Procurement & imports (`apps/procurement`) — shipped

The buy side. Org-scoped on the **buying** organization; money is held in the
document's own `currency` with an `exchange_rate` to RWF, and anything that reaches
inventory is base-currency and **landed**.

```
catalog.suppliers ─┬─ supplier_profiles (1:1 standing/terms/banking/scorecard)
                   ├─< supplier_licences        (GDP qualification gate)
                   ├─< supplier_price_agreements (effective-dated, volume breaks)
                   └─< supplier_evaluations      (scored from posted receipts)

purchase_requisitions ─< requisition_lines
        │  (approved, consolidated at HQ)
        ▼
request_for_quotations ─< rfq_lines
        └─< supplier_quotes ─< supplier_quote_lines      (award → PO)
        ▼
purchase_orders ─< purchase_order_lines
        ├── import_consignments ─< landed_cost_components   (allocated into unit cost)
        ├─< goods_receipts ─< goods_receipt_lines → inventory.batches (+ QualityCheck)
        └─< supplier_invoices ─< supplier_invoice_lines     (3-way match)
                     ├─< supplier_notes (debit / credit)
                     └── finance.supplier_bills (payable + GL)

number_sequences   ← gapless per (org, domain, kind, year) document numbering
```

**Invariants**
- A PO cannot be **approved** if the supplier is suspended/blacklisted or a *required*
  licence is missing, unverified or expired.
- A goods receipt cannot be **posted** without a batch number, and never with an
  already-expired batch; posting is irreversible (it writes the immutable ledger).
- A supplier invoice with a match variance cannot be **submitted** without an audited
  override reason; approval is done by the approvals engine, never the requester.
- GL: receipt posts `Dr 1200 Inventory / Cr 2150 GRNI`; invoice approval posts
  `Dr 2150 GRNI (+ Dr 5000 price variance) (+ Dr 1300 VAT input) / Cr 2000 AP`;
  a debit/credit note posts `Dr 2000 AP / Cr 5000`.

---

## Table count summary

~70 tables across 13 modules (incl. the `workspace` collaboration/notifications/tools
layer). Foundation (iam + catalog + inventory) is ~20 of them and is what everything
else references — which is why we build it first.

## Sources
- GS1/GTIN & drug master data: https://www.tracktracerx.com/gtins/ · SPHN drug concepts: https://sphn-semantic-framework.readthedocs.io/en/latest/concepts_guidelines/drug_guidelines.html · USAID GHSC master-data template: https://www.ghsupplychain.org/
- Rwanda PAYE/RSSB 2025 rates: https://netpipo.com/ · https://www.countrytaxcalc.com/tax-guides/africa/rwanda-paye-guide-2026/ · https://www.playroll.com/payroll/rwanda
- Double-entry schema: https://blog.journalize.io/posts/an-elegant-db-schema-for-double-entry-accounting/ · https://developer.squareup.com/blog/books-an-immutable-double-entry-accounting-database-service/
- (plus all sources in 00-research-findings.md)
