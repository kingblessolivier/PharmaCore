# PharmaCore — Security & Compliance Design

> How PharmaCore protects data and meets Rwanda's regulatory obligations (RRA EBM,
> Rwanda FDA / GDP, health-data privacy). Traces to NFR-SEC/NFR-C in the SRS.
>
> Version 0.1 · 2026-08-03

---

## 1. Authentication
- **Password auth** (OAuth2 password flow) → short-lived **JWT access token** +
  refresh token. Passwords hashed with **argon2id** (or bcrypt), never stored plain.
- **MFA (TOTP)** available, enforced for admin/finance roles.
- **Offline auth:** the POS caches a scoped token + a hashed local PIN so a cashier
  can keep working through an outage; re-validation happens on reconnect. Tokens
  are short-lived and device-bound (`sync_devices`).
- Account lockout after N failed attempts; all logins written to `audit_log`.

## 2. Authorization (RBAC + permissions)
- Users hold **roles**; roles grant fine-grained **permissions**
  (`sale.create`, `payroll.approve`, `inventory.adjust`, `prescription.dispense`…).
- **Least privilege:** cashier cannot read payroll; warehouse cannot post journals.
- **Scoped access:** every query is filtered by `organization_id` from the token;
  cross-branch access is an explicit permission.
- **License-gated capability:** `prescription.dispense` / restricted-drug approval
  is dynamically denied if the acting pharmacist's `license.status = EXPIRED`
  (enforced in the service layer, not just UI).
- **Shift-gated access:** terminal login requires an active clocked-in shift.

## 3. Data protection
- **In transit:** TLS 1.2+ everywhere (clients ↔ backend, backend ↔ RRA/insurers).
- **At rest:** database and object-storage encryption (AES-256). Integration
  **credentials** (EBM `developer_id`, insurer keys, momo keys) stored encrypted
  (`ebm_configs.credentials_encrypted`) via a KMS/secret manager — never in code.
- **PII minimization:** patient records only capture what dispensing/insurance
  needs (name, phone, national ID if insured, allergies). No data in URLs/query
  strings.
- **Local device data:** the POS SQLite store is encrypted; it holds only the
  branch working-set, purged after successful sync + retention window.

## 4. Auditability & immutability (GDP core)
- **`audit_log`** captures every state-changing action (who/what/when/before/after,
  IP) and is **append-only** — no update/delete grants in the app role.
- **Immutable records:** finalized documents, EBM receipts, posted journals, and
  `daily_snapshots` are write-once. Corrections are **new reversing/void records**,
  never edits — preserving a complete, retrievable history (GDP requirement).
- **Document integrity:** every generated PDF carries a **SHA-256 content hash**
  and object-storage **object-lock**; QR verification resolves to the stored hash.
- **Traceability:** batch → order → GRN → sale → patient is fully linkable; a
  single recall query lists every holder of a batch.

## 5. Rwanda regulatory compliance
### 5.1 RRA EBM (tax)
- Fiscalize **every retail sale** via a certified `EbmProvider`; store SDC id,
  sequential receipt number, signature, QR, and **tax breakdown by class (A/B/C/D)**.
- Register **items and purchases** with EBM, not only sales.
- **Certification prerequisite:** the software/vendor must hold RRA **CIS
  certification / Developer ID** before production use — tracked as a go-live gate.
- Non-compliance risk is severe (fines up to 10–20× evaded VAT, closure) → EBM
  error rate is a monitored, alerting metric, and EOD cannot lock with EBM errors.

### 5.2 Rwanda FDA / GDP
- Track **premises and staff licenses** with expiry alerts.
- Enforce storage conditions (cold-chain fields, temperature logs on shipments).
- Maintain complete, retrievable distribution records with defined retention.
- **Controlled substances:** flagged products keep a dispensed-medication ledger
  (prescriber id, patient, quantity) for regulatory inspection.

### 5.3 Health-data privacy
- Access to patient clinical data is permissioned and logged; least-exposure by
  role. Data-subject handling and retention policy documented before go-live.

## 6. Application-security practices
- Input validation via DRF serializers; ORM / parameterized queries (no string SQL).
- Output encoding / CSP on web app; no secrets in the frontend bundle.
- Rate limiting and idempotency keys on sensitive mutations.
- Dependency scanning + SAST in CI; least-privilege DB roles (app role lacks
  DELETE on immutable tables).
- Secrets via environment/secret-manager; `.env` never committed.

## 7. Backup & disaster recovery
- Managed PostgreSQL with **point-in-time recovery** + daily encrypted backups;
  periodic restore drills.
- Object storage versioned + object-locked.
- Offline outbox on devices is itself a resilience layer (no counter sale lost to
  a central outage).
- Documented RPO/RTO targets set with the business before launch.

## 8. Compliance checklist (go-live gates)
- [ ] RRA CIS certification / Developer ID obtained
- [ ] Per-drug tax class confirmed with accountant/RRA
- [ ] Insurer agreements + formularies loaded
- [ ] Rwanda FDA premises licenses recorded and valid
- [ ] Encryption (transit + at rest + credentials) verified
- [ ] Audit-log append-only enforced at DB grant level
- [ ] Backup + restore drill passed
- [ ] RBAC matrix reviewed (no cross-role data leakage)
