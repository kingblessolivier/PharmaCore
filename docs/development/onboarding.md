# PharmaCore — Engineer Onboarding

Get productive in a day. Follow in order.

---

## 1. Understand what we're building (½ day of reading)
1. [Root README](../../README.md) — the elevator pitch + module map.
2. [Research findings](../00-research-findings.md) — how real systems + Rwanda rules work.
3. [Key decisions](../01-key-decisions.md) — offline-first, multi-insurer, EBM-abstracted, English-only. **These shape everything.**
4. [Architecture](../05-architecture.md) + [data model](../02-data-model.md).
5. Skim [workflows/state machines](../06-workflows-state-machines.md) and [API design](../07-api-design.md).
6. If you'll touch UI: the [design system](../design/README.md) (start with principles + tokens).

## 2. Set up your machine
Prereqs: Python 3.12, Node ≥ 20, Docker, Git.
```bash
git clone <repo> medlink && cd medlink

# backend
cd backend
python -m venv .venv && source .venv/Scripts/activate    # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db redis
alembic upgrade head
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs

# seed demo data
python -m app.seed

# frontend (once it exists)
cd ../frontend && npm install && npm run dev
```
Config detail: [environments & config](environments-and-config.md).

## 3. Learn the workflow
- [Git workflow](git-workflow.md): branch from `staging`, small PRs, Conventional
  Commits, squash to `staging`, promote to `main`.
- [Coding standards](coding-standards.md) and [testing strategy](testing-strategy.md).
- [Definition of Done](definition-of-done.md) — bookmark it; it's the PR self-check.

## 4. Your first change (recommended starter)
- Pick a `good first issue`.
- Branch: `git checkout staging && git pull && git checkout -b feature/<scope>-<desc>`.
- Write code + tests; run `pre-commit`, lint, and the test suite locally.
- Open a PR into `staging`, fill the template, get review, squash-merge.
- Watch it deploy to staging and verify.

## 5. Key conventions to remember
- **Immutability & audit:** never edit/delete finalized documents, posted journals,
  audit rows, or snapshots. Every state change writes `audit_log`.
- **Externalize:** no hardcoded secrets, config, colours, or UI strings.
- **Adapters:** all external systems (EBM/insurer/SMS/momo) behind mockable interfaces.
- **Money is `Numeric(14,2)`; IDs are UUIDs; business rules (rates/schemes/tax) are data.**

## 6. Who/what to ask
- Architecture questions → `docs/` first, then the tech lead.
- "Where does X live?" → module packages under `backend/app/<module>/`.
- Decisions → the [ADR log](../01-key-decisions.md) and [ADR process](adr-process.md).
- Broken CI / flaky test → post in the team channel with the failing job link.

## 7. Security & conduct
- Never commit secrets or real PII. Report vulns per [SECURITY.md](../../SECURITY.md).
- Be excellent to each other: [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md).
