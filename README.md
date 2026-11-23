# VendorProof AI

VendorProof AI is planned as a supplier-document verification workspace for procurement, finance, compliance, and operations teams. It aims to organize supplier documents, surface missing, expired, inconsistent, or uncertain information, and help people resolve findings using traceable evidence. AI will not decide fraud or approve suppliers.

**Phase 1** provides workspace sign-in, a persisted dashboard, supplier search and lifecycle management, and private PDF intake with document version history.

## Run locally

Prerequisites used for verification: PostgreSQL 16, Python 3.14 with uv, Node 24 with npm, and Chrome for browser tests. Start your local PostgreSQL service and create an empty database named `vendorproof` owned by your development database role. On a local PostgreSQL installation with database creation privileges, run `createdb vendorproof`.

From the repository root, run the following in one terminal:

```sh
cd backend
uv sync --locked
cp .env.example .env
# Edit VP_DATABASE_URL for your local PostgreSQL role and connection.
uv run alembic upgrade head
uv run python -m app.provision Development admin@example.invalid admin
uv run uvicorn app.main:app --no-access-log
```

Provisioning prompts privately for a password. Each invocation creates a new user. Reuse the exact workspace name to add a user with role `admin`, `operator`, `reviewer` or `auditor`. Keep the database credentials within the backend environment. Use a dedicated private volume or directory for `VP_STORAGE_ROOT` (default: `~/.vendorproof/objects`). The example disables secure cookies for loopback HTTP development. Use HTTPS and secure cookies outside local development.

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173 and sign in with the workspace name, email and password. Use the same hostname for the API and web app so the strict same-site cookie works. Configure exact allowed origins with `VP_CORS_ORIGINS` and the browser-visible API prefix with `VITE_API_BASE_URL`. Liveness is available at `/api/v1/health` and database connectivity at `/api/v1/health/db`.

## Quality checks

Run `npm ci` in `frontend/` first. Create a separate disposable PostgreSQL database owned by the test role. Export `VP_TEST_DATABASE_URL` as its SQLAlchemy psycopg URL. The suite adds synthetic users and documents and runs migrations inside a generated schema. Local ports 55173 and 58001 must be free for the browser test.

```sh
cd backend
VP_DATABASE_URL="$VP_TEST_DATABASE_URL" uv run alembic upgrade head
uv run python -m compileall -q app migrations tests
uv run ruff check app migrations tests
uv run ruff format --check app migrations tests
uv run pytest -q
uv run pip-audit --local
```

In `frontend/`, run `npm run lint`, `npm run typecheck`, `npm run build`, `npm test`, and `npm audit`.

## Canonical project documents

- [PRD.md](PRD.md) — requirements and scope
- [ARCHITECTURE.md](ARCHITECTURE.md) — system boundaries and proposed stack
- [DESIGN.md](DESIGN.md) — product and interface direction
- [DATA_POLICY.md](DATA_POLICY.md) — data governance
- [MODEL_PLAN.md](MODEL_PLAN.md) — extraction and model controls
- [TEST_PLAN.md](TEST_PLAN.md) — verification strategy
- [SECURITY.md](SECURITY.md) — security requirements
- [RULES.md](RULES.md) — authoritative engineering rules
- [PHASES.md](PHASES.md) — phased roadmap
- [DECISIONS.md](DECISIONS.md) — architecture decision records
- [MEMORY.md](MEMORY.md) — project handoff and current state
