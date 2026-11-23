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

## Next phase

Phase 2, document intelligence. Begin with local PDF text extraction against versioned synthetic fixtures, page-level provenance, validation and explicit failure states. Read MODEL_PLAN.md and PHASES.md before changing the processing contract.
