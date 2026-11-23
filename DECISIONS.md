# Architecture Decision Records

Record decisions that materially constrain architecture, security, data handling, or product behavior. Status may be proposed until validated by implementation.

## ADR-001 — Begin with canonical documentation

- **Date:** 2026-11-24
- **Context:** Repository is empty and product scope includes sensitive documents and consequential human review.
- **Decision:** Complete Phase 0 specifications before application code.
- **Alternatives considered:** Start a UI/API skeleton immediately; defer security and data decisions.
- **Reasoning:** Shared requirements and boundaries reduce contradictory implementation and unsafe defaults.
- **Consequences:** Initial work produces documentation only; implementation waits for a later instruction after Phase 0.
- **Status:** Accepted.

## ADR-002 — Use a modular monolith for the initial system

- **Date:** 2026-11-24
- **Context:** No existing workload, deployment topology, or team scale is known.
- **Decision:** Prefer one FastAPI backend organized by domain, React client, PostgreSQL, and private storage adapter.
- **Alternatives considered:** Microservices, serverless decomposition, separate AI service from day one.
- **Reasoning:** The preferred stack is sufficient for MVP boundaries without operational overhead; split only when measured constraints justify it.
- **Consequences:** Modules need explicit interfaces and tenant-safe data access; processing can move to a worker later.
- **Status:** Proposed.

## ADR-003 — Keep consequential decisions human-owned

- **Date:** 2026-11-24
- **Context:** Extraction and comparison can be uncertain, and documents may conflict.
- **Decision:** AI may assist bounded extraction/ambiguity resolution but cannot declare fraud, approve suppliers, or authorize payment. Findings require evidence and uncertainty handling.
- **Alternatives considered:** Automated supplier risk/approval score as an MVP outcome.
- **Reasoning:** Prevents unsupported model conclusions from becoming consequential decisions and supports auditability.
- **Consequences:** Review workflow and evidence provenance are core requirements; abstention is a valid result.
- **Status:** Accepted.

## ADR-004 — PostgreSQL as the system of record; document bytes in private storage

- **Date:** 2026-11-24
- **Context:** Records need transactional integrity and uploaded documents have different size/access characteristics.
- **Decision:** Store structured metadata and workflow state in PostgreSQL; store bytes through a private storage adapter using opaque keys.
- **Alternatives considered:** Store all bytes in relational rows; make public filesystem paths authoritative.
- **Reasoning:** Separates transactional data from file lifecycle and supports private storage providers.
- **Consequences:** Metadata and object deletion/retention must be coordinated and tested; provider choice remains open.
- **Status:** Proposed.

## ADR-005 — Start extraction with PyMuPDF and Tesseract, evaluate before adding providers

- **Date:** 2026-11-24
- **Context:** Documents may be text PDFs or scans; no external credentials are assumed.
- **Decision:** Plan local PDF text extraction and Tesseract OCR, with strict schemas and deterministic validation; keep any model provider behind an optional adapter.
- **Alternatives considered:** Mandatory hosted LLM pipeline; vector database/RAG; custom model training.
- **Reasoning:** Local components provide an offline baseline; more complex model infrastructure lacks demonstrated need.
- **Consequences:** OCR quality and supported document types must be measured; provider selection and data-sharing approval are deferred.
- **Status:** Proposed.

## ADR-006 — Run two local processes for milestone 1

- **Date** 2026-11-24
- **Context** The shell needs one read-only API health call.
- **Decision** Run Uvicorn and Vite locally with configurable API address and CORS origins.
- **Alternative considered** Containerize both processes and add Compose.
- **Reasoning** Neither service currently depends on a database or another container.
- **Consequences** Developers install the two runtimes. Revisit Compose when adding PostgreSQL.
- **Status** Accepted for local development.

## ADR-007 — Membership sessions and restricted original documents

- **Date** 2026-11-24
- **Context** A workspace can contain sensitive supplier PDFs.
- **Decision** Provision identities locally, resolve membership and role on each request, and limit original file downloads to administrators.
- **Alternatives considered** Public registration, browser bearer tokens, direct file URLs.
- **Reasoning** Server-side sessions support immediate revocation and tenant-scoped download checks.
- **Consequences** Authentication requires PostgreSQL. Reviewers can inspect metadata. Raw files need administrator access until finer permissions exist.
- **Status** Accepted for Phase 1.
