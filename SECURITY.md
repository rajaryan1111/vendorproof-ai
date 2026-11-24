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

## Phase 1 permissions and sessions

All four roles can read their own dashboard, directory and document metadata. Administrators and operators can create/edit active suppliers and upload, replace or archive documents. Only administrators can archive suppliers and download raw documents because a PDF may contain bank information. Reviewer and auditor access is read-only. Provisioning requires local operator database access.

Passwords use Argon2id. An eight-hour HttpOnly SameSite=Strict cookie holds a random opaque value. PostgreSQL stores its SHA-256 digest and the membership ID. Logout deletes the session. Mutations require a custom header and check any supplied Origin against the CORS allowlist. Login limits are 60 attempts per client address per five minutes. Configure trusted proxy handling before deployment.

## Threat boundaries

Assume browser requests, document filenames/content, OCR/model output, and external provider responses are untrusted. Threats include tenant IDOR, malicious PDFs/images, parser exploits, malware, prompt injection, XSS through extracted text, credential theft, accidental bank-data disclosure, abusive uploads, and deletion/audit gaps. Use defense in depth; do not trust file extensions, client validations, model assertions, or opaque IDs as authorization.

## Implementation controls

Use SQLAlchemy parameterized operations, Alembic-tracked schema changes, generated object keys, strict limits, private storage, short-lived download access, content disposition safe defaults, output escaping, CSRF protection for cookie sessions, and security headers. Avoid returning unnecessary fields. Errors expose a correlation ID and safe code; detailed diagnostics stay in restricted redacted logs. Keep credentials and local env files out of Git.

## Security verification and operations

Use the security tests listed in TEST_PLAN.md, dependency updates/scanning, secret scanning, and review of migration/storage permission changes. Before production, complete a deployment threat model, provider/data-sharing review, incident contacts and response process, backup restore exercise, access review, and retention/deletion validation. This plan does not assert that these controls are implemented or audited.

## Phase 2 processing boundary

Only administrator report responses contain raw text, OCR output and candidate values. Reviewer summaries allowlist schema keys, validation states, page numbers and engine-generated warnings. Other members can see attempt status, category and counts. Store derived reports with the same restricted classification as PDF originals. Render evidence as React text.

The worker reads generated private paths, verifies SHA-256 and starts a separate parser process with an environment allowlist. Limits include 40 pages, 200,000 extracted characters, a 2,200-pixel longest rendered edge, 15 seconds per OCR call, and 100 seconds per job. Linux also sets a 1 GiB address-space ceiling. The parser process shares the worker's OS user permissions. Production deployment requires stronger isolation, storage encryption and malware controls. Phase 5 requires a local ClamAV daemon for production intake and scans older documents before allowing production processing or download. Extraction remains offline.

## Verification permissions

Admins configure policies. Admins, operators and reviewers run comparisons. All four roles may read same-tenant finding metadata. Only administrators can inspect source values for current, accessible documents. Non-admin representations omit original and normalized values. Exact-span lookup checks the finding, tenant, supplier, document, digest, attempt and archival flag. The engine has no account-number field. The comparison API masks long numeric and IBAN-like text as an additional safeguard. This pattern check is not a general sensitive-data classifier.

Admins and reviewers can acknowledge, request clarification, resolve or dismiss a current review-required finding with a reason. Conflicting sequence numbers, terminal decisions and attempts to review old runs are rejected. The API exposes note text only to administrators and reviewers. The review table rejects direct UPDATE and DELETE. Request logs contain safe status metadata. No review action authorizes payments, approves suppliers or communicates externally.

## Exception access boundaries

The API resolves active workspace membership on login and on subsequent authenticated requests. All workspace roles can inspect the scoped queue and cited version metadata. Administrators control assignment to active administrators or reviewers. Administrators and the assigned reviewer can edit or inspect saved drafts, compare evidence and record decisions. Operators retain the existing corrected-PDF upload permission. Source excerpts still require an administrator and a currently accessible document version.

Supplier locking and revision checks reject competing changes. Composite foreign keys constrain linked documents, runs, findings and assignees to their intended scope. PostgreSQL triggers reject updates and deletes to findings, runs, review events, drafts and linked corrections. The legacy review endpoint rejects workflow-managed findings. Archiving a supplier freezes exception mutations. Information already viewed is subject to the same client-session limitations as other document data.

## Release threat model and deployment acceptance

Untrusted bytes must pass the ClamAV socket gate, signature, parse, encryption, page and size checks. The scanner uses an official signature database maintained on the host. Its version date must be current within 72 hours. Missing, stale or unavailable scanner results fail closed. An accepted scan binds to the SHA-256 digest. Downloads verify bytes against that digest, check authorization and use attachment headers. Production workers require scan attestation. Review inherited pre-Phase-5 reports as historical data.

The API service has write access to private objects. The worker's systemd filesystem view is read-only outside its private temporary space. Each production parser runs under bubblewrap with user, mount and network isolation, a minimal environment and bounded CPU, memory and wall time. The host kernel, service account, scanner, DB owner and backup operators remain trusted boundaries. Treat namespace, disk encryption, patching, alert delivery, backup custody and restore-from-offsite as host-specific acceptance checks.

Caddy enforces body limits, same-origin CSP, HSTS, anti-framing and no-referrer headers. Production cookies require HTTPS. Logs identify templated routes, durations and outcomes. The database runtime role cannot update historic reviews or identities. The dependency and credential scans are release checks with finite coverage.
