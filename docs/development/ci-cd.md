# PharmaCore — CI/CD

How code goes from a PR to production, safely. The pipeline mirrors the
[git workflow](git-workflow.md): PRs are gated, `staging` deploys automatically,
`main` deploys on a tagged release.

---

## 1. Continuous Integration (every PR & push)
Runs on each PR to `staging`/`main` and each push to a PR branch. **All jobs must
pass** — they are the required status checks in branch protection.

| Stage | Job | Fails the build when |
|---|---|---|
| 1 | **lint** | ruff / ESLint violations |
| 2 | **format check** | black / Prettier diffs |
| 3 | **type-check** | mypy / tsc errors |
| 4 | **test** | any unit/integration test fails or coverage drops below gate |
| 5 | **migrations** | Alembic `upgrade`+`downgrade` fails on scratch DB |
| 6 | **build** | backend image / frontend bundle fails to build |
| 7 | **security-scan** | dependency audit or SAST finds a known-critical issue |

Also on PRs: an optional **preview deploy** (ephemeral) for reviewers; the PR must be
**up to date** with base before merge.

## 2. Continuous Delivery / Deployment
```
PR → (CI green + reviews) → squash-merge to staging
      └─► auto-deploy to STAGING  ─► smoke tests ─► QA/UAT
                                        │
              maintainers: promotion PR staging → main
                                        │
              merge + tag vX.Y.Z ─► auto-deploy to PRODUCTION ─► smoke tests
```
- **Staging deploy:** automatic on merge to `staging`. Runs DB migrations, then smoke
  tests (health, login, a sample sale against MockEbm). Rollback on smoke failure.
- **Production deploy:** triggered by a **git tag `vX.Y.Z`** on `main` (release).
  Runs migrations (expand-only; see below), health/smoke checks, then shifts traffic.

## 3. Migration safety in deploys
- Migrations run **before** the new app version serves traffic.
- **Expand → migrate → contract:** additive schema first (safe with old code),
  backfill, then remove old columns in a *later* release — never break the running version.
- Immutable-table grants (deny UPDATE/DELETE to app role) are part of migrations.
- A failed migration aborts the deploy and rolls back.

## 4. Environments
| Env | Branch | EBM | Data | Purpose |
|---|---|---|---|---|
| **dev** (local) | feature branches | Mock | throwaway | build & unit/integration tests |
| **staging** | `staging` | Mock/Sandbox | anonymized/synthetic | QA, UAT, e2e |
| **production** | `main` (tags) | Certified OSDC/VSDC | real | live |
Config & secrets per environment: [environments & config](environments-and-config.md).

## 5. Secrets & config
- Secrets come from the platform secret manager / CI secrets — **never** in the repo.
- Each env has its own credentials (DB, EBM, insurer, SMS, momo, object storage).
- CI has least-privilege deploy credentials scoped per environment.

## 6. Rollback
- **App:** redeploy the previous image tag (kept for N releases) or shift traffic back.
- **DB:** because migrations are expand-only, the previous app version is compatible;
  destructive changes are deferred to a later release, so rollback rarely needs a
  down-migration. PITR backup is the last resort.
- Every production deploy is a tagged, reproducible artifact.

## 7. Observability tied to CI/CD
- Deploys annotate dashboards; alerts on error-rate, EBM failure rate, sync backlog,
  drawer variance.
- Smoke-test failures page the on-call and auto-rollback staging.

## 8. Artifacts & caching
- Docker images tagged by commit SHA and release version, pushed to the registry.
- CI caches deps (pip/npm) and layers for speed.
- SBOM generated on release for supply-chain traceability.

## 9. Pipeline location
Defined as code under `.github/workflows/` (or the chosen CI). This doc is the intent;
the workflow files are the implementation and are reviewed like any other code.
