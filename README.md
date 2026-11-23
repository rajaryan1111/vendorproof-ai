# VendorProof AI

VendorProof AI is planned as a supplier-document verification workspace for procurement, finance, compliance, and operations teams. It aims to organize supplier documents, surface missing, expired, inconsistent, or uncertain information, and help people resolve findings using traceable evidence. AI will not decide fraud or approve suppliers.

**Project status:** Phase 0 documentation foundation. No application features are implemented yet. No customer validation, production deployment, or accuracy claims are made.

## Planned capabilities

- Tenant-scoped supplier records and secure document intake.
- Structured document extraction with evidence references and visible uncertainty.
- Deterministic checks for missing, expired, and conflicting information.
- Human review, correction drafts, and attributable decision history.

These are roadmap capabilities, not currently available software.

## Preferred technology stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, React Router; Zod and form/query libraries where useful.
- Backend: Python, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic.
- Database: PostgreSQL.
- Document processing (planned): PyMuPDF, Tesseract OCR, Pillow only if justified.
- Testing (planned): Pytest, Vitest, React Testing Library, Playwright where appropriate.
- Local infrastructure (planned): Docker Compose and GitHub Actions.

The exact implementation and dependency versions will be selected and locked in Phase 1. No external API key is assumed.

## Repository structure

The repository currently contains the canonical documentation at its root. Planned code layout will be decided in Phase 1; no source tree exists yet.

## Development prerequisites and setup

There is no runnable application yet, so no application setup command is available. Phase 1 will add reproducible prerequisites and commands for Python, Node.js, PostgreSQL/Docker, environment configuration, and migrations. Do not create real supplier data for local examples; use clearly labeled synthetic fixtures.

## Environment configuration

No environment variables are defined yet. Future configuration must be documented in an example file containing placeholders only; secrets belong in an untracked local environment file or a secret manager and must never be committed.

## Testing

No test suite or test command exists yet. The planned test strategy and Phase 1 acceptance gate are in [TEST_PLAN.md](TEST_PLAN.md).

## Roadmap

See [PHASES.md](PHASES.md) for objectives, dependencies, deliverables, checks, acceptance criteria, and definitions of done. Current phase: Phase 0. The next milestone is to finish, validate, and publish the canonical documentation foundation; Phase 1 requires a subsequent instruction.

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
