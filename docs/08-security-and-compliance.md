# PharmaCore — Security & Compliance Design

> **Alignment note — foundational (early) doc.** PharmaCore is now framed as a **workspace of subsystems**; the research-backed specs [docs 12–19](README.md) and the [ROADMAP](../ROADMAP.md) **supersede or extend** anything here (each cites its sources). Key deltas: backend is **Django + DRF** (ADR-006, not FastAPI); the depot→retail transfer shipped as the **lean flow** — place → **approve = ship** → **receive = land**, auto-listing at the destination — with picking / driver / per-item-count logistics deferred to the Warehouse phase; and much of this is **already built** (see ROADMAP status). Verified Rwanda/international facts live in [13](13-regulatory-licensing-and-documents-rwanda.md) / [14](14-international-operational-standards.md) / [17](17-insurance-and-government.md) / [18](18-rwanda-integrations-and-statutory.md).

> How PharmaCore protects data, records every activity, resists abuse, and meets
> Rwanda's regulatory obligations (RRA EBM, Rwanda FDA / GDP, health-data privacy).
> Traces to NFR-SEC/NFR-C in the SRS. **Security is not a phase — it is a property of
> every module** (see the hardening checklist, §12).
>
> Version 0.2 · 2026-08-03

---

## 1. Authentication (proving who you are)
- **JWT via djangorestframework-simplejwt**: a **short-lived access token** (≈15–30 min)
  + a longer refresh token. Passwords hashed with **argon2id**, never stored plaintext.
- **Refresh-token rotation + blacklist**: each refresh issues a new token and
  invalidates the old; logout/compromise blacklists the token. Tokens are signed
  (HS256/RS256) with a KMS-held secret.
- **MFA (TOTP)** available for all; **enforced** for admin/finance/HR roles.
- **Brute-force protection**: account **lockout after N failed attempts** + login
  **rate-limiting** (§5). Failed and successful logins are logged (§4).
- **Password policy**: minimum length, common-password rejection (Django validators),
  rotation for privileged accounts.
- **Offline auth (POS)**: a scoped, short-lived token + a hashed local PIN lets a
  cashier keep working through an outage; the device is registered (`sync_devices`) and
  the token is **device-bound**; full re-validation on reconnect.

## 2. Authorization (what you're allowed to do) — deny by default
- **RBAC**: users hold **roles**; roles grant fine-grained **permissions**
  (`sale.create`, `payroll.approve`, `inventory.adjust`, `prescription.dispense`…).
  Default is **deny** — access requires an explicit grant.
- **Least privilege**: a cashier can't read payroll; a warehouse clerk can't post journals.
- **Tenant scoping**: every query is filtered by `organization_id` **from the token**
  server-side — a client can never widen its own scope. Cross-branch access is an
  explicit permission.
- **Object-level checks**: not just "can view sales" but "can view *this* sale" (same org).
- **License-gated capability**: `prescription.dispense` / restricted-drug approval is
  **dynamically denied** if the pharmacist's licence is expired — enforced in the
  service layer, never only in the UI.
- **Shift-gated access**: terminal (POS/warehouse) login requires an active clocked-in shift.

## 3. Encryption & data protection
- **In transit**: **TLS 1.3** everywhere (clients ↔ backend, backend ↔ RRA / insurers /
  momo / SMS). HSTS enforced; HTTP redirects to HTTPS.
- **At rest**: database and object storage encrypted with **AES-256** (managed-service
  or disk-level).
- **Application-level field encryption for the crown jewels** — encrypted in the app
  before they touch the DB, keys in a **KMS**: integration **credentials**
  (`ebm_configs.credentials_encrypted`, insurer/momo keys), **national IDs**, and
  sensitive **patient** fields (allergies, prescriptions). So a DB dump alone doesn't
  expose them.
- **Device data (offline POS)**: the local **SQLite store is encrypted (SQLCipher)**,
  holds only the branch working-set, and is purged after successful sync + retention window.
