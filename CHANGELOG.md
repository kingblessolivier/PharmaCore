# Changelog

All notable changes to PharmaCore are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Sections used: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

<!--
Maintenance rules:
- Every PR that changes behavior adds a line under [Unreleased].
- On release, move [Unreleased] items into a new versioned section with the date,
  and reset [Unreleased] to empty section headers. (See docs/development/release-process.md)
- Write entries for humans: what changed and why it matters, not the commit hash.
-->

## [Unreleased]

### Added
- Full system analysis & design documentation set (`docs/`): research findings,
  key decisions (ADRs), data model, SRS, use cases, architecture, workflows/state
  machines, API design, security & compliance.
- Design system documentation (`docs/design/`): principles, tokens, brand & logo
  system, iconography, navigation, single-page workflow, components, overlays,
  document design & authenticity, dashboards & charts (validated colour-blind-safe
  palette), motion, UX writing & terminology. Two visual references (app shell,
  dashboard).
- Development process docs (`docs/development/`, root governance files, `.github/`
  templates): git workflow, coding standards, testing strategy, CI/CD, release
  process, environments, definition of done, onboarding, ADR process; ROADMAP,
  CONTRIBUTING, SECURITY, CODE_OF_CONDUCT.

### Changed
- UI scope set to **English only** (ADR-004); removed the bilingual/Kinyarwanda plan.

### Notes
- No application code yet — the project is in the design/documentation phase by
  decision. The first code lands in Phase 0 (see [ROADMAP](ROADMAP.md)).

---

## [0.0.0] — 2026-08-03
### Added
- Project inception: repository and documentation foundation for PharmaCore, a unified
  pharmaceutical ERP for Rwanda (wholesale distribution + retail POS + compliance +
  HR/finance).

[Unreleased]: https://example.com/pharmacore/compare/v0.0.0...HEAD
[0.0.0]: https://example.com/pharmacore/releases/tag/v0.0.0
