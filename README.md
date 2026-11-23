# VendorProof AI

VendorProof AI is planned as a supplier-document verification workspace for procurement, finance, compliance, and operations teams. It aims to organize supplier documents, surface missing, expired, inconsistent, or uncertain information, and help people resolve findings using traceable evidence. AI will not decide fraud or approve suppliers.

**Project status** — Phase 1 milestone 1 is complete. The workspace overview checks the running API. Supplier and document workflows are planned for later milestones.

## Run locally

From the repository root, open two terminals. The verified environment used Python 3.14, uv 0.12, Node 24.10 and npm 11. Install dependencies from the committed lockfiles.

```sh
cd backend
uv sync --locked
uv run uvicorn app.main:app --no-access-log
```

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173 and check the connection indicator. The browser calls http://localhost:8000/api/v1/health. The API returns `{"status":"ok"}` when running. This check measures process availability.

Defaults work without environment files. To override them, copy the relevant service's `.env.example` to `.env` in the same directory. Set `VP_CORS_ORIGINS` to a JSON list of exact frontend origins. Set `VITE_API_BASE_URL` to the API address including its version prefix. Vite embeds this public value at build time. Restart the development servers after changes. The optional `VP_DATABASE_URL` setting only validates a PostgreSQL URL. Local development requires just the API and Vite processes.

## Quality checks

In `backend/` run:

```sh
uv run python -m compileall -q app tests
uv run ruff check app tests
uv run ruff format --check app tests
uv run pytest -q
```

In `frontend/` run:

```sh
npm run lint
npm run typecheck
npm run build
npm test
```

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
