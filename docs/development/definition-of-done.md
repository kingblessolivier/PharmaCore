# PharmaCore — Definition of Done

A change is **done** only when every applicable box is checked. "It works on my
machine" is not done. Use this as the PR self-check.

---

## Every change
- [ ] Meets the acceptance criteria of its issue.
- [ ] Follows the [coding standards](coding-standards.md); lint/format/type-check pass.
- [ ] **Tests added/updated** and green; coverage gate met ([testing strategy](testing-strategy.md)).
- [ ] CI fully green (lint, type-check, test, migrations, build, security scan).
- [ ] Reviewed and approved (≥1 for `staging`; ≥2 incl. CODEOWNER for `main`).
- [ ] Conventional-commit history; small, focused PR.
- [ ] Docs updated (relevant `docs/` page) and a `CHANGELOG.md [Unreleased]` line added.
- [ ] No secrets, no hardcoded config, no real PII in code/tests.
- [ ] UI strings from the catalog; UI text is English-only and ESL-friendly.

## If it changes the UI
- [ ] Uses design tokens/components — no hardcoded colours/spacing.
- [ ] Accessible: keyboard operable, visible focus, `aria-label`s, contrast ≥ 4.5:1.
- [ ] Responsive at target breakpoints; `prefers-reduced-motion` respected.
- [ ] Matches the [design system](../design/README.md) (nav, overlays, states).

## If it changes the schema
- [ ] Alembic migration included; `upgrade` **and** `downgrade` tested.
- [ ] Expand-only for the release (destructive steps deferred).
- [ ] Immutable tables keep deny-UPDATE/DELETE grants.

## If it's compliance-sensitive (stock, money, documents, EBM, audit, auth)
- [ ] **2 reviews** on `staging`.
- [ ] Tests prove immutability/audit behavior is preserved.
- [ ] `audit_log` written for every state change.
- [ ] Compliance impact described in the PR (EBM/GDP/tax/insurance).
- [ ] No path makes finalized/audit records editable or deletable.

## If it touches an external integration (EBM, insurer, SMS, momo, storage)
- [ ] Behind the adapter interface; a mock exists for tests.
- [ ] Failure path handled (queue + retry, no data loss); user-facing error is clear.
- [ ] Credentials via secret manager, encrypted at rest.

## Before it can reach production
- [ ] QA/UAT passed on the **staging environment**.
- [ ] Release checklist ([release process](release-process.md#release-checklist)) satisfied.
- [ ] For go-live-gated features (real EBM): certification/tax-class prerequisites met.
