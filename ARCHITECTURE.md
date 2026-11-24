# VendorProof AI Architecture

**Status:** Phase 1 implements the React workspace, authenticated API, PostgreSQL schema and private local PDF store. Phase 2 adds local document extraction. Phase 3 compares supported candidates in versioned supplier snapshots. Local development runs PostgreSQL, Uvicorn and Vite. Material alternatives remain open until a working milestone validates them.

## System shape

Start as a modular monolith: React/TypeScript client, Python/FastAPI API, PostgreSQL, and a private file-storage adapter. Keep extraction and verification behind backend modules and interfaces. Add a separate worker only when measured processing/runtime needs justify it.

```mermaid
flowchart LR
  U[User browser] -->|HTTPS / JSON| API[FastAPI modular monolith]
  API --> AUTH[Authentication and authorization]
  API --> DB[(PostgreSQL)]
  API --> FS[Private object or local dev storage]
  API --> PROC[Document processing modules]
  PROC --> EXT[Optional OCR / model provider adapter]
  PROC --> DB
  API --> AUD[Audit events in PostgreSQL]
```

```mermaid
sequenceDiagram
  actor Reviewer
  participant Web as React client
  participant API as FastAPI
  participant Store as Private file store
  participant DB as PostgreSQL
  Reviewer->>Web: Upload supplier document
  Web->>API: Authenticated PDF body and filename header
  API->>API: Authorize tenant, validate size/type/signature
  API->>Store: Store under generated opaque key
  API->>DB: Persist metadata and audit event
  API-->>Web: Document ID and processing status
```

## Frontend

React, TypeScript, Vite, Tailwind CSS, and React Router are the preferred initial stack. Use Zod at client boundaries and server-side Pydantic validation as authoritative. Add TanStack Query for server state when its cache/invalidation needs justify it; use React Hook Form for nontrivial forms. The client is never an authorization boundary. Keep route areas aligned to suppliers, documents, verification/review, and administration.

## Backend and API

Use FastAPI with Pydantic request/response schemas and SQLAlchemy 2.x. Organize by domain modules (identity/access, suppliers, documents, verification/review, audit) with explicit service and persistence boundaries. Expose versioned JSON APIs under `/api/v1`; document errors with stable codes and avoid exposing stack traces or raw sensitive values. Uploads use authenticated application/pdf requests with server-enforced limits. The API derives tenant/user identity from validated authentication context, never from a trusted client-supplied tenant identifier.

## Database

PostgreSQL stores identities, membership, sessions, suppliers, PDF metadata, login limits and supplier activity. Findings and review tables are deferred. The API uses SQLAlchemy 2 connections with bound SQL and Alembic migrations; migrations are the only schema change path. Apply tenant identifiers and constraints deliberately, index common tenant-scoped lookups, and enforce tenant scope in every repository/service query. Consider PostgreSQL row-level security only as defense in depth after connection-pool/session behavior is designed and tested; it does not replace application authorization.

## File storage

Store document bytes outside ordinary web roots under opaque generated keys, with encryption at rest and private access controls in production. Development may use a private local storage adapter that is excluded from Git. Database metadata records tenant, supplier, object key, detected media type, size, digest, and lifecycle state, but not document contents. Serve downloads through an authorization-checked API or short-lived scoped URL. Storage provider is configurable behind a narrow adapter; do not introduce a cloud dependency before deployment needs are known.

## Processing and AI boundary

Document processing is a backend module with explicit states (uploaded, queued, processing, needs_review, failed, complete). Phase 2 begins with PyMuPDF text extraction and Tesseract OCR for scanned pages, with page-level provenance. Pydantic schemas validate candidate fields. Phase 3 uses deterministic normalization and rules for comparisons, missingness, and expiry. An optional provider adapter may assist only with bounded ambiguous extraction/resolution; providers are configurable and not assumed available. Every result preserves evidence and uncertainty. Model output cannot approve a supplier or label one fraudulent. See MODEL_PLAN.md.

## Background work and failure handling

Phase 1 may process small development tasks synchronously only if request limits and timeouts are safe. Phase 2 should introduce a durable queue/worker when OCR or model latency makes request-bound work unreliable; choose the simplest supported option based on operational constraints. Persist state transitions and bounded error codes, make tasks idempotent by document/version, and provide controlled retries. Never silently discard failures or put document contents in logs.

## Authentication and authorization

