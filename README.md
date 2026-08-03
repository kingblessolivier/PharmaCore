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

> Status: **early foundation**. The core domain (organizations, users/roles,
> products, batch inventory) is being built first because every other module
> reads from it. See the roadmap below for how the rest is sequenced.

---

## Modules (planned scope)

| # | Module | Slug | Depends on | Status |
|---|--------|------|-----------|--------|
| 1 | Identity & Access (orgs, departments, users, roles, JWT) | `iam` | — | 🚧 in progress |
| 2 | Catalog (medicine master data) | `catalog` | iam | 🚧 in progress |
| 3 | Inventory (batches, expiry, FEFO, per-department stock) | `inventory` | catalog | 🚧 in progress |
| 4 | Wholesale / B2B distribution (PO → approval → transfer → GRN) | `distribution` | inventory | ⬜ planned |
| 5 | Documents engine (PO, packing slip, delivery note, GRN, invoices) | `documents` | distribution | ⬜ planned |
| 6 | Retail POS & dispensing (manual entry, batch pick, sale states) | `retail` | inventory | ⬜ planned |
| 7 | Insurance claims (post-sale, co-pay, adjudication) | `insurance` | retail | ⬜ planned |
| 8 | RRA EBM fiscal receipts (async queue) | `ebm` | retail | ⬜ planned |
| 9 | HR / payroll (employees, attendance, salary, licenses) | `hr` | iam | ⬜ planned |
| 10 | Reporting & dashboards (EOD closeout, snapshots) | `reporting` | all | ⬜ planned |

Architecture note: modules are **vertical slices** inside one FastAPI app and one
PostgreSQL database (single source of truth). Each slice owns its models,
schemas, and routes but shares the identity/catalog/inventory core.

---

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic (migrations), Pydantic v2
- **Database:** PostgreSQL 16 (production). SQLite works for quick local boots.
- **Auth:** JWT (OAuth2 password flow), bcrypt password hashing, role-based access
- **Docs generation (later):** HTML → PDF (WeasyPrint) via background workers
- **Frontend (later):** web app; packaged for desktop (Tauri/Electron) for the POS counter

---

## Getting started

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# Git Bash:            source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env          # then edit DATABASE_URL / SECRET_KEY
alembic upgrade head          # create tables (Postgres) — or use SQLite default
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API.

To run PostgreSQL locally without installing it:

```bash
docker compose up -d db
```

### Seed a first admin + demo data

```bash
python -m app.seed
```

---

## Repository layout

```
backend/
  app/
    core/        # config, database session, security (JWT/hashing)
    models/      # SQLAlchemy ORM models (one file per domain area)
    schemas/     # Pydantic request/response models
    api/
      deps.py    # shared dependencies (current user, role guards)
      routes/    # one router per module
      router.py  # aggregates all routers
    main.py      # FastAPI app entrypoint
    seed.py      # dev seed data
  alembic/       # database migrations
  requirements.txt
  docker-compose.yml
```
