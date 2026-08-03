# PharmaCore — Environments & Configuration

The environments PharmaCore runs in and how configuration/secrets flow to each.

---

## Environments
| Env | Where | Branch | EBM provider | Insurers | Data | Who uses it |
|---|---|---|---|---|---|---|
| **Local / dev** | developer machine | feature branches | **Mock** | Mock | throwaway (docker Postgres, or SQLite) | engineers |
| **Staging** | cloud (mirrors prod) | `staging` | Mock or **RRA sandbox** | Mock/sandbox | anonymized/synthetic | QA, UAT, demos |
| **Production** | cloud | `main` (tags) | **Certified OSDC/VSDC** | real | real | live pharmacies |

Principle: dev and staging **never** touch real RRA/insurer/patient data.

## Configuration model
- **12-factor:** all config comes from **environment variables** (or the secret
  manager), never hardcoded. Same image, different config per environment.
- **Business rules are data, not env:** statutory rates, insurance schemes/formularies,
  tax classes live in the **database** (versioned), not in config files (see
  [data model](../02-data-model.md)).
- **Feature flags** toggle in-progress modules per environment.

## `.env.example` (committed template — real values never committed)
```dotenv
# --- Core ---
MEDLINK_ENV=dev                      # dev | staging | production
SECRET_KEY=change-me                 # JWT signing (from secret manager in prod)
DATABASE_URL=postgresql+psycopg://medlink:medlink@localhost:5432/medlink
REDIS_URL=redis://localhost:6379/0

# --- Auth ---
JWT_ACCESS_TTL_MINUTES=30
JWT_REFRESH_TTL_DAYS=14

# --- Object storage (immutable documents) ---
STORAGE_ENDPOINT=
STORAGE_BUCKET=medlink-documents
STORAGE_ACCESS_KEY=
STORAGE_SECRET_KEY=

# --- EBM (RRA) ---
EBM_PROVIDER=mock                    # mock | osdc | vsdc
EBM_BASE_URL=
EBM_TIN=
EBM_SDC_ID=
EBM_DEVELOPER_ID=

# --- External adapters ---
SMS_PROVIDER=mock
MOMO_PROVIDER=mock
INSURER_PROVIDER=mock

# --- Ops ---
LOG_LEVEL=info
SENTRY_DSN=
```

## Secrets management
- Real secrets live in the platform **secret manager** / CI secrets — injected as env
  vars at runtime. Never in the repo, never in logs, never in the frontend bundle.
- Integration credentials (EBM developer id, insurer keys, momo keys) are also stored
  **encrypted at rest** in `ebm_configs` / integration tables via the secret manager (see
  [security](../08-security-and-compliance.md#3-data-protection)).
- Rotate on a schedule and on any suspected exposure.

## Per-environment differences that matter
- **EBM:** dev/staging use the Mock (or RRA sandbox); production uses the **certified**
  adapter — a **go-live gate**, not a config flip.
- **Data:** production enables full backups + PITR; staging uses synthetic/anonymized
  data; dev is disposable.
- **Immutable-table DB grants** are applied in every environment (behavior parity).

## Local quick start
```bash
cp .env.example .env
docker compose up -d db redis
alembic upgrade head
uvicorn app.main:app --reload
```
See [onboarding](onboarding.md) for the full path.
