# Contributing to PharmaCore

Welcome. PharmaCore is a pharmaceutical ERP where correctness and compliance matter —
so we favour small, reviewed, well-tested changes over speed. This guide is the
entry point; deeper rules live in [docs/development/](docs/development/README.md).

---

## 1. Before you start
- Read the [architecture](docs/05-architecture.md) and the [data model](docs/02-data-model.md).
- Skim the [key decisions](docs/01-key-decisions.md) — offline-first, multi-insurer,
  EBM-abstracted, English-only shape most work.
- Pick or open an issue; comment that you're taking it.

## 2. Local setup
```bash
# backend
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db          # local Postgres
alembic upgrade head
uvicorn app.main:app --reload

# frontend (once it exists)
cd frontend && npm install && npm run dev
```
Full detail: [onboarding guide](docs/development/onboarding.md) and
[environments & config](docs/development/environments-and-config.md).

## 3. The workflow (short version)
1. Branch from `staging`: `feature/<scope>-<short-desc>` (see naming below).
2. Make focused commits using **Conventional Commits**.
3. Open a **PR into `staging`** — fill the PR template, keep it small.
4. CI must be green; get the required review(s).
5. Squash-merge to `staging`; it deploys to the staging environment for QA.
6. Releases promote `staging` → `main` (maintainers). See the
   **[git workflow](docs/development/git-workflow.md)** for the full rules — this is
   the authoritative doc for branching and the staging→main merge process.

## 4. Branch naming
`<type>/<scope>-<kebab-summary>` — e.g. `feature/inventory-fefo-picker`,
`fix/pos-offline-oversell`, `chore/ci-cache`, `docs/api-sync-endpoints`.
Types: `feature` · `fix` · `chore` · `docs` · `refactor` · `test` · `perf` · `hotfix`.

## 5. Commit messages — Conventional Commits
```
<type>(<scope>): <summary in imperative>

<body: what & why, not how>

<footer: Refs #123 / BREAKING CHANGE: …>
```
Scopes match modules: `iam, catalog, inventory, distribution, documents, retail,
insurance, ebm, hr, finance, reporting, sync, design, ci`.
Example: `feat(retail): add FEFO batch highlight in POS batch picker`.

## 6. Standards
- Code: [coding standards](docs/development/coding-standards.md) (Python + TS).
- Tests: every behavior change ships tests — [testing strategy](docs/development/testing-strategy.md).
- Docs: update the relevant `docs/` page and add a `CHANGELOG.md` `[Unreleased]` line.
- A change isn't finished until it meets the [Definition of Done](docs/development/definition-of-done.md).

## 7. What needs extra care (compliance-sensitive)
Changes touching **stock movements, money/journals, documents, EBM, or audit
logging** require: a second reviewer, tests for the immutability/audit behavior, and
an explicit note in the PR describing the compliance impact. Never make audit or
finalized records mutable.

## 8. Reporting bugs / requesting features
Use the issue templates (`.github/ISSUE_TEMPLATE`). Security issues: **do not** open
a public issue — follow [SECURITY.md](SECURITY.md).

## 9. Code of conduct
Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
