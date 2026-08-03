# PharmaCore — Release Process

How a set of merged, QA'd changes on `staging` becomes a tagged production release
on `main`. Small, frequent, reversible releases beat big risky ones.

---

## Versioning (SemVer)
`MAJOR.MINOR.PATCH` — e.g. `1.4.2`.
- **MAJOR** — incompatible API change / breaking migration (`feat!`/`BREAKING CHANGE`).
- **MINOR** — new backwards-compatible functionality (`feat`).
- **PATCH** — backwards-compatible bug fixes (`fix`, `perf`).
Pre-1.0 (`0.x`): minor may include breaking changes as the system stabilizes; call
them out clearly. The version is derived from the Conventional Commits since the last tag.

## Release cadence
Release from `staging` whenever a coherent, QA-passed set is ready (target: a regular
cadence, e.g. weekly, plus hotfixes as needed). Don't batch huge releases.

## Steps
1. **Freeze & verify staging.** Ensure `staging` is green and QA/UAT passed on the
   staging environment.
2. **Determine the version** from the Conventional Commits since the last tag
   (feat→minor, fix→patch, breaking→major).
3. **Update `CHANGELOG.md`:** move `[Unreleased]` items into a new
   `[X.Y.Z] — YYYY-MM-DD` section; reset `[Unreleased]`.
4. **Open the promotion PR `staging → main`** (2 reviews incl. CODEOWNER, CI green).
5. **Merge to `main`** (merge-commit/fast-forward — preserve the release set).
6. **Tag the release:** `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.
   The tag triggers the production deploy ([CI/CD](ci-cd.md)).
7. **Verify production** smoke tests pass; watch dashboards/alerts for a bake period.
8. **Announce** the release (notes from the changelog).

## Migrations in a release
- Only **expand/additive** migrations ship with the app that still supports the old
  schema; destructive (contract) steps go in a **later** release once nothing uses them.
- Migrations run before traffic shifts; failure aborts + rolls back.

## Hotfix release
See [git workflow §7](git-workflow.md#7-hotfixes-production-emergencies): branch from
`main`, PR to `main`, tag `vX.Y.(Z+1)`, deploy, then **back-merge `main → staging`**.

## Rollback
Redeploy the previous tag (images retained for N releases). Because migrations are
expand-only, the prior app version stays schema-compatible. PITR is the last resort.
See [CI/CD §6](ci-cd.md#6-rollback).

## Release checklist
- [ ] `staging` green; QA/UAT signed off
- [ ] Version decided (SemVer) from commits
- [ ] `CHANGELOG.md` updated; docs current
- [ ] Migrations reviewed (expand-only; up+down tested)
- [ ] Promotion PR approved (2×, CODEOWNER), CI green
- [ ] Merged to `main`, tagged `vX.Y.Z`
- [ ] Production smoke tests pass; alerts watched
- [ ] Compliance-sensitive changes: go-live gates re-checked (EBM cert, tax classes)

## Feature flags
Ship incomplete/large features behind flags so they can merge to `staging`/`main`
without being active. Gate risky modules (a new EBM adapter) and enable per
environment/branch first.
