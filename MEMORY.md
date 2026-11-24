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

## Phase 4 release

Branch `feat/phase-4-exception-resolution` starts at verified Phase 3 release `6c652592fb59a9e089bb9602d904cbfa0533e555`. Implementation commit `924042801dbd69d60bf2831f50b9658973293684`. Resolve the release commit with `git log -1 --format=%H --grep="^docs: record Phase 4 acceptance and handoff$"`. Migration 004 projects the exception queue from immutable findings and the existing review log. It adds active membership, assignment and comparison events, draft revisions, and idempotent correction-to-document links. The queue includes older unresolved snapshots. Assigned reviewers and administrators control drafts and decisions. Approved sentences keep internal notes and original values out of supplier-facing text. Drafts remain internal.

The local API, React workspace and existing worker were exercised with synthetic PDFs and users. The Chrome workflow assigned a bank-holder discrepancy, saved two draft revisions, processed a corrected bank letter, compared cited evidence, recorded a human resolution, and verified audit and historical results after restart. A separate workspace was denied access.

Release evidence on 2026-11-24: Python compilation and Ruff lint/format passed for the checked application, migrations, tests and evaluation code. Full pytest passed 72 cases, including Chrome, migration round trip, preservation of Phase 3 review data, blocked destructive downgrade, concurrent assignment, inactive session denial, failed extraction and retry. Nine Vitest tests, ESLint, TypeScript and the Vite production build passed. pip-audit and npm audit reported zero known vulnerabilities. Upstream Starlette/PyMuPDF deprecations and React Router bundler notices remain.

Operational limits: verification runs retain the existing 30-active-document bound. Queue age uses elapsed days with a selectable threshold. A correction with no supported comparable result remains open for investigation or an explicitly justified dismissal. Downgrading a database with Phase 4 history requires an archival plan.

## Phase 5 deployment preparation

The feature branch starts at Phase 4 release `ccdf93f8b6bdbd03438bb2fe0bc128bd7ff817bc`. Application release evidence, external gates and the current checkpoint follow below.

Revision 005 records scan attestations, worker availability and processing actors. The release adds Linux service units, a same-origin TLS edge, a private ClamAV gate, a namespace-confined production parser, host probes, encrypted recovery and release CI. UI changes cover navigation, forms, responsive layout and paginated document and verification history. The release process uses the verified feature branch.

Local evidence on 2026-11-24 (macOS arm64, PostgreSQL 16, Python 3.14, Node 24):

- 78 pytest cases passed, including real Chrome at 1280 and 390 px, tablet overflow and keyboard focus at 768 px, a Caddy TLS smoke test, migration upgrade/downgrade, real ClamAV synthetic detection and outage, concurrent claims, tenant restrictions and a recovery exercise. Nine Vitest cases passed. Python compilation, Ruff lint/format, ESLint, TypeScript and the Vite production build passed. pip-audit and npm audit reported zero known vulnerabilities. The tracked-path credential signature check passed. Upstream deprecation and bundler notices persist.
- The local encrypted snapshot contained six versioned PDFs (5,357,016 ciphertext bytes). Backup took 0.097 seconds and restore took 0.082 seconds in the recorded run. The tested recovery point included the assigned, corrected and human-resolved finding before the snapshot. Restored PDFs matched SHA-256. Fresh logins recovered the supplier, extraction report, historical run, two drafts and audit, and the other workspace remained denied. Session rows were excluded from the backup. The timed exercise excludes provisioning, offsite transfer, DNS and operator response.
- One synthetic supplier, six versions and 15 local HTTP reads per operation produced median queue/directory/dashboard/exception-detail times of 2.8/2.3/2.6/3.6 ms and response sizes of 3062/266/1020/5180 bytes. Four simultaneous small uploads completed in 0.15 s. The 11-document evaluation (13 pages, three OCR pages) measured a 0.003 s median and 0.196 s maximum per document with 9,465,682 peak Python-allocated bytes. The whole evaluation process reached 97,304,576 bytes RSS. The web build emitted 110.51 kB gzipped JS and 3.04 kB gzipped CSS. These are local samples.
- The worker, queue, OCR, DB and backup probes were healthy. The local disk had about 6.4% free, and the 15% headroom check correctly flagged it. Runtime-role grants were applied in disposable PostgreSQL and verified for membership row locking, scan attestation and denial of identity/review updates.

The owner selected deployment preparation and has no approved hostname or production host. External gates include encrypted persistent volumes, live TLS, host isolation and scanner updates, an independent backup destination and offline recovery identity, production restore, alert delivery, retention policy and sign-off. Selective physical deletion in a shared immutable database requires a separate approved procedure. See [operations](deploy/OPERATIONS.md) for exact commands. Resolve the published release using the feature branch's remote SHA and check its CI run.

## Final deployment audit

Baseline and remote Phase 5 branch verified at 13e84798a4bb5f7d679bb2aa5c1982d155add570. The final deployment branch adds Vercel routing, a data-free Render parser check, organization access management (schema 006), an offline credential gate, and mount checks on scheduled backups. The encrypted Linux profile remains the customer-data implementation.

On the disposable macOS PostgreSQL instance, 80 pytest tests and 11 frontend tests passed. Compilation, Ruff checks, ESLint, TypeScript, Vite build and both package audits passed. Chrome covered the supplier workflow at 1280 and 390 pixels and the queue, resolution history and keyboard focus at 768. A fresh restore verified six PDF versions from a 5,357,016-byte encrypted archive. Local backup took 0.135 s and restore took 0.098 s. Median queue, directory, dashboard and comparison times were 2.6, 2.8, 2.4 and 3.2 ms (15 requests each). The local disk monitor flagged capacity below its 15% threshold. These measurements apply to the disposable test host.

The [Linux release gate](https://github.com/rajaryan1111/vendorproof-ai/actions/runs/45412920629) passed on application commit `1bf030d63914958327fa9295d4d50c0302eb42f3`. Vercel Hobby and Render Free served this commit over HTTPS. The Render production-parser probe returned false on that instance. A proxied database probe returned 503 with private, no-store headers, and Chrome withheld the sign-in form at the public URL. No cloud supplier transactions, recovery drill or alert delivery were performed. See [hosting evidence and release conditions](deploy/CLOUD.md).
