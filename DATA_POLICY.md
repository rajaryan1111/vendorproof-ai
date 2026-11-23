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

Only PDFs up to 5 MiB are accepted. Bytes are stored under tenant and document UUIDs, with owner-only file permissions. The development host supplies disk encryption. Replacement creates a new immutable object and archives the previous record in one database transaction. Archiving hides metadata and disables download. Physical purge, backup expiry, malware scanning and orphan reconciliation require deployment-specific implementation. A crash between object write and database commit can leave a private unreferenced file. Use synthetic data locally.

## Backup and incident handling

Production backups must be encrypted, access-restricted, monitored, and periodically restore-tested; define recovery targets before launch. Suspected disclosure or loss triggers the organization's incident process, provider review, access containment, evidence preservation, and applicable notification assessment. No incident-response SLA is claimed here.
