# VendorProof AI Data Governance Policy

**Status:** Proposed baseline; deployment-specific retention, residency, and legal obligations are not yet known.

## Classification and collection

- **Public:** product documentation and non-sensitive configuration.
- **Internal:** tenant settings, user names, workflow metadata, and audit metadata.
- **Confidential:** supplier names, registration identifiers, addresses, agreements, insurance and tax records.
- **Restricted:** bank details, identity data, document bytes, authentication credentials, and extracted sensitive fields.

Collect only fields required for supplier identity, document completeness, verification, review, and audit. Avoid collecting personal data unrelated to those purposes. Mark data source and provenance where practical.

## Storage and access

Supplier/document records are tenant-scoped. Document bytes live in private encrypted storage under opaque generated keys; metadata lives in PostgreSQL. Enforce role-based access and tenant checks on every access path. Restrict bank fields to roles with a demonstrated payment-review need, mask them in ordinary views, and avoid returning complete account identifiers except when explicitly authorized. Backups inherit the source classification and access restrictions.

## Processing and provider sharing

Local deterministic processing is preferred where adequate. Before sending document content or extracted sensitive fields to an external model/OCR provider, document the provider, purpose, data fields, retention/training settings, region, contract controls, and tenant configuration. No provider is presumed available or approved. Send the minimum necessary content, redact unrelated fields where feasible, and do not send secrets. Provider responses are untrusted and must be validated. Provider data use and retention require deployment review.

## Logging and audit

Never log document bytes, full extracted text, credentials, or complete bank identifiers. Logs may contain opaque IDs, tenant ID, safe event type, state, timing, and a bounded error code. Audit history captures who/what/when/reason for consequential actions without copying unnecessary sensitive content. Define access and retention for both logs and audit records.

## Retention and deletion

Retention duration is configurable only after customer and legal requirements are known; this document does not invent a universal period. Establish per-tenant policy for active documents, superseded versions, audit data, backups, and failed uploads. Deletion must remove or schedule removal of object bytes and metadata consistently, record the deletion event without preserving deleted content, and account for backup expiry and legal holds. Provide an auditable workflow and verify it before production use.

## Data minimization, demos, and testing

Use synthetic, clearly labeled demo data only. Never use actual customer or supplier documents in tests or examples. Keep fixtures fabricated, non-identifying, and free of realistic credentials/account numbers. Do not commit uploaded files, local databases, private documents, or secrets. Test files should be generated or synthetic and excluded from production paths.

## Phase 1 local file lifecycle

Only PDFs up to 5 MiB are accepted. Bytes are stored under tenant and document UUIDs, with owner-only file permissions. The development host supplies disk encryption. Replacement creates a new immutable object and archives the previous record in one database transaction. Archiving hides metadata and disables download. Phase 5 implements private scan attestation and configurable backup expiry. Physical retirement and orphan reconciliation require the storage owner and customer retention policy. A crash between object write and database commit can leave a private unreferenced file. Use synthetic data locally.

## Backup and incident handling

Production backups must be encrypted, access-restricted, monitored, and periodically restore-tested; define recovery targets before launch. Suspected disclosure or loss triggers the organization's incident process, provider review, access containment, evidence preservation, and applicable notification assessment. No incident-response SLA is claimed here.

## Derived page text and candidates

Processing persists full page text, OCR boxes and scores, source slices and candidate values in PostgreSQL. Treat the entire report as restricted, including its backups. Archiving a document disables API access to all attempts but retains stored results. A tenant purge must cover processing_attempts alongside document bytes, supplier metadata and backups. Evaluate only generated synthetic PDFs. Worker stderr and parser text do not enter request logs.

## Verification records

Treat stored original and normalized values, citations, policy context and review notes as confidential or restricted according to the source. Findings reference exact immutable document versions and extraction attempts. Missing-document evidence consists of the policy and frozen inventory. An absent document has no PDF snippet. Archiving an original restricts access to its historical raw values and source-span endpoint. Include all four verification tables and their backups in deployment retention and controlled purge procedures. Review reasons should describe actions taken and omit bank details or copied document text.

## Resolution records

Assignment and decision records retain workspace membership references, timestamps, reasons and state changes. Draft revisions retain subject, approved message text, author and time under their originating finding and supplier. Internal reasons and extracted values are excluded from draft generation. Reassignment transfers draft access to the current owner. Administrators retain access.

Linked corrections retain the upload request ID, actor, immutable document version and SHA-256 provenance. Archived source bytes remain private. Historical metadata and saved text follow the existing workspace retention policy. Phase 4 introduces no purge schedule. Drafts have no delivery destination or external transport.

## Deployment retention boundary

Deploy one customer retention boundary per instance when physical retirement is required. Record the agreed lifecycle and holds for originals, superseded files, OCR text, candidates, verification evidence, notes, drafts and audit events. The operator inventory reports per-tenant counts. Archived material remains retained until authorized retirement. Customer-specific selective erasure in a shared immutable database requires an approved procedure before onboarding.

Recovery bundles contain the database and its referenced byte objects. They exclude login sessions, throttling data and worker heartbeat. Restrict access to backup operators, keep decryption identities separate and expire ciphertext according to the configured retention. Copies outside the timer's destination require matching expiry and hold policies. Reconcile post-snapshot deletions and revocations on restore. See the disposal and recovery steps in [operations](deploy/OPERATIONS.md).
