# VendorProof AI Roadmap

Roadmap status reflects repository evidence as of 2026-11-24. Do not mark a phase complete until its definition of done is met and MEMORY.md records evidence.

## PHASE 0 — Repository inspection and canonical documentation

- **Objective:** establish a consistent, evidence-based project contract before implementation.
- **Scope:** inspect repository/Git state; create the 12 canonical root Markdown files; cross-check requirements, architecture, security, policy, tests, and roadmap; commit and push documentation branch if access permits.
- **Dependencies:** access to the repository and its history; none at current empty repository.
- **Deliverables:** PRD, ARCHITECTURE, DESIGN, DATA_POLICY, MODEL_PLAN, TEST_PLAN, SECURITY, RULES, PHASES, DECISIONS, MEMORY, README.
- **Tests/checks:** repository state inspection, required-file check, identifier and consistency review, whitespace/diff review.
- **Acceptance:** no existing work overwritten; all 12 files exist; planned versus implemented is clear; docs agree; commit is verified; push status is reported accurately.
- **Definition of done:** all acceptance criteria met and MEMORY.md identifies next milestone. No application implementation in Phase 0.

## PHASE 1 — Application foundation

Milestones: (1) repository configuration and backend/frontend foundations; (2) PostgreSQL configuration and Alembic migrations; (3) authentication, RBAC, and tenant isolation; (4) supplier management; (5) secure document upload/storage; (6) frontend integration and persisted-data dashboard; (7) automated test and static-check gate.

- **Objective:** deliver a runnable, secure foundation with real persistence and no implied AI capability.
- **Scope:** React/TypeScript/Vite frontend; FastAPI/Pydantic/SQLAlchemy backend; PostgreSQL; migrations; auth; role/tenant enforcement; supplier CRUD; validated private upload; dashboard; basic tests.
- **Dependencies:** Phase 0 complete; selected auth and development storage decisions.
- **Deliverables:** reproducible local setup, API/UI, schema migrations, synthetic fixtures, tests and updated docs.
- **Tests:** Phase 1 gate in TEST_PLAN.md, plus lint and type checks.
- **Acceptance:** app and DB start; migrations run; auth/authorization/tenant isolation work; suppliers persist; documents securely upload and associate correctly; dashboard displays persisted records; tests pass.
- **Definition of done:** each acceptance criterion has execution evidence; security and docs reviewed; milestone committed; MEMORY.md updated.

## PHASE 2 — Document intelligence

- **Objective:** extract typed, reviewable candidate information from supported documents.
- **Scope:** PyMuPDF text extraction, Tesseract OCR for scans, versioned schemas, document classification, provenance, validation, processing state, extraction evaluation.
- **Dependencies:** Phase 1 secure document lifecycle.
- **Deliverables:** processing module, bounded worker strategy if needed, schemas, OCR pipeline, evaluation corpus/results.
- **Tests:** synthetic document processing, malformed/OCR edge cases, schema/provenance tests, field-level evaluation and regression.
- **Acceptance:** failures and uncertainty are visible; candidates link to exact document evidence; no invented values; performance/cost measured before provider choice.
- **Definition of done:** evaluation results and limitations documented, security/privacy reviewed, docs and memory updated.

## PHASE 3 — Verification intelligence

- **Objective:** surface deterministic evidence-backed discrepancies and completeness issues.
- **Scope:** normalization; configurable required-document detection; expiry validation; contradiction checks; evidence references; severity and confidence/uncertainty.
- **Dependencies:** Phase 2 provenance and validated extraction.
- **Deliverables:** versioned rules and findings UI/API with evidence navigation.
- **Tests:** labeled synthetic comparisons, per-rule precision/recall, boundary/date/normalization regressions.
- **Acceptance:** every finding identifies source/rule or says evidence is unavailable; uncertain inputs abstain; no fraud or approval conclusion.
- **Definition of done:** rules reviewed, evaluation recorded, permission/audit impact checked, docs and memory updated.

## PHASE 4 — Exception resolution

- **Objective:** let authorized people resolve findings with a clear, auditable workflow.
- **Scope:** exception queues, corrective-action suggestions, correction-request drafts, assignment, review actions, approval history, corrected-document reprocessing.
- **Dependencies:** Phase 3 findings and stable audit/identity model.
- **Deliverables:** reviewer workflows and append-only decision history.
- **Tests:** role/state transition tests, audit attribution, draft safety, end-to-end review and reprocessing.
- **Acceptance:** human makes consequential decisions; drafts are editable and never sent without explicit action; history is complete and tenant-scoped.
- **Definition of done:** workflow passes access, security, usability, and regression gates; docs and memory updated.

## PHASE 5 — Production readiness

- **Objective:** prepare an evidence-backed operational deployment.
- **Scope:** security hardening, durable background jobs, performance, observability, end-to-end coverage, deployment, backups/restore, retention/deletion validation, demo environment.
- **Dependencies:** prior phases and identified deployment/customer requirements.
- **Deliverables:** deployment and runbooks, monitoring, restore evidence, security review, reproducible demo environment.
- **Tests:** end-to-end suite, load/performance checks against stated workload, restore exercise, dependency/security scans.
- **Acceptance:** operational, privacy, security, and recovery controls are demonstrated; no unsupported production-readiness claims.
- **Definition of done:** deployment-specific owners approve their requirements; all findings are resolved or explicitly accepted; memory and docs updated.
