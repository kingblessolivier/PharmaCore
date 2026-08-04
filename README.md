# PharmaCore <sub>by Medlink</sub>

**PharmaCore** is a unified **Pharmaceutical ERP** for Rwanda, built by **Medlink**:
wholesale depot → retail pharmacy distribution, retail dispensing/POS, transport &
reception documents, insurance & RRA EBM tax compliance, and internal HR/payroll —
one database, one system.

> **Naming:** *Medlink* is the company; *PharmaCore* is the platform; the sub-systems
> are *PharmaCore Distribution / Retail / Insurance / Finance / People / Insights /
> Admin*. See [ADR-005](docs/01-key-decisions.md) and the
> [brand system](docs/design/02-brand-and-logo-system.md). (The repository folder is
> still named `Medlink`; that's just the directory, not the product.)

> Status: **Phase 1 complete** ✅ — Identity, Catalog, and Inventory (batch stock with
> an immutable movement ledger + FEFO) are built end-to-end (backend + UI), plus a
> pharmacy **Manage** console. Next: Phase 2 (Distribution & Documents). See the
> [ROADMAP](ROADMAP.md).

---

## Modules (planned scope)

| # | Module | Slug | Depends on | Status |
|---|--------|------|-----------|--------|
| 1 | Identity & Access (orgs, departments, users, roles, licences, JWT, audit) | `iam` | — | ✅ Phase 1 |
| 2 | Catalog (medicine master, ingredients, suppliers, barcodes) | `catalog` | iam | ✅ Phase 1 |
| 3 | Inventory (batches, expiry, FEFO, immutable movements, intake/adjust/wastage) | `inventory` | catalog | ✅ Phase 1 |
| 4 | Wholesale / B2B distribution (PO → approval → transfer → GRN) | `distribution` | inventory | ⬜ planned |
| 5 | Documents engine (PO, packing slip, delivery note, GRN, invoices) | `documents` | distribution | ⬜ planned |
| 6 | Retail POS & dispensing (manual entry, batch pick, sale states) | `retail` | inventory | ⬜ planned |
| 7 | Insurance claims (post-sale, co-pay, adjudication) | `insurance` | retail | ⬜ planned |
| 8 | RRA EBM fiscal receipts (async queue) | `ebm` | retail | ⬜ planned |
| 9 | HR / payroll (employees, attendance, salary, licenses) | `hr` | iam | ⬜ planned |
| 10 | Reporting & dashboards (EOD closeout, snapshots) | `reporting` | all | ⬜ planned |
| 11 | Collaboration, Notifications & Tools (comments, messaging, notification pipeline, calculators) | `workspace` | iam | ⬜ planned |

Architecture note: modules are **vertical slices** — one **Django app per module**
over one PostgreSQL database (single source of truth). Each app owns its models,
serializers, and views but shares the identity/catalog/inventory core.

---

## Tech stack

- **Backend:** Python 3.12, **Django 5 + Django REST Framework**, Django ORM + migrations
- **Database:** PostgreSQL 16 (production). SQLite works for quick local boots.
- **Auth:** JWT (djangorestframework-simplejwt), argon2 password hashing, role-based access
- **Docs generation (later):** HTML → PDF (WeasyPrint) via background workers
- **Frontend:** React 18 + TypeScript + Vite; packaged for desktop (Tauri) for the POS counter

See [docs/09-technology-stack.md](docs/09-technology-stack.md) for the full stack and rationale.

---

## Getting started

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# Git Bash:            source .venv/Scripts/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then edit DATABASE_URL / SECRET_KEY
python manage.py migrate      # SQLite default — or point DATABASE_URL at Postgres
python manage.py runserver
```

Open http://127.0.0.1:8000/health (API) and http://127.0.0.1:8000/api/docs/ (Swagger).

To run PostgreSQL locally without installing it:

```bash
docker compose up -d db
```

---

## Repository layout

```
backend/
  config/        # Django project: settings.py, urls.py, wsgi.py, asgi.py
  apps/
    core/        # health/root views  (+ one app per module: iam, catalog, …)
  manage.py
  tests/         # pytest (+ pytest-django)
  requirements.txt
  docker-compose.yml
frontend/        # React 18 + TypeScript + Vite (design tokens via Tailwind)
```
