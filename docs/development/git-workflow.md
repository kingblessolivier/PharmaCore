# PharmaCore — Git Workflow

The authoritative rules for branching, reviews, and the **promotion from staging to
main**. Designed for safety (this system moves medicine and money) while staying
simple for a small team.

---

## 1. Branch model

Two long-lived, protected branches + short-lived working branches.

```
feature/*  fix/*  chore/*        (short-lived, off staging)
      │
      ▼   PR + review + green CI (squash)
   ┌────────────┐  deploy →  Staging environment  (QA / UAT)
   │  staging   │
   └────────────┘
      │   promotion PR (release) + green CI + maintainer approval
      ▼
   ┌────────────┐  deploy →  Production
   │    main    │  ← tagged release (vX.Y.Z)
   └────────────┘
      ▲
   hotfix/*  (off main for emergencies, then back-merged to staging)
```

| Branch | Purpose | Deploys to | Protected |
|---|---|---|---|
| **`main`** | Production-ready, released code | Production (on tag) | ✅ strict |
| **`staging`** | Integration + QA of merged work | Staging | ✅ |
| **`feature/*` etc.** | One unit of work | Preview (optional) | — |
| **`hotfix/*`** | Urgent production fix | — | — |

**Golden rule: nothing lands on `main` that didn't pass through `staging`.**
`main` is only ever updated by promoting `staging` (or a hotfix, which is immediately
back-merged to `staging`).

---

## 2. The normal flow (feature → staging → main)

1. **Sync & branch** from `staging`:
   ```bash
   git checkout staging && git pull
   git checkout -b feature/inventory-fefo-picker
   ```
2. **Work in small commits** using [Conventional Commits](#5-commit-convention).
3. **Open a PR into `staging`.** Fill the PR template; keep it focused (<~400 lines
   diff where possible). Draft PRs are welcome for early feedback.
4. **CI must pass** (lint → type-check → test → build → migration check → security
   scan) and **required reviews** must approve (see §4).
5. **Squash-merge into `staging`.** The squash commit message follows Conventional
   Commits (it becomes the changelog source). Delete the branch.
6. **QA on the staging environment.** Staging auto-deploys on merge.
7. **Release:** a maintainer opens a **promotion PR `staging → main`** (or fast-forwards),
   CI green, then merges and **tags `vX.Y.Z`** → production deploy. See
   [release process](release-process.md).

---

## 3. Branch protection rules (configured on the remote)

### `main` (strictest)
- ❌ No direct pushes; changes only via PR from `staging` (or `hotfix/*`).
- ✅ Require **2 approving reviews**, including a **CODEOWNER**.
- ✅ Require **all CI checks green** and branch **up to date** with base.
- ✅ Require **linear history**; **no force-push**, **no deletion**.
- ✅ Require conversations resolved; require signed commits (recommended).
- ✅ Include administrators (rules apply to everyone).

### `staging`
- ❌ No direct pushes; changes via PR.
- ✅ Require **1 approving review** (2 for compliance-sensitive code — see §6).
- ✅ Require **all CI checks green** and branch up to date.
- ✅ No force-push, no deletion.

> These are enforced in the repo settings / branch protection or rulesets; this doc
> is the source of intent. CI status checks required: `lint`, `type-check`, `test`,
> `build`, `migrations`, `security-scan`.

---

## 4. Reviews
- **Every PR needs review** — no self-merges to protected branches.
- `staging`: ≥1 reviewer. `main` promotion: ≥2, incl. a CODEOWNER.
- Reviewers check: correctness, tests, security/compliance impact, docs & changelog
  updated, adherence to [coding standards](coding-standards.md).
- Authors respond to every comment; resolve before merge.

## 5. Commit convention (Conventional Commits)
```
<type>(<scope>): <imperative summary>
```
- **Types:** `feat` `fix` `docs` `style` `refactor` `perf` `test` `build` `ci` `chore` `revert`.
- **Scopes (modules):** `iam catalog inventory distribution documents retail insurance ebm hr finance reporting sync design ci`.
- **Breaking change:** add `!` (`feat(api)!: …`) or a `BREAKING CHANGE:` footer.
- Examples:
  - `feat(retail): highlight FEFO batch in POS picker`
  - `fix(sync): make oversell reconciliation idempotent`
  - `refactor(ebm)!: change EbmProvider.sign_sale signature`
- Squash-merge titles must also follow this — they drive the [CHANGELOG](../../CHANGELOG.md) and version bumps.

## 6. Compliance-sensitive changes (extra gate)
Any change touching **stock movements, journals/money, generated documents, EBM,
audit logging, or auth/RBAC**:
- requires **2 reviews on staging** (not 1),
- must include tests proving **immutability/audit** behavior is preserved,
- must describe the compliance impact in the PR template's compliance section.
Never make finalized/audit records editable or deletable.

## 7. Hotfixes (production emergencies)
```bash
git checkout main && git pull
git checkout -b hotfix/ebm-retry-crash
# fix + test
```
- PR **into `main`** (2 reviews, green CI), merge, **tag a patch release** (`vX.Y.(Z+1)`).
- **Immediately back-merge `main` → `staging`** so the fix isn't lost:
  ```bash
  git checkout staging && git pull && git merge --no-ff main && git push
  ```

## 8. Keeping branches current
- Rebase feature branches on `staging` (`git pull --rebase origin staging`) to keep
  history linear; resolve conflicts locally.
- Long-running branches are risky — split work and merge often.

## 9. Merge strategy summary
| Merge | Strategy | Result |
|---|---|---|
| feature → staging | **Squash** | one clean, conventional commit per unit of work |
| staging → main | **Merge commit / fast-forward** (promotion) | preserves the release set; tagged |
| hotfix → main | Squash or merge | patch release |
| main → staging (back-merge) | Merge | keeps branches in sync |

## 10. Tags & versions
Releases are tagged `vX.Y.Z` on `main` (SemVer). See [release process](release-process.md)
and [versioning](release-process.md#versioning-semver).

---
### Quick reference
```bash
# start work
git checkout staging && git pull && git checkout -b feature/<scope>-<desc>
# ... commit using conventional commits ...
git push -u origin HEAD          # open PR into staging
# after approvals + green CI: squash-merge via the PR UI
# release (maintainers): promotion PR staging -> main, then tag vX.Y.Z
```
