# PharmaCore — Backend

Django + Django REST Framework backend for PharmaCore (by Medlink). Phase 0 walking
skeleton: project settings, a health endpoint, and the toolchain + CI wired.

## Quick start
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash  (or .venv\Scripts\Activate.ps1)
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate           # SQLite by default — no services needed
python manage.py runserver         # http://127.0.0.1:8000/health
```
API docs (Swagger UI): http://127.0.0.1:8000/api/docs/ · schema: `/api/schema/`.

For Postgres:
```bash
docker compose up -d db redis
# set DATABASE_URL=postgres://pharmacore:pharmacore@localhost:5432/pharmacore in .env
```

## Checks (same as CI)
```bash
ruff check .
black --check .
mypy config apps
python manage.py makemigrations --check --dry-run   # schema in sync
pytest
```

## Migrations (Django)
```bash
python manage.py makemigrations
python manage.py migrate
```
Models arrive in Phase 1 (see ../ROADMAP.md); the skeleton has none yet.

## Layout
```
config/        Django project — settings.py, urls.py, wsgi.py, asgi.py
apps/
  core/        health/root views  (+ module apps added per phase: iam, catalog, …)
manage.py
tests/         pytest (+ pytest-django)
```
See ../docs/development/ for standards, testing, and CI.
