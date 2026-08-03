# Security Policy

PharmaCore handles medicine stock, money, patient data, and tax-fiscal records.
Security issues are treated with priority.

## Reporting a vulnerability
**Do not open a public issue for a security vulnerability.**

Report privately to the maintainers (security contact / private advisory). Include:
- a description and impact,
- steps to reproduce (or a proof of concept),
- affected version/commit and environment,
- any suggested remediation.

We aim to acknowledge within a few business days, agree on severity and a fix
timeline, and credit reporters (if desired) once resolved. Please give us reasonable
time to remediate before any public disclosure.

## Supported versions
During pre-1.0 development, only the latest release on `main` and the current
`staging` receive security fixes. A support matrix will be published at 1.0.

## Handling sensitive data
- **Never** commit secrets, credentials, API keys, or **real patient/PII/insurer**
  data — including in tests, fixtures, screenshots, or logs. Use synthetic data.
- Report accidental secret exposure immediately; rotate the secret; scrub history.

## Our security practices (summary)
Encryption in transit + at rest, RBAC least-privilege, immutable audit trail, secrets
in a secret manager, dependency + SAST scanning in CI, and go-live security review.
Full detail: [docs/08-security-and-compliance.md](docs/08-security-and-compliance.md).

## Scope
This policy covers the PharmaCore codebase and its deployments. Vulnerabilities in
third-party services (RRA EBM, insurers, cloud providers) should be reported to those
parties; tell us too if PharmaCore is affected.
