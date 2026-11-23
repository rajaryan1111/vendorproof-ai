# Project continuity

Phase 1 is complete on `feat/phase-1-foundation`. Phase 0 ends at `706c550`. Milestone 1 ends at `1bd0037`. Subsequent checkpoints cover PostgreSQL (`b446d5d`), authentication (`b8bc4d2`), suppliers (`70ac314`), PDF storage (`0455d35`) and the integrated frontend (`ef41537`). Resolve the final evidence commit with `git log -1 --format=%H --grep='^test: complete Phase 1 integration and security coverage$'`.

## Delivered

React Router provides sign-in, dashboard, account identity and sign-out, a searchable paginated supplier directory, validated create/edit forms, and document operations. Counts and recent activity come from PostgreSQL. The FastAPI application retains its versioned health endpoint, safe errors and request IDs. SQLAlchemy manages request transactions and Alembic revision 001_workspace establishes the schema.

| Tables | Purpose |
|---|---|
| organizations, users, memberships | Workspace identity, Argon2id hash and user role within the organization |
| sessions, login_limits | Expiring session digest with membership reference and per-client login throttling |
| suppliers | Tenant-owned UUID, name, contact, timestamps and archived flag |
| documents | Immutable file ID, tenant and supplier, filename, size, SHA-256, creation time, archived flag and replacement reference |
| activity | Actor, tenant, supplier, action and database timestamp |

Membership is resolved for every protected request. All roles read workspace records and document metadata. Admins and operators manage active suppliers and PDF versions. Admins alone can archive suppliers and download original PDFs. Reviewers and auditors are read-only. Local provisioning requires database access. Bank fields are not extracted. Original PDFs are restricted because they may contain financial details.

## Verification

Native PostgreSQL 16 started on a private socket. Alembic upgraded a genuinely empty database. A separate regression test upgraded and downgraded a fresh schema. Compilation, Ruff lint and format passed for 13 Python files. Pytest passed five tests including API integration and live Chrome acceptance. Cross-tenant admin requests for another workspace's supplier and PDF were denied, and a revoked session cookie failed on replay. Malformed, mislabeled, path-like and oversized uploads were rejected. Chrome signed in, created, listed and edited a supplier, uploaded a synthetic PDF, and downloaded byte-identical content. The same record and bytes remained available after an API restart. Logout denied further access. ESLint, TypeScript, production build and Vitest (one connection-state test) passed. npm audit and pip-audit reported no known vulnerabilities in the checked environments.

## Operational boundaries

The local private store uses generated UUID paths and owner-only file permissions. PDF validation checks type, extension, size, signature and parseable structure. Stored means uploaded. Malware scanning, physical purge, crash orphan reconciliation, deployment encryption and backup/restore remain operational work. Local HTTP requires the explicit secure-cookie override in the example. TestClient emits a deprecation warning for its HTTPX transport. Tests use only synthetic workspaces and files.

## Phase 2 release

Branch `feat/phase-2-document-intelligence` starts at verified Phase 1 SHA `418a8a1236b8233ecf96a37383a5ad2a29233de2`. Migration 002_processing retains previous document records and creates tenant-linked processing_attempts. A local worker claims queued versions, verifies the digest, runs bounded PyMuPDF/Tesseract extraction and saves immutable fields/1 reports with local/1 implementation metadata. Its statuses, source references, failure codes and retry behavior are documented in ARCHITECTURE.md. Administrator reports and reviewer-safe metadata are accessible from supplier detail.

Full integrated release gate: 19 pytest cases passed, including real OCR, old-schema upgrade, retry and interruption recovery, schema/provenance checks, role and tenant isolation, and the Chrome workflow opening a scanned PDF extraction. Two Vitest cases passed. Production build, TypeScript, ESLint, Python compile, Ruff lint and formatting passed. Both package audits reported no known vulnerabilities. Upstream Starlette/PyMuPDF deprecations and Vite bundling notices remain. The worker runs on POSIX and requires local Tesseract language data.

Synthetic-v1: 11 PDFs, 13 pages, 3 scored scan pages. All 12 nonempty pages yielded text, both unknown documents remained unknown, and one degraded insurance scan was misclassified as unknown. CER 10.63%, WER 36%, exact positive-field matches 14/17, normalized 15/17, strict source localization 14/17. No external calls. The committed results JSON records the confusion matrix, field counts, abstention, timings and allocation measurements. The small synthetic templates and weak degraded-scan results limit generalization.

## Phase 3 release

Branch `feat/phase-3-verification-intelligence` started at verified Phase 2 commit `2d5bd78caaeb2abfb751af3e88705760f6c32b09`. Run `git log -1 --format=%H --grep='^docs: record Phase 3 acceptance and handoff$'` for the release reference.

Migration 003 adds verification_policies, verification_runs, verification_findings and verification_reviews. Per-supplier policy revisions encode tenant requirements, conditional applicability, identifier namespace and expiry window. verify/1 compares validated Phase 2 candidates, timestamps results against a UTC calendar date and preserves each immutable source version. The historical checklist and evidence remain attached to their run. Snapshots reuse IDs for identical inputs. A changed policy, document attempt, date or rule version produces a distinct run. Reviewers and admins record reasoned actions. Exact raw evidence is administrator-only and access is rechecked when opening a span.

Release gates: 65 pytest cases, including PostgreSQL migration/rollback and the full Chrome acceptance workflow; four Vitest cases; Python compile, Ruff lint/format, ESLint, TypeScript, production build and both dependency audits. The acceptance flow used real synthetic uploads, normalized and conflicting names, expired coverage, a missing agreement, and a degraded OCR page. It tested a separate reviewer's dismissal, actor attribution, outside-tenant denials, restart persistence and archived-source redaction.

Synthetic verification_v1: 41 target cases across 14 rule families. 24/24 expected review decisions and 17/17 negative decisions, 11/41 abstentions, 39/39 labeled value references localized, 52 review-required findings across all rules. No representative workload or customer accuracy baseline exists. Runs are manual, support at most 30 active PDF versions, and use configured namespaces and supported date formats. Upstream Starlette/PyMuPDF deprecations and React Router bundling notices remain.

## Exact next phase

Phase 4 — exception resolution. Begin with assignment and queue ownership for existing findings, followed by corrective-action suggestions and editable correction-request drafts under human control. Phase 3 stops with internal review and audit history.
