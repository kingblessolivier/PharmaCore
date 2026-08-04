# PharmaCore — Testing Strategy

PharmaCore handles stock, money, and regulated documents — so tests aren't optional,
they're how we prove correctness. Every behavior change ships tests; CI gates on them.

---

## 1. The test pyramid
```
        ▲  fewer, slower, higher-confidence
  e2e   │  critical user journeys (POS sale offline→sync, order→GRN, payroll run)
  ─────  │
  integration  │  API + DB + workers together; state machines; migrations
  ───────────  │
  unit         │  services, calculators (co-pay, PAYE, FEFO), validators — many, fast
        ▼
```
Target mix ≈ **70% unit / 25% integration / 5% e2e**. Push logic down to fast unit tests.

## 2. What to test where

### Unit (fast, no IO)
- **Money & rules:** co-pay computation (per scheme/formulary), PAYE/RSSB payroll,
  tax-class selection, FEFO ordering, discrepancy math.
- **State machines:** valid/invalid transitions for order, sale `payment_status`,
  `ebm_status`, claim, payroll.
- **Validators/guards:** negative-stock block, unbalanced-journal reject,
  expired-license dispense block, Rx-required gate.
- Adapters mocked (EBM/insurer/SMS/momo).

### Integration (API + DB + workers)
- Endpoints against a real Postgres (test container) with transactions/rollback.
- **Immutability/audit:** attempting to edit a posted journal / finalized GRN /
  audit row **fails**; every mutation writes an `audit_log` row.
- **Stock invariants:** transfer and sale keep `Σ movements = on-hand`; reservations
  release on cancel.
- **Django migrations:** `makemigrations --check` (in sync) + `migrate` on a scratch DB.
- Document generation worker produces a hashed, numbered PDF record.

### End-to-end (critical journeys)
- **Offline POS sale → reconnect → sync → fiscalize** (against MockEbmProvider),
  including the **oversell conflict** path (two terminals, last pack).
- **Order → approve/allocate → dispatch → GRN finalize** produces correct stock +
  immutable documents.
- **Insured sale → adjudication → co-pay → EBM** end-to-end.
- **Monthly payroll run** yields correct net pay + payslips.
- **EOD closeout** locks an immutable snapshot and blocks with EBM errors present.

## 3. Compliance-focused tests (must-have)
- Immutability: no code path updates/deletes finalized docs, posted journals, audit,
  snapshots.
- Audit completeness: every state change is logged with who/what/when.
- Fiscalization: sale carries correct tax class; receipt stored immutably; errors retryable.
- Offline: no sale is ever lost; sync is idempotent by `(device_id, event_id)`.

## 4. Tooling & conventions
- **Backend:** `pytest` + `pytest-django`; docker Postgres for integration;
  `factory_boy`/fixtures for data; `freezegun` for time; `respx`/mocks for external
  HTTP. Coverage via `coverage.py`.
- **Frontend:** `vitest` + Testing Library (unit/component); **Playwright** for e2e.
- **Determinism:** no real network, no sleeps; seed randomness; UTC time in tests.
- Test data uses **fake** patient/insurer data — never real PII.

## 5. Coverage & gates (CI-enforced)
- **New/changed code ≥ 85%** line+branch coverage; overall ratchet upward (never down).
- Compliance-sensitive modules (`inventory, distribution, retail, insurance, ebm,
  finance`) held to a higher bar and require the immutability/audit tests.
- CI fails on: any failing test, coverage drop, or a compliance test missing for a
  compliance-sensitive diff.

## 6. Test naming & structure
- Arrange–Act–Assert; one behavior per test; descriptive names
  (`test_copay_uses_scheme_formulary_rate_not_hardcoded`).
- Mirror the source tree (`tests/<module>/…`).

## 7. Non-functional testing (Phase 7)
- **Load/perf:** POS commit < 1s; search < 300ms; sale-write throughput per branch.
- **Resilience:** external outage (EBM/insurer) → queue + retry, no data loss.
- **Security:** dependency + SAST scans in CI; periodic pen-test before go-live.
- **Accessibility:** automated a11y checks (axe) on key screens + manual keyboard pass.
- **Backup/restore drill** validated before production.
