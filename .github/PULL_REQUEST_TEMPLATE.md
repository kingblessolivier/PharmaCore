<!--
PRs target `staging` (feature/fix/chore/docs). Only maintainers open `staging → main`
promotion PRs. Keep PRs small and focused. See docs/development/git-workflow.md
-->

## What & why
<!-- What does this change and why? Link the issue. -->
Closes #

## Type
- [ ] feat  - [ ] fix  - [ ] docs  - [ ] refactor  - [ ] perf  - [ ] test  - [ ] chore  - [ ] ci

## How it was tested
<!-- Commands run, cases covered. New/updated tests? -->

## Screenshots / recordings (UI changes)

## Checklist (Definition of Done)
- [ ] Conventional-commit title; small, focused diff
- [ ] Follows coding standards; lint/format/type-check pass
- [ ] Tests added/updated and green; coverage gate met
- [ ] CI green (lint, type-check, test, migrations, build, security scan)
- [ ] Docs updated + `CHANGELOG.md [Unreleased]` line added
- [ ] No secrets / hardcoded config / real PII
- [ ] UI (if any): design tokens/components, accessible, responsive, English-only copy

## Schema changes
- [ ] N/A
- [ ] Django migration included; `makemigrations --check` clean; expand-only

## Compliance impact (stock / money / documents / EBM / audit / auth)
- [ ] None
- [ ] Yes → describe below; **requires 2 reviews** + immutability/audit tests
<!-- Describe the EBM/GDP/tax/insurance/audit impact and how immutability is preserved. -->

## Reviewer notes
<!-- Anything specific you want reviewers to focus on. -->