- **Key management**: keys in a KMS / secret manager; rotated on schedule and on
  suspected exposure; never in code or the frontend bundle.
- **PII minimization**: collect only what dispensing/insurance needs; never put personal
  data in URLs or query strings.

> **On "end-to-end encryption":** true *zero-knowledge* E2E — where the server itself
> cannot read the data — is **incompatible with an ERP**, because the server must search
> inventory, adjudicate insurance, compute payroll, and generate reports (it can't
> operate on data it can't decrypt). We therefore do **not** claim zero-knowledge E2E.
> What we guarantee instead: **encrypted on every hop (TLS 1.3) and at rest (AES-256),
> field-level encryption for the most sensitive data, an encrypted device DB, KMS-held
> keys, and strict access control + full logging** — the correct, achievable posture for
> this system.

## 4. Comprehensive activity, access & security logging
Two complementary streams — **nothing significant happens without a record**.

**4.1 Business audit trail (`audit_log`)** — every **state-changing** action:
who (user), what (action + entity_type + entity_id), when, **before/after** values, and
source IP. Written by the service layer on create/update/void/approve/etc. **Append-only**
— the app DB role has no UPDATE/DELETE on it (enforced by a Postgres grant).

**4.2 Security & access events** — beyond state changes, we log:
- **Auth events**: login success/failure, logout, token refresh, MFA challenges,
  lockouts, password changes.
- **Authorization events**: permission **denials** (who tried to do what) — the signal
  for probing/misconfiguration.
- **Sensitive-data access**: reads of patient clinical data and payroll (access, not just
  change) — for health-data accountability.
- **Exports & prints**: who exported/printed which report or document.
- **Config/security changes**: role/permission edits, integration credential changes,
  device registration, notification-rule changes.
- **Admin actions**: anything done through the Django admin.

**4.3 Application & infra logs** — structured **JSON logs** (structlog) with a
request/correlation id, shipped to a log aggregator (retention per policy). **Never log
secrets or full PII.** Correlate app logs ↔ `audit_log` by request id.

**4.4 Tamper-resistance & retention** — `audit_log` is append-only; logs are
write-once/retained per GDP; alerting on suspicious patterns (repeated denials, off-hours
admin actions, mass exports).

## 5. Rate limiting & abuse protection
- **API throttling (DRF)**: `AnonRateThrottle` + `UserRateThrottle` global defaults,
  plus **`ScopedRateThrottle`** for sensitive endpoints — strict on **login** and
  token-refresh (brute-force), and on export/report/bulk endpoints.
- **Login throttle + lockout**: escalating backoff per account/IP; lockout after N fails.
- **Idempotency keys** on sale/payment mutations → safe retries, no double-charge.
- **Edge protection**: reverse proxy / WAF rate limits and connection limits; body-size
  limits; optional IP allow-listing for admin.
- **Bot/DoS**: CAPTCHA is **not** used inside the app (staff tool); protection is at the
  edge + throttling.

## 6. Application & platform hardening
- **Input/output**: DRF-serializer validation on all input; ORM/parameterized queries
  (no string SQL); output encoding; **no secrets in the frontend bundle**.
- **Django security settings** (production): `DEBUG=False`, explicit `ALLOWED_HOSTS`,
  `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` (+ preload), `SESSION_COOKIE_SECURE` &
  `CSRF_COOKIE_SECURE`, `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=DENY`,
  `SECURE_REFERRER_POLICY`. `manage.py check --deploy` in CI.
- **Headers / CSP**: strict **Content-Security-Policy**, HSTS, no inline scripts in the
  SPA build; CORS locked to known origins (`django-cors-headers`).
- **Least-privilege DB roles**: the app role lacks UPDATE/DELETE on immutable tables
  (`audit_log`, finalized documents, posted journals, snapshots).
- **Dependency & code scanning in CI**: dependency audit (known CVEs) + **SAST**; SBOM on
  release; no known-critical vulns merged.
- **Secrets**: environment / secret-manager only; `.env` never committed; rotation on exposure.
- **Container/network**: minimal base images, non-root containers, private networking for
  DB/Redis, only necessary ports exposed, TLS termination at the proxy.

## 7. Auditability & immutability (GDP core)
- **`audit_log`** is append-only (see §4). **Immutable records**: finalized documents,
  EBM receipts, posted journals, and `daily_snapshots` are write-once — corrections are
  **new reversing/void records**, never edits (complete, retrievable history).
- **Document integrity**: every generated PDF carries a **SHA-256 content hash** + object
  storage **object-lock**; QR verification resolves to the stored hash.
- **Traceability**: batch → order → GRN → sale → patient is fully linkable; one recall
  query lists every holder of a batch.

## 8. Rwanda regulatory compliance
### 8.1 RRA EBM (tax)
- Fiscalize **every retail sale** via a certified `EbmProvider`; store SDC id, sequential
  receipt number, signature, QR, **tax breakdown by class (A/B/C/D)**. Register **items
  and purchases**, not only sales.
- **Certification prerequisite**: RRA **CIS certification / Developer ID** before prod
  (go-live gate). EBM error rate is monitored/alerting; EOD can't lock with EBM errors.

### 8.2 Rwanda FDA / GDP
- Track **premises and staff licenses** with expiry alerts; enforce storage conditions
  (cold-chain logs); retain complete distribution records; **controlled substances** keep
  a dispensed-medication ledger for inspection.

### 8.3 Health-data privacy
- Access to patient clinical data is permissioned **and logged** (§4.2), least-exposure by
  role; data-subject handling + retention policy documented before go-live.

## 9. Monitoring & incident response
- Alerts on: EBM error rate, sync backlog, login-failure spikes, permission-denial spikes,
  drawer variance, off-hours admin/export activity.
- **Incident response**: documented runbook (detect → contain → eradicate → recover →
  review); vulnerability reporting per [SECURITY.md](../SECURITY.md); breach-notification
  process defined before go-live.

## 10. Backup & disaster recovery
- Managed PostgreSQL with **point-in-time recovery** + daily **encrypted** backups;
  periodic **restore drills**. Object storage versioned + object-locked. The offline
  outbox is itself a resilience layer. Documented **RPO/RTO** targets.

## 11. When it's built (security is continuous, not deferred)
| Control | Lands |
|---|---|
| Auth (JWT), argon2, `audit_log`, base RBAC | **Phase 0 ✅** |
| Rate limiting (login + API), security headers, `check --deploy`, permission-denial logging | **Phase 1** (foundational) |
| Field-level encryption, sensitive-access logging, object-level perms | Phase 1–4 as those records appear |
| Dependency/SAST scanning required on merge | once CI runner is unblocked |
| Full hardening, pen-test, restore drill, incident runbook | **Phase 7** |

## 12. Hardening checklist (go-live gates)
- [ ] `DEBUG=False`, `ALLOWED_HOSTS` set, `manage.py check --deploy` clean
- [ ] TLS 1.3 + HSTS; secure cookies; CSP; CORS locked to known origins
- [ ] Rate limiting on login/refresh + sensitive endpoints; lockout tested
- [ ] MFA enforced for privileged roles; refresh-token rotation/blacklist on
- [ ] Encryption verified: transit + at rest + field-level crown jewels + device DB; keys in KMS
- [ ] Audit-log append-only enforced at DB grant level; security-event logging live
- [ ] Least-privilege DB roles; app role lacks UPDATE/DELETE on immutable tables
- [ ] Dependency + SAST scans passing; SBOM produced; no known-critical vulns
- [ ] Backup + **restore drill** passed; RPO/RTO agreed
- [ ] RBAC matrix reviewed (no cross-role/cross-tenant leakage); pen-test findings closed
- [ ] RRA CIS certification; per-drug tax class confirmed; insurer agreements + FDA licences loaded
