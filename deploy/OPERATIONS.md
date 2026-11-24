# Release and operations

This profile runs one Linux host per customer retention boundary. Caddy serves the compiled SPA and proxies the API on loopback. The API and one worker use a local PostgreSQL 16 socket and the same private object directory. A Linux user namespace isolates each PDF parser. Install these services with systemd. Container networking or a public object store is unnecessary for this topology.

See [Vercel and Render validation](CLOUD.md) for the no-cost hosting profile and its release limits.

## Before provisioning

Supply an approved Linux host with working unprivileged bubblewrap, an actual DNS hostname, inbound HTTPS (and HTTP for the ACME challenge), a firewall, host patch ownership and console access. Put PostgreSQL, its WAL, objects, temporary staging and swap on encrypted storage. Mount a private, separately recoverable backup destination at `/mnt/vendorproof-backups`. Verify mount identity and access on the actual host. Configure an independent read-only or immutable copy that a compromised application account cannot delete. Store the age private identity offline with authorized recovery operators. Agree on retention, legal holds, disk capacity, recovery objectives and incident contacts before admitting customer data.

## Install and release

The commands below target Ubuntu 24.04 with PostgreSQL 16 and system Python 3.12. Run privileged commands as a host administrator. Install approved Caddy 2.11.9 or a validated patched successor, age, uv, Node 24 and Chrome for acceptance. CI pins and checks the Linux Caddy artifact. Build from a reviewed SHA that passed the release gate. Set `VP_RELEASE` to its full Git commit and `VP_HOST` to the approved DNS name. Verify the host's ClamAV engine remains supported and receives official signature updates.

```sh
: "${VP_RELEASE:?Set the reviewed release SHA}" "${VP_HOST:?Set the approved DNS hostname}"
sudo apt-get update
sudo apt-get install -y postgresql-16 postgresql-client-16 python3.12-venv bubblewrap apparmor-profiles tesseract-ocr tesseract-ocr-eng clamav-daemon clamav-freshclam age
sudo useradd --system --home-dir /var/lib/vendorproof --shell /usr/sbin/nologin vendorproof
sudo install -d -m 0755 /opt/vendorproof/releases
sudo install -d -m 0700 -o vendorproof -g vendorproof /var/lib/vendorproof/objects
sudo install -d -m 0750 -o root -g vendorproof /etc/vendorproof
sudo -u postgres createuser vendorproof
sudo -u postgres createdb vendorproof
git clone --branch feat/final-deployment-and-product-polish https://github.com/rajaryan1111/vendorproof-ai.git vendorproof-release
cd vendorproof-release
git checkout --detach "$VP_RELEASE"
test "$(git rev-parse HEAD)" = "$VP_RELEASE"
(cd frontend && npm ci && npm run lint && npm run typecheck && npm test && npm run build)
sudo install -d "/opt/vendorproof/releases/$VP_RELEASE"
git archive HEAD | sudo tar -x -C "/opt/vendorproof/releases/$VP_RELEASE"
sudo cp -R frontend/dist "/opt/vendorproof/releases/$VP_RELEASE/frontend/dist"
(cd "/opt/vendorproof/releases/$VP_RELEASE/backend" && sudo "$(command -v uv)" sync --locked --no-dev --python /usr/bin/python3.12)
sudo install -m 0600 deploy/production.env.example /etc/vendorproof/app.env
sudo install -m 0600 deploy/backup.env.example /etc/vendorproof/backup.env
sudoedit /etc/vendorproof/app.env /etc/vendorproof/backup.env
```

Use a new release directory for each SHA. Set the exact HTTPS origin in `app.env`, a recipient public key and the approved retention days in `backup.env`. Keep development, test and production databases, storage, secrets and key custody separate. Production accepts an explicitly configured Unix database socket or certificate-verified PostgreSQL TLS. Use local peer authentication in this profile. Store any remote DB credential only in a protected secret file injected by systemd. The browser build defaults to same-origin `/api/v1`. Only a public API prefix belongs in a Vite variable.

