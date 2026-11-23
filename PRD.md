# VendorProof AI Product Requirements

**Status:** Initial product specification; requirements are proposed and unvalidated unless stated otherwise.

**Date:** 2026-11-24

## Vision and problem

VendorProof AI is a supplier-document verification workspace for procurement, finance, compliance, and operations teams. It organizes supplier records and supporting documents, surfaces missing, expired, inconsistent, or uncertain information, and gives reviewers traceable evidence for resolution. It is decision support: it does not determine fraud and never approves a supplier automatically.

Supplier onboarding commonly involves multiple documents that may disagree, be incomplete, or be difficult to read. The product aims to make review work visible, repeatable, and auditable. This is a product hypothesis; no customer validation, adoption, accuracy, or business-impact evidence is asserted.

## Users and personas

- **Procurement operator:** creates supplier records, requests documents, and tracks onboarding completeness.
- **Finance reviewer:** checks payment-related details, including bank-account holder consistency, with restricted access to sensitive fields.
- **Compliance reviewer:** examines registrations, insurance, agreements, expirations, and evidence.
- **Workspace administrator:** manages users, roles, organization settings, retention, and access.
- **Auditor/read-only reviewer:** inspects records and decision history without changing them.

Personas are initial design assumptions, not validated research findings.

## Core workflow

1. An authorized user creates or selects a supplier in their tenant.
2. A user uploads documents through a controlled interface; the system validates and stores them securely.
3. Processing extracts candidate fields with source references and uncertainty. Processing status and failures are visible.
4. Deterministic rules compare extracted values across documents and against configured requirements, producing findings with evidence.
5. A human reviews findings, requests corrections, records a decision, or leaves the case unresolved. Any generated correction message is a draft for human review.
6. The system records who did what and when, while limiting access to sensitive data.

## Functional requirements

- **FR-001 Supplier records:** authorized users can create, view, update, and search tenant-scoped supplier profiles; records have stable identifiers and timestamps.
- **FR-002 Secure document intake:** authorized users can upload supported document types with size/type validation, supplier association, storage protection, and visible processing status.
- **FR-003 Document inventory:** users can list documents, inspect permitted metadata, replace or archive them according to policy, and see processing failures.
- **FR-004 Extraction with provenance:** processing returns typed candidate values, confidence/uncertainty, and page/region or text evidence references; unavailable evidence is represented as unavailable, never fabricated.
- **FR-005 Verification findings:** deterministic checks identify configured missing documents, expired dates, and cross-document conflicts; each finding links to source evidence and rule/version.
- **FR-006 Human review:** authorized reviewers can mark findings reviewed, request correction, resolve with a reason, or escalate; supplier approval is an explicit human action outside AI conclusions.
- **FR-007 Audit history:** consequential record, document, finding, and review actions are attributable and time-stamped; normal users cannot rewrite history.
- **FR-008 Tenant isolation and roles:** all tenant-owned reads and writes enforce tenant boundaries and role permissions (see SEC requirements).
- **FR-009 Dashboard:** show persisted counts and work queues with clear empty/loading/error states; any illustrative demo data must be identified as such.
- **FR-010 Correction drafts:** prepare editable, evidence-linked correction-request drafts; sending is a separate human action and is outside initial MVP unless explicitly implemented and secured.
- **FR-011 Authentication:** users authenticate through the configured mechanism; unauthenticated access to tenant data is denied.

## Non-functional requirements

- **NFR-001 Security:** apply least privilege, tenant isolation, safe upload/storage, secret management, and secure defaults per SECURITY.md.
- **NFR-002 Traceability:** a reviewer can navigate from a finding to its rule and source document evidence.
- **NFR-003 Reliability:** processing failures are explicit and retryable without silently duplicating or losing review history.
- **NFR-004 Maintainability:** use a modular monolith and documented API/data contracts; avoid premature distributed services.
- **NFR-005 Accessibility:** target WCAG 2.2 AA for core workflows, including keyboard operation and clear status announcements; validate during implementation.
- **NFR-006 Performance:** define measurable latency targets after baseline workload and deployment are known; do not claim targets or achieved performance without measurement.
- **NFR-007 Privacy:** collect and retain only data needed for verification and audit, with tenant-scoped access and a documented deletion lifecycle.

## Delivery status

Phase 1 delivers FR-001, secure PDF intake and inventory within FR-002/003, supplier activity history, membership-based access, dashboard metrics and authentication. Extraction, findings, correction drafts and approval decisions belong to subsequent phases.

## MVP scope

Phase 1 establishes the application, PostgreSQL schema/migrations, authentication and role/tenant foundations, supplier CRUD, secure local/development document upload, a persisted-data dashboard, and automated tests. Later phases add extraction, evidence-backed deterministic verification, exception resolution, and production operations. Phase 1 must not imply AI verification exists.

## Future scope

OCR and structured extraction, document classification, configurable requirement sets, evidence-backed cross-document checks, exception queues, reviewer assignment, correction drafts, reprocessing, integrations, and production deployment. Each item is gated by its roadmap phase and security review.

## Out of scope

Automated fraud determinations; automatic supplier approval or payment authorization; legal/compliance guarantees; autonomous communication to suppliers; generalized RAG/vector search; multi-agent orchestration; and unsupported claims of accuracy, savings, or enterprise adoption.

## Acceptance criteria

Phase 1 acceptance is tracked in PHASES.md and TEST_PLAN.md. At minimum, a developer can start the app and database from documented setup, run migrations, authenticate, enforce role and tenant boundaries, persist and retrieve suppliers, securely upload and associate allowed documents, see persisted dashboard records, and run the documented tests. No phase is complete on file creation alone.

## Success measures

Initial product measures to instrument only after privacy review: supplier onboarding completion time, review backlog/age, document completeness, reviewer correction rate, extraction field accuracy against a consented and appropriately governed evaluation set, and processing latency/cost. Baselines, targets, and collection consent are not yet established.

## Assumptions and risks

- **Assumption:** one deployment may serve multiple organizations; tenant isolation is therefore foundational.
- **Assumption:** initial supported uploads can be limited to PDF and common image formats; exact limits and jurisdictional needs require implementation decisions.
- **Assumption:** a human is accountable for consequential review and approval.
- **Risk:** OCR/extraction errors may appear authoritative; provenance, uncertainty, and review gates are mandatory.
- **Risk:** bank and identity information is sensitive; access, logs, retention, and provider boundaries need careful design.
- **Risk:** malware, malformed files, and parser vulnerabilities; uploads are untrusted and need defense in depth.
- **Risk:** customer requirements and applicable privacy rules are unknown; retention and legal obligations require deployment-specific review.
- **Risk:** no validated customer research or production workload is available in this repository.

## Phase 2 delivery

FR-004 now delivers local extraction reports for supported English labels in registration, tax, banking, insurance and agreement PDFs. Unknown documents retain reviewable page evidence. Each report is attached to one immutable version. Human reviewers retain authority. Phase 3 adds reproducible cross-document findings (FR-005), reasoned review actions (FR-006), and attributed history (FR-007). Expiry checks require an applicable policy. Missing means an unmet requirement in the recorded inventory, and unresolved classifications are reported separately.
