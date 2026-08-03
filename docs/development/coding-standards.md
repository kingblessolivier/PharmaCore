# PharmaCore — Coding Standards

Consistency lets any engineer read any file. These are enforced by tooling where
possible (formatters, linters, type-checkers in CI) so reviews focus on logic, not style.

---

## 1. General
- **Match the surrounding code.** Comment density, naming, and idioms stay local.
- Small functions, clear names, no dead code. Delete rather than comment-out.
- No secrets, tokens, or credentials in code or fixtures — ever. Use env/secret manager.
- Every state-changing operation writes to `audit_log`; never bypass it.
- Immutable records (finalized documents, posted journals, audit rows, daily
  snapshots) are **append-only** — no update/delete paths.

## 2. Python (backend — FastAPI)
- **Version:** Python 3.12. **Format:** `black`. **Lint/imports:** `ruff`. **Types:**
  `mypy` (strict on new code). All three run in CI and block merge.
- **Typing:** full type hints on public functions; Pydantic v2 models for all
  request/response schemas.
- **Structure:** module packages (`iam, catalog, …`); within each: `models.py`,
  `schemas.py`, `service.py` (business logic), `router.py` (HTTP). Routers stay thin;
  logic lives in services. Cross-module access goes through service interfaces, not
  direct table reads.
- **Naming:** `snake_case` funcs/vars, `PascalCase` classes, `UPPER_SNAKE` constants;
  singular model names (`Product`, not `Products`).
- **DB:** SQLAlchemy 2.0 typed models; **parameterized queries only** (never string
  SQL). Money is `Numeric(14,2)`. Wrap multi-write invariants (stock transfer, journal
  posting) in a transaction.
- **Errors:** raise typed exceptions mapped to RFC-7807 problem+json (see
  [API design](../07-api-design.md)); never leak stack traces to clients.
- **Async:** use `async def` for IO-bound endpoints; offload CPU/blocking work (PDF,
  EBM) to workers, never the request thread.
- **Logging:** structured (JSON) logs with request id; never log secrets or full
  patient PII.

## 3. Database migrations (Alembic)
- Every schema change ships an Alembic migration in the same PR; **never edit a
  merged migration** — add a new one.
- Migrations are **reviewed for reversibility and safety**: no destructive change
  (drop column/table) without a documented, staged plan (expand → migrate → contract).
- Test migrations `upgrade` **and** `downgrade` in CI against a scratch DB.
- Immutable tables get DB-level grants that deny UPDATE/DELETE to the app role.

## 4. TypeScript / React (frontend)
- **Format:** Prettier. **Lint:** ESLint (typescript-eslint). **Types:** `tsc`
  strict; no `any` without justification. All block merge in CI.
- **Components:** function components + hooks; one component per file; `PascalCase`
  component files. Co-locate styles.
- **Design tokens:** consume tokens/Tailwind config from the design system — **no
  hardcoded hex/spacing** (see [design tokens](../design/01-design-tokens.md)).
- **State/data:** a typed API client (generated from the OpenAPI schema where
  possible); server state via a query library; avoid prop-drilling with sensible context.
- **Accessibility is not optional:** semantic HTML, `aria-label`s on icon-only
  controls, visible focus, keyboard operability (see design docs 03/06/07).
- **Copy:** all UI strings from the strings catalog (English-only, ESL-friendly — see
  [UX writing](../design/11-ux-writing-and-terminology.md)); never hardcode text in JSX.

## 5. API conventions
Follow [07-api-design.md](../07-api-design.md): `/api/v1`, JWT bearer, cursor
pagination, RFC-7807 errors, `Idempotency-Key` on sale/payment mutations, URL
versioning (additive within a version). Server derives tenant (`organization_id`)
from the token — never trust a client-supplied org id.

## 6. Security in code
- Validate all input (Pydantic); encode all output; rate-limit sensitive endpoints.
- Least-privilege DB roles; encrypt credentials at rest via secret manager.
- Dependency + SAST scanning in CI; no known-critical vulns merged.
- Full detail: [08-security-and-compliance.md](../08-security-and-compliance.md).

## 7. Tests (see full [strategy](testing-strategy.md))
- Every behavior change ships tests. New modules start with service-layer tests.
- Deterministic; no network in unit tests (mock EBM/insurer/SMS/momo adapters).

## 8. Documentation in code
- Docstrings on non-obvious services; keep `docs/` current when behavior changes;
  add a `CHANGELOG.md [Unreleased]` line in the PR.
- Reference code as `path:line` in reviews and issues.

## 9. Tooling config (lives in repo)
`pyproject.toml` (black/ruff/mypy/pytest) · `.eslintrc` / `.prettierrc` · `alembic.ini`
· `.editorconfig` · `pre-commit` hooks running format+lint before commit.