Run `freshclam` through the distribution updater. Configure clamd to use the local socket in `VP_SCANNER_SOCKET`, mode 0660, the clamav group, official signatures, a stream limit above 5 MiB and `AlertExceedsMax yes`. Set clamd's timezone to UTC. Keep the socket private. Verify `systemctl status clamav-daemon clamav-freshclam` and actual signature currency. The production startup probe calls the scanner and starts a confined Python parser. Missing isolation, unknown scanner replies or signatures older than 72 hours block this release. On a new Ubuntu 24.04 host with AppArmor, install the signed package's policy with `sudo install -m 0644 /usr/share/apparmor/extra-profiles/bwrap-userns-restrict /etc/apparmor.d/bwrap-userns-restrict` and load it with `sudo apparmor_parser -r /etc/apparmor.d/bwrap-userns-restrict`. For hosts with an existing customized bwrap profile, have the host administrator reconcile it before activation. Preserve the global unprivileged-namespace restriction. See [Ubuntu's AppArmor documentation](https://documentation.ubuntu.com/security/security-features/privilege-restriction/apparmor/). Investigate a failed probe before starting service.

## Migration and activation

For upgrades, stop writes and the worker, take an encrypted backup using the previous release, and validate a restore in isolation. Test migration time against a representative copy. Revision 006 adds the append-only workspace access history. Revision 005 adds scan attestation, job availability, worker health and lookup indexes. Legacy PDFs start without scan attestation. Migrations use the database owner. The application role has no schema ownership.

```sh
release_dir="/opt/vendorproof/releases/$VP_RELEASE"
(cd "$release_dir/backend" && sudo -u postgres env VP_DATABASE_URL='postgresql+psycopg://postgres@localhost/vendorproof?host=/var/run/postgresql' "$release_dir/backend/.venv/bin/alembic" upgrade head)
sudo -u postgres psql -v ON_ERROR_STOP=1 -v runtime_role=vendorproof -d vendorproof -f "$release_dir/deploy/grants.sql"
sudo ln -sfn "$release_dir" /opt/vendorproof/current
sudo install -m 0644 deploy/vendorproof-*.service deploy/vendorproof-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vendorproof-api vendorproof-worker
sudo systemctl enable --now vendorproof-backup.timer vendorproof-monitor.timer
```

Provision initial members from the backend directory as the database owner using `app.provision`, the owner-only database connection above, and its interactive password prompt. Never place an initial password on the command line. Run the following operator command repeatedly until the scanned count is zero. A rejected legacy file requires investigation. Existing queues retain ordinary failure and retry history.

```sh
sudo systemd-run --wait --pipe --collect -p User=vendorproof -p SupplementaryGroups=clamav -p EnvironmentFile=/etc/vendorproof/app.env -p WorkingDirectory=/opt/vendorproof/current/backend /opt/vendorproof/current/backend/.venv/bin/python -m app.operations scan-backlog
```

Install `deploy/Caddyfile` as `/etc/caddy/Caddyfile`. In a Caddy service drop-in set `Environment=VP_SITE=<approved DNS hostname>` and `Environment=VP_STATIC_ROOT=/opt/vendorproof/current/frontend/dist`. Caddy needs read access only to the built site. Keep its ACME state persistent. Bind PostgreSQL and the API privately. Validate the proxy using the same environment, then activate it and check the public trust chain.

```sh
sudo install -m 0644 deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl edit caddy
sudo -u caddy env VP_SITE="$VP_HOST" VP_STATIC_ROOT=/opt/vendorproof/current/frontend/dist caddy validate --config /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl restart caddy
curl --fail --show-error "https://$VP_HOST/api/v1/health/db"
sudo systemctl start vendorproof-backup.service vendorproof-monitor.service
sudo systemctl status vendorproof-api vendorproof-worker vendorproof-backup.service vendorproof-monitor.service
```

Use synthetic accounts and PDFs for a hostname-specific smoke test. Verify TLS trust and cookie attributes, denial to a second workspace, scan rejection and scanner outage, OCR completion, a correction comparison, durable files after restart and a restore from the independent copy. Obtain operator sign-off before real intake. CI tests pushes and PRs. Deployment is an explicit host operation on a tested SHA. No cloud deployment credentials are required by CI.

## Health and alerting

`/api/v1/health` is API liveness. `/api/v1/health/db` checks a real database query. Neither includes infrastructure details. The private host monitor checks API connectivity, worker heartbeat (180 seconds), installed OCR language, oldest runnable job (10 minutes), processing failures (3 in 15 minutes), storage headroom (15%), scanner availability and backup freshness (26 hours). These are initial operating thresholds. Set them against the customer's workload and expectations. A worker claims one job at a time, drains on SIGTERM and marks abandoned jobs failed after three minutes. An authorized retry keeps the previous attempt and delays failed-job retries exponentially up to five minutes. Each document has a ten-attempt limit.

Read `journalctl -u vendorproof-api -u vendorproof-worker -u vendorproof-backup -u vendorproof-monitor`. Request JSON has a time, severity, templated operation, tenant UUID when authenticated, response code, duration and correlation ID. Restrict journal access. Count login 401/429 responses, upload errors, request latency and verification durations by operation in the host's log collector. Keep Uvicorn access logs disabled. Set a local journald storage cap and the approved log lifetime.

Systemd failure hooks emit a `daemon.crit` journal event tagged `vendorproof-alert`. Configure the approved collector to route `SYSLOG_IDENTIFIER=vendorproof-alert` to the on-call destination and verify receipt. Connect the host monitor's nonzero service exits, backup job failures and a separate external HTTPS availability/certificate check to the approved alert destination. The separate journal probe flags 20 login 401/429 responses within five minutes. Page on failed backup or database, stale worker, sustained backlog, storage exhaustion and sustained login failure spikes. Test delivery with the duty operator. A stopped host cannot report its own outage. This repository does not contain an alert recipient.

## Recovery

Create the public age recipient with `age-keygen -o identity.txt` **on the offline recovery system** and retrieve only the public recipient with `age-keygen -y identity.txt`. The backup timer publishes an age-encrypted bundle of a PostgreSQL exported snapshot and every immutable object referenced by that snapshot. Object hashes are checked before encryption. Plaintext staging must remain on private encrypted temporary storage with space for a DB dump and tar bundle. Only ciphertext is staged or published on the backup destination. Expired matching backups are removed after a successful new snapshot. Existing sessions and stale worker health are excluded.

Restore on a separate isolated host or volume. Install the recorded release and PostgreSQL version. Create a fresh database in a new environment, choose a **nonexistent** target object directory, mount the recovery identity read-only and set the owner's `VP_DATABASE_URL` for that empty database. Use `VP_ENVIRONMENT=testing` for an isolated recovery drill, with no public listener. Run from the release backend:

```sh
: "${VP_RESTORE_ARCHIVE:?Set the authorized encrypted snapshot path}" "${VP_RESTORE_IDENTITY:?Set the protected identity path}" "${VP_RESTORE_OBJECTS:?Set a new private object path}"
.venv/bin/python -m app.recovery restore --archive "$VP_RESTORE_ARCHIVE" --identity "$VP_RESTORE_IDENTITY" --objects "$VP_RESTORE_OBJECTS" --sha256 "${VP_ARCHIVE_SHA256:?Supply the independently recorded backup digest}"
.venv/bin/alembic current
```

Collect the snapshot name and SHA-256 from the backup journal in an independently protected inventory. Authenticate the backup publisher through this inventory and custody of the backup store. Restore validates the recorded digest, age ciphertext integrity, archive entry types and names, a single-transaction PostgreSQL restore, object count and SHA-256 values before publishing the private files. A failed validation keeps the restored database out of service. Investigate and retry in a fresh target. Restore grants separately, provision the runtime service identity and verify application access, report provenance, assignments, history and tenant denial. Reapply any post-backup deletion or revocation decisions before opening traffic. Record backup snapshot time, restore duration and operator evidence. The local drill supplies no contractual recovery target.

## Retention, incident response and rollback

Use `python -m app.operations retention-inventory TENANT_UUID` under a protected operator identity to count workspace records, including derived reports, evidence, drafts and history. This command exports counts. A full recovery bundle contains all tenants and restricted values and must never serve as a tenant export. Restrict subject exports to explicitly authorized records and recipients.

Archival immediately gates access to the archived PDF and historical raw evidence. It preserves required review and version history. Before launch, record customer-approved lifetimes for active, superseded, derived, audit and backup data, a legal-hold owner and an offboarding date. A deployment with a single retention boundary can retire the complete encrypted database, WAL, object storage, plaintext staging, replicas and expired backup copies together after holds are released. Preserve only approved minimal audit metadata in the customer's separately controlled archive. Validate that live objects, OCR text, source spans and drafts are gone, and ensure restore operators honor deletion decisions until the last snapshot expires. Early selective erasure inside a shared immutable database requires an approved migration and review. Do not host a customer requiring such erasure on this profile without that procedure.

For suspected compromise, block ingress, stop intake and workers, restrict operator access, revoke sessions, preserve redacted evidence and contact the recorded incident lead. Rotate affected credentials and keys. Isolate compromised backups and verify a clean restore before reopening. For an application rollback, stop writers and use a compatible tested release. Prefer a forward fix after new writes. When schemas or behavior are incompatible, restore the pre-upgrade snapshot and objects together into isolated infrastructure, reconcile subsequent activity, then switch traffic. A downgrade of revision 005 discards scan/heartbeat metadata and retry scheduling. The earlier protected review log prevents unsafe downgrades across Phase 4 history.