Phase 1 uses locally provisioned Argon2id passwords and opaque, revocable membership sessions. Role checks and tenant membership checks are server-side on every request. Initial roles: workspace administrator, operator, reviewer, and read-only auditor; exact permission matrix belongs in SECURITY.md and must be tested. Do not store secrets in source or browser storage without a threat-model decision.

## Audit and observability

Audit consequential actions (identity/role changes, supplier updates, upload/replacement/deletion, processing transitions, finding changes, review decisions) with actor, tenant, target, action, timestamp, and safe metadata. Keep audit events append-only through application permissions and disclose corrections as new events. Operational logs use correlation IDs and bounded error codes, redact sensitive fields and document text, and have defined access and retention.

## Deployment and integrations

Verified local development uses native PostgreSQL 16 and documented app commands; deployment topology is undecided. Production requires TLS, managed secret injection, private durable storage, backups, migration discipline, monitoring, and a malware-scanning integration boundary. External OCR/model, email, identity, and storage services sit behind adapters; no API key or service availability is assumed. See DATA_POLICY.md and SECURITY.md.

## Local processing contract (implemented)

Alembic 002_processing adds one table with a composite foreign key to the existing tenant, supplier and immutable document UUID. New uploads insert attempt 1 in the upload transaction. Older versions can be queued on demand. The row holds versioned structured JSON, claim/finish times and a bounded error code. All report sources inherit the report's document UUID, SHA-256, schema and engine version. A replacement PDF gets a new UUID.

The worker claims a row with FOR UPDATE SKIP LOCKED, commits the claim, runs the parser outside the database transaction and publishes once using a conditional update. Allowed transitions are uploaded → queued → processing → needs_review or failed. A worker marks processing attempts older than three minutes failed. Operators and administrators retry manually, up to ten attempts per document. Supplying the last attempt UUID as the reprocessing precondition makes duplicate requests idempotent. No automatic retries consume CPU after bad input.

Under /api/v1/suppliers/{sid}/documents/{key}/processing, GET lists attempt history and POST queues work. POST ?after={last-id} requests another attempt. GET /{attempt-id} returns administrator evidence. GET /{attempt-id}?summary=true returns a reviewer-safe field and page summary. The API checks the document tenant, supplier and archival state before accessing reports.

## Verification persistence and API

Migration 003 adds four tables. verification_policies stores tenant and supplier scope, policy version, configuration, author and timestamp. verification_runs records the actor, UTC evaluation date, rule and policy revisions, fingerprint, document inventory and checklist. verification_findings stores stable UUIDs, rule, outcome, severity, evidence quality, citation data, review requirement and timestamps. verification_reviews stores attributed append-only decisions with a database trigger preventing changes and deletion. Composite foreign keys enforce scope.

The API serializes configuration, run creation and review on the supplier row. One database query snapshots the latest processing attempt for each active document. A SHA-256 fingerprint covers the ordered input versions, digests, attempts and states, date, policy version and engine version. Identical inputs reuse the run and finding IDs. Changes produce another snapshot. The local synchronous engine accepts at most 30 active versions per supplier. Larger runs fail explicitly.

Under /api/v1/suppliers/{id}/verification: GET /policy and PUT /policy?previous=N read and revise configuration. POST /runs evaluates, GET /runs lists snapshots and GET /runs/{run} returns policy, inventory, checklist and findings. POST /findings/{finding}/review appends an event with the expected previous sequence. GET /findings/{finding}/sources/{index} resolves one authorized citation against its stored extraction. Verification does not modify supplier or extraction state.

## Exception resolution

Alembic revision `004_resolution` adds membership activity, two immutable tables for draft revisions and linked PDF versions, and an indexed assignment lookup on the existing review log. The `exception_queue` view projects one row per review-required finding. Its latest review supplies status and sequence. Its latest assignment supplies ownership. Phase 3 acknowledgements appear as in progress and clarification requests as awaiting supplier response. Original event values are preserved.

The API serializes writes with the supplier row lock. Assignment and decisions check the observed review sequence. Drafts check their own revision. Correction uploads validate the PDF, authorize the target, preserve the replacement relationship, link the finding and enqueue the ordinary processing job in the request transaction. A per-finding request UUID supports retries. Existing file storage retains its documented filesystem crash boundary.

A comparison references the new immutable run and corrected document. It follows replacement ancestry and matches the original rule and cited counterparts. Checklist comparisons also match the required category. Resolution after a linked correction checks the latest linked version, extraction state, displayed comparison, current input fingerprint and supporting result again inside the decision transaction. An empty comparison keeps the exception open for investigation.
