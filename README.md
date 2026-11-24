# VendorProof AI

VendorProof AI is a supplier-document review workspace for procurement, finance, compliance and operations. It links deterministic findings to source documents and records the human decisions that resolve exceptions.

This branch includes workspace sign-in, private versioned PDFs, local extraction, evidence-backed verification and a human-reviewed exception queue.

## Deployment release

The prepared deployment uses Caddy, systemd, PostgreSQL, private persistent volumes, ClamAV and a separate processing worker. The [deployment checklist and recovery runbook](deploy/OPERATIONS.md) covers environment setup, migrations, grants, HTTPS, monitoring, backups, restore and rollback. Live rollout requires a customer-approved target and operational sign-off.

The [Vercel and Render checklist](deploy/CLOUD.md) covers the free personal validation deployment. Organization administrators can inspect members, change roles and suspend or reinstate access. Account creation remains an operator task.

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

## Process supplier PDFs locally

Install Tesseract 5 and the trained data for your selected language. On macOS, use `brew install tesseract`. On Debian/Ubuntu, install `tesseract-ocr` and the appropriate language package. Check `tesseract --list-langs` for `eng` or set `VP_OCR_LANGUAGE` to an installed language. PyMuPDF is included in the backend lockfile. The worker uses local CPU and requires a POSIX environment (tested on macOS).

From `backend/`, run `uv sync --locked` and `uv run alembic upgrade head`. Start a third terminal in that directory with the same database and private storage settings as the API:

```sh
uv run python -m app.intelligence.worker
```

Upload a PDF and open the supplier detail page. The worker claims queued attempts automatically. Existing Phase 1 documents show **Process PDF** until submitted. Administrators can open extraction reports when the state reaches **needs review**. Reviewers can inspect field statuses and page locations. Reprocess starts a new attempt and retains the previous result. For a single job, use `--once`. If the queue stays queued, check that the worker is running against the same database. For `ocr_unavailable` or `ocr_failed`, verify the worker's PATH and installed trained data, then reprocess.

Run `uv run python -m evaluation.v1.measure` from `backend/` to generate the evaluation metrics from synthetic documents. See [recorded results](backend/evaluation/v1/results.json) and [measurement definitions](MODEL_PLAN.md).

## Quality checks

Run `npm ci` in `frontend/` first. Create a separate disposable PostgreSQL database owned by the test role. Export `VP_TEST_DATABASE_URL` as its SQLAlchemy psycopg URL. The suite adds synthetic users and documents and runs migrations inside a generated schema. Use a test role with CREATEDB for the isolated recovery exercise. Install age/age-keygen, Caddy 2.11.9, OpenSSL, ClamAV (including clamd), Chrome and Tesseract. Linux additionally requires functional non-root bubblewrap user namespaces. Build the frontend with `npm run build` before the HTTPS test. Free loopback ports 55173, 58001, 58002 and 58443. Use `VP_ENVIRONMENT=testing` for the suite.

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

## Verify a supplier

Apply `uv run alembic upgrade head` from backend and start the existing API, React app and local processing worker. Upload and process the supplier PDFs. From **Verification workspace**, an administrator opens **Configure requirements**, enters the supplier's policy context, selects required categories and date checks, and saves a revision. Blank conditions apply to every supplier evaluated under that specific policy. An unmet condition disables the requirement. Missing context leaves it unresolved.

Choose **Run verification**. Review the dated inventory, checklist and source comparisons. Administrators can open cited spans. Reviewers can record an acknowledgement, clarification request, resolution or dismissal with a reason. Choose **Verification history** to inspect an earlier run. Changes to inputs take effect on the next run.

Run `uv run python -m evaluation.verification_v1.measure` in backend to reproduce the synthetic verification evaluation. [Reference cases](backend/evaluation/verification_v1/cases.json) and [measured results](backend/evaluation/verification_v1/results.json) include the exact targeted outcomes and denominators.

## Resolve an exception

1. Apply `uv run alembic upgrade head` in `backend/`. Start the API, frontend and document worker as described above.
2. Open **Exceptions** or choose **Open exception** from a supplier verification finding. An administrator selects the owner, enters a reason and records the assignment.
3. As the assigned reviewer, filter **Ownership** to **mine**. Inspect the finding and evidence. Edit the draft using its approved subject and sentences, inspect the preview and choose **Save draft**. Saved revisions are internal.
4. An administrator or operator chooses the document to replace (or adds supporting evidence), selects a corrected PDF and confirms the upload. Keep the existing worker running. Use **Refresh exception** to see completion or a processing failure.
5. As the owner or an administrator, choose **Rerun and compare**. Inspect the original and current outcomes and citations. Select the next state, enter the reason and confirm the decision. A failed, stale or unsupported comparison blocks resolution. Review history shows who acted, when and on which evidence.
