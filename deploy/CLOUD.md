# Personal validation on Vercel and Render

This ₹0 deployment uses the existing Vercel Hobby frontend and a single Render Free web service. The hosted page displays the API connection and the result of Render’s startup parser probe. It offers a manual recheck and local setup instructions. A failed or unrecognized health response leaves sign-in closed.

The hosted API registers only the public health diagnostic. It has no sessions, tenant database, document store, ClamAV service or OCR worker. Workspace requests return 503. The frontend exposes no credential or upload form in this mode. A successful parser probe alone never enables supplier operations. Run the [local application](../README.md#run-locally) for the complete private workflow.

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

The Vercel build uses a same-origin external rewrite and private, no-store caching for API responses. Keep the existing Hobby project and the single Free service when publishing revisions. Frontend-only changes deploy from the tracked Git branch. The Render service needs a new deployment only when its release changes.
