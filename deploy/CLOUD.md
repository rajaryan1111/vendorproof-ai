# Personal validation on Vercel and Render

The free deployment serves the actual frontend and measures parser isolation in a non-root Render container. The Render entry point has no database connection, storage credentials, scanner bypass or workspace routes. It rejects sign-in, uploads, downloads and all other workspace operations. Use synthetic local acceptance to exercise those workflows until a suitable host is available.

| Control | Free validation | Requirement for customer intake |
|---|---|---|
| Origin and sessions | Vercel serves the Vite bundle and proxies API paths over HTTPS. The browser always uses its own origin in production builds. | Set one exact frontend origin in the API. Test host-only Secure, HttpOnly, SameSite=Strict cookies, CSRF rejection, source-IP throttling and no-store responses through the real proxy. |
| Private objects | No document bytes are accepted. Render Free has ephemeral filesystems. Even paid disks attach to one instance. | Run the existing API and worker on one approved Linux host with the same encrypted private volume, or qualify a shared encrypted store and matching restore implementation before splitting them. |
| ClamAV and parser | The check launches the same bubblewrap command and PyMuPDF/Tesseract import probe at startup. A failed probe is reported as false. | The Linux API validates PDFs in a namespace during upload, so moving just the worker leaves intake unprotected. Both processes require successful preflight, official fresh signatures and actual isolation on their host. |
| Worker and PostgreSQL | Free Render compute has no background worker type. A free database expires after 30 days and lacks managed backups. No database or worker is provisioned. | Use the documented Linux worker and private PostgreSQL, or use paid Render PostgreSQL with a verified TLS endpoint, runtime grants, bounded connection pools, owner migrations, and restricted inbound access. |
| Backups and alerts | No customer records or recovery destination on the validation service. | Mount an independent encrypted backup destination, keep the age identity offline, test a restore and verify an alert with an operator. |
| Secrets and logs | No secrets are needed in either validation service. Request access logs are disabled in the check. | Populate provider secret facilities for the relevant service only, restrict platform logs and validate redaction on the actual ingress. |

## Verified personal deployment

On November 24, 2026, Render and Vercel deployed application commit `1bf030d63914958327fa9295d4d50c0302eb42f3` on free plans. The [frontend](https://vendorproof-ai-frontend.vercel.app) and [Render diagnostic](https://vendorproof-runtime-check.onrender.com/api/v1/health) use provider-issued HTTPS. Vercel forwarded the diagnostic response with `parser_probe_passed: false`. The database check through the frontend returned 503 with private, no-store caching. Direct Render sign-in also returned 503. No private database, worker or PDF storage was created on these services. Chrome verified the offline view and connection retry. Workflow and restore evidence in MEMORY.md comes from the disposable local environment.

## Deploy the personal validation release

1. In Render, create a Blueprint from the GitHub repository. Choose branch `feat/final-deployment-and-product-polish` and `render.yaml`. Review the single **Free** web service. Select the free workspace and deploy the reviewed SHA. No database, disk, backups or other paid resources are in this Blueprint. Alternatively use its identical Docker web-service settings in the dashboard.
2. From Render’s actual service URL, set the shell variable `VP_API_ORIGIN` to its bare HTTPS origin. Inspect the response and record the parser result. HTTP 200 here indicates the diagnostic process is available. Workspace readiness must return 503.
3. Import the same GitHub branch into Vercel. Select the `frontend` root, Vite, Node 24, `npm ci`, `npm run build` and `dist`. Set `VP_API_ORIGIN` as a **build** variable for the target environment. The origin has no path, credentials or trailing slash. Leave preview environments disconnected or point them at the data-free validation service. Keep confidential values out of all frontend settings.
4. Vercel initially selects this repository’s Phase 0 default even when importing a commit URL. Set Project Settings → Environments → Production → Branch Tracking to `feat/final-deployment-and-product-polish`. Under Deployments → Deployments actions → Create Deployment, enter this branch and verify the resolved SHA before selecting Deploy to Production. Inspect the build logs. Set `VP_FRONTEND_ORIGIN` to Vercel’s issued HTTPS origin. Run the checks below, then open the site in Chrome. The disconnected workspace must withhold credential and document inputs. Provider-generated addresses are sufficient for personal validation.

```sh
: "${VP_API_ORIGIN:?Use the actual Render HTTPS origin}"
: "${VP_FRONTEND_ORIGIN:?Use the actual Vercel HTTPS origin}"
curl --fail --silent --show-error "$VP_API_ORIGIN/api/v1/health"
curl --fail --silent --show-error "$VP_FRONTEND_ORIGIN/api/v1/health"
curl --silent --show-error --output /dev/null --write-out '%{http_code}\n' "$VP_FRONTEND_ORIGIN/api/v1/health/db"
curl --fail --head "$VP_FRONTEND_ORIGIN/login"
```

The Vercel build uses an external rewrite; API URLs never fall through to the SPA. A missing upstream leaves API paths unserved. Separately check any future production upstream at 5 MiB with synthetic PDF content. A configured rewrite must preserve request bodies, the Origin header, cookies and private response headers. Validate client-IP attribution at both proxy hops before using address-based login limits. Remove obsolete upstream routes when retiring a host.

For a production release follow [the Linux operations guide](OPERATIONS.md). Supply an approved Linux API/worker target with DNS and a tested namespace policy. If using Render PostgreSQL from that host, allow only the host’s stable egress CIDR, use the provider’s verified certificate chain and test recovery from outside the primary database. Keep migrations and initial provisioning under a separate database owner. Verify grants after every migration.

Provider references: [Render Free](https://render.com/docs/free), [disk constraints](https://render.com/docs/disks), [PostgreSQL access](https://render.com/docs/postgresql-creating-connecting), [Vercel external rewrites](https://vercel.com/docs/routing/rewrites), [Hobby usage](https://vercel.com/docs/plans/hobby).
