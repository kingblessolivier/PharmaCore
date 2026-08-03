# PharmaCore — Backend

FastAPI backend for PharmaCore (by Medlink). Phase 0 walking skeleton: config,
DB session, and a health endpoint, with the toolchain and CI wired.

## Quick start
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash  (or .venv\Scripts\Activate.ps1)
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
```
SQLite is the default so the app boots with no external services. For Postgres:
```bash
docker compose up -d db redis
# set DATABASE_URL=postgresql+psycopg://pharmacore:pharmacore@localhost:5432/pharmacore in .env
```

## Checks (same as CI)
```bash
ruff check .
black --check .
mypy app
pytest
```

## Migrations (Alembic)
```bash
alembic revision --autogenerate -m "create <thing>"
alembic upgrade head
alembic downgrade -1
```
Models arrive in Phase 1 (see ../ROADMAP.md); the skeleton has none yet.

## Layout
```
app/
  core/    config.py, database.py
  api/routes/   health.py  (+ module routers added per phase)
  main.py
alembic/   migration environment
tests/     pytest
```
See ../docs/development/ for standards, testing, and CI.
