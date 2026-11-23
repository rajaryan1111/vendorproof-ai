# VendorProof AI Security Architecture

**Status:** Baseline requirements for implementation; not a certification or claim of completed security review.

## Security requirements

- **SEC-001 Authentication:** protect all tenant data behind validated identity; use a maintained auth/session approach, secure password hashing if passwords are used, secure cookie attributes for cookie sessions, expiry/revocation, and rate limits on authentication endpoints.
- **SEC-002 Authorization:** deny by default; enforce role permissions server-side for every route and object operation. Initial roles are admin, operator, reviewer, auditor; define a permission matrix before implementation.
- **SEC-003 Tenant isolation:** derive tenant scope from authenticated membership, check it on every database and file access, and test cross-tenant object IDs. Client-supplied tenant IDs never grant access.
- **SEC-004 Upload safety:** allowlist formats and size/page limits; check file signatures and parser-detected type, generate storage keys, reject path-like names, protect against archive/decompression abuse, and store outside public web roots. Treat content as hostile.
- **SEC-005 Document protection:** private encrypted storage, least-privilege service credentials, authorization-checked download, and optional malware-scanning adapter before processing or availability. Scanner outage behavior must fail safely according to deployment policy.
- **SEC-006 Sensitive data:** mask bank details in ordinary responses and UI; restrict full values by role; redact logs and errors; minimize external provider sharing.
- **SEC-007 Auditability:** record consequential actor/action/time/target/reason events; ordinary application roles cannot update/delete audit history.
- **SEC-008 Input/output safety:** validate with Pydantic and database constraints; parameterized ORM queries; escape rendered content; use CSP and appropriate security headers; protect cookie-authenticated mutations against CSRF.
- **SEC-009 Operations:** keep secrets in environment/secret manager, rotate credentials, restrict database/storage network access, patch dependencies, monitor auth/upload anomalies, and maintain backup/restore and incident procedures.
- **SEC-010 API abuse and errors:** apply per-user/IP and tenant-aware rate controls where appropriate; cap request/body/time, use stable safe error responses, and never expose stack traces, tokens, SQL, or document text.

## Identity and role model

Authentication establishes user identity; tenant membership establishes organization context. Proposed permissions: administrators manage membership/configuration and all records; operators manage suppliers and upload documents; reviewers access evidence and record review outcomes; auditors read records/history. Sensitive banking fields require a specific permission in addition to a broad role. Final matrix must be encoded centrally and covered by positive and negative tests. AI-derived findings confer no approval permission.

## Threat boundaries

Assume browser requests, document filenames/content, OCR/model output, and external provider responses are untrusted. Threats include tenant IDOR, malicious PDFs/images, parser exploits, malware, prompt injection, XSS through extracted text, credential theft, accidental bank-data disclosure, abusive uploads, and deletion/audit gaps. Use defense in depth; do not trust file extensions, client validations, model assertions, or opaque IDs as authorization.

## Implementation controls

Use SQLAlchemy parameterized operations, Alembic-tracked schema changes, generated object keys, strict limits, private storage, short-lived download access, content disposition safe defaults, output escaping, CSRF protection for cookie sessions, and security headers. Avoid returning unnecessary fields. Errors expose a correlation ID and safe code; detailed diagnostics stay in restricted redacted logs. Keep credentials and local env files out of Git.

## Security verification and operations

Use the security tests listed in TEST_PLAN.md, dependency updates/scanning, secret scanning, and review of migration/storage permission changes. Before production, complete a deployment threat model, provider/data-sharing review, incident contacts and response process, backup restore exercise, access review, and retention/deletion validation. This plan does not assert that these controls are implemented or audited.
