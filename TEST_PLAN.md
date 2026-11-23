# VendorProof AI Test Plan

**Status:** Milestone 1 tests exercise health, request IDs, allowed and denied origins, safe 404 responses, and dashboard loading, failure and retry. Later acceptance tests remain planned.

## Executable Phase 1 gate

Run the README quality commands. Pytest covers API and SQL transactions through real PostgreSQL, role/tenant denial, PDF validation and replacement, session revocation, and clean migration/rollback. Playwright drives Chrome against Vite and Uvicorn, checks required fields, creates and edits a supplier, uploads a synthetic PDF, retrieves its bytes, verifies outside-tenant denial, restarts the API and signs out. Vitest covers API connection-state recovery.

## Test layers

- **Backend unit:** domain validation, tenant-scoped services, normalization/rules, state transitions, audit event creation, and error mapping with isolated dependencies.
- **API integration:** FastAPI requests against disposable PostgreSQL/migrations; authentication, role/tenant enforcement, supplier CRUD, upload metadata, and error contracts.
- **Frontend component:** Vitest and React Testing Library for forms, status rendering, evidence links, accessibility-relevant interactions, and loading/empty/error states.
- **Frontend integration:** API-bound flows for supplier creation, upload status, verification review, and permission failures using controlled test services.
- **Security:** unauthenticated access, cross-tenant IDOR attempts, role escalation, upload spoofing/oversize/path traversal, stored XSS payloads, rate limits, and sensitive-data redaction.
- **Document processing:** synthetic PDFs/images for text/OCR, malformed inputs, empty/unreadable pages, provenance coordinates, and idempotent retries.
- **AI evaluation:** versioned synthetic set measuring field extraction, evidence localization, abstention, contradictions, prompt injection resilience, latency, and cost (see MODEL_PLAN.md).
- **Regression:** retain each fixed defect as a focused test; migrations are tested from a clean database and from the previous supported schema.
- **End-to-end:** Playwright covers authenticated tenant setup, supplier/document flow, human review, and audit visibility when those phases exist.

## Requirements mapping

| Requirement | Verification |
|---|---|
| FR-001, FR-009 | API and UI persistence tests; dashboard counts equal tenant-scoped records |
| FR-002, FR-003 | upload validation, storage authorization, metadata association, lifecycle tests |
| FR-004, FR-005 | schema/provenance tests and deterministic comparison evaluation |
| FR-006, FR-007 | permission, state transition, immutable history and attribution tests |
| FR-008, FR-011, SEC-001–SEC-006 | authentication, role, tenant boundary, and negative API tests |
| FR-010 | draft generation, evidence references, editability, and no-send-without-human-action tests |
| NFR-002, NFR-005 | provenance navigation tests and accessibility checks on core workflows |
| NFR-001, NFR-003, NFR-004, NFR-006, NFR-007 | security tests, retry/idempotency checks, maintainability review, measured performance, and retention/deletion verification |

## Phase 1 acceptance gate

- **TEST-001 Setup:** documented local setup starts the app and PostgreSQL from a clean checkout.
- **TEST-002 Migration:** Alembic upgrades a clean database and reports current revision.
- **TEST-003 Authentication:** authentication succeeds for a configured user and rejects invalid/unauthenticated requests.
- **TEST-004 Authorization:** role checks and tenant isolation are verified for allowed and denied operations, including guessed IDs.
- **TEST-005 Suppliers:** supplier records persist and are visible only within their tenant.
- **TEST-006 Upload safety:** valid uploads persist safely and associate to the correct supplier/tenant; invalid signatures, unsupported types, and oversized files are rejected without partial records or public exposure.
- **TEST-007 Dashboard:** dashboard reads persisted records and handles empty, loading, and failure states.
- **TEST-008 Quality checks:** relevant backend/frontend tests, lint, and type checks pass; exact commands and results are recorded in MEMORY.md.
- **TEST-009 Data hygiene:** no actual supplier documents or secrets are present in fixtures or repository history.
- **TEST-010 AI provenance:** each extraction candidate references source evidence or abstains; malformed and unsupported model output is rejected (AI-001, AI-004).
- **TEST-011 Deterministic verification:** versioned normalization and checks return correct match/conflict/missing/expiry states on labeled synthetic cases (AI-002).
- **TEST-012 Human authority:** model responses cannot change supplier approval/payment state and ambiguous inputs enter review (AI-003).
- **TEST-013 Evaluation:** quality, limitations, sample sizes, latency, and costs are recorded for a versioned evaluation set (AI-005).

## CI gate

GitHub Actions should install from pinned/locked project dependencies, run backend and frontend tests, lint and type checks, validate migrations, and scan dependencies/secrets using chosen maintained tools. CI must fail on errors; do not suppress failures. Select concrete commands when project configuration is introduced in Phase 1. No CI workflow exists yet.
