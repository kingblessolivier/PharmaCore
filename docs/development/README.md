# PharmaCore — Development & Process Documentation

How we build, review, test, release, and operate PharmaCore. These are the working
agreements for the engineering team.

| Doc | Covers |
|---|---|
| [Git workflow](git-workflow.md) | Branching model, **feature → staging → main**, branch protection, commits, hotfixes |
| [Coding standards](coding-standards.md) | Python/Django, TypeScript/React, ORM/migrations, API, logging |
| [Testing strategy](testing-strategy.md) | Test pyramid, coverage gates, fixtures, offline-sync & compliance tests |
| [CI/CD](ci-cd.md) | Pipeline stages, environments, deploys, rollback |
| [Release process](release-process.md) | SemVer, promoting staging→main, tagging, changelog, migrations |
| [Environments & config](environments-and-config.md) | dev/staging/prod, env vars, secrets, EBM mock/sandbox/prod |
| [Definition of Done](definition-of-done.md) | The checklist a change meets before it's "done" |
| [Onboarding](onboarding.md) | Get productive in a day |
| [ADR process](adr-process.md) | How we record architectural decisions |

## Related
- Governance (repo root): [CONTRIBUTING](../../CONTRIBUTING.md) · [CHANGELOG](../../CHANGELOG.md) · [ROADMAP](../../ROADMAP.md) · [SECURITY](../../SECURITY.md) · [CODE_OF_CONDUCT](../../CODE_OF_CONDUCT.md)
- GitHub templates: `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/`, `.github/CODEOWNERS`
- Product/technical design: [../README.md](../README.md) · Design system: [../design/README.md](../design/README.md)

## The one-paragraph summary
Branch from `staging`; small PRs with Conventional Commits; CI (lint → type-check →
test → build → migration check → security scan) must be green; ≥1 review (≥2 for
`main` and compliance-sensitive code); squash-merge to `staging`; QA on the staging
environment; maintainers promote `staging` → `main` for a tagged release that deploys
to production. Nothing reaches `main` that didn't pass through `staging`.
