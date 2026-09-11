# Northwind Commerce

Northwind Commerce is a modern B2B storefront sample that demonstrates web, API, database, cache, payment, CI, and deployment-promotion flows.

## Important Links

| Resource | Link / purpose |
| --- | --- |
| Live storefront | [northwind-commerce.onrender.com](https://northwind-commerce.onrender.com) |
| API documentation | [Swagger UI](https://northwind-commerce.onrender.com/docs) |
| Public API checks | [Liveness](https://northwind-commerce.onrender.com/health/live) · [Catalog](https://northwind-commerce.onrender.com/catalog) |
| Render service | [Deploy history](https://dashboard.render.com/web/srv-dafi29v40ujc73bcolgg/deploys) · [Runtime logs](https://dashboard.render.com/web/srv-dafi29v40ujc73bcolgg/logs) · [CPU/memory metrics](https://dashboard.render.com/web/srv-dafi29v40ujc73bcolgg/metrics) |
| Render configuration | [Environment variables](https://dashboard.render.com/web/srv-dafi29v40ujc73bcolgg/env) · [Service settings](https://dashboard.render.com/web/srv-dafi29v40ujc73bcolgg/settings) |
| Render blueprint | [Infrastructure configuration and sync status](https://dashboard.render.com/blueprint/exs-dafi268u01pc73ai2tdg) |
| Grafana dashboard | [Northwind Commerce: request rate, errors, latency, checkout results, and logs](https://nimbleomelette894.grafana.net/d/northwind-observability/northwind-commerce) |
| Grafana Explore | [Query metrics, logs, and traces](https://nimbleomelette894.grafana.net/explore) |
| Grafana plan and usage | [Cloud account and free-plan usage](https://grafana.com/orgs/nimbleomelette894/my-account/manage-plan) |
| PostHog dashboard | [Northwind event counts and checkout funnel](https://us.posthog.com/project/598963/dashboard/2074658) |
| PostHog events | [Event history](https://us.posthog.com/project/598963/activity/explore) · [Live stream](https://us.posthog.com/project/598963/activity/live) |
| PostHog configuration and usage | [Project settings](https://us.posthog.com/project/598963/settings/project-details) · [Usage and billing](https://us.posthog.com/organization/billing/overview) |
| GitHub repository | [Source code and pull requests](https://github.com/scryr-app/ex-northwind-commerce) · [All workflow runs](https://github.com/scryr-app/ex-northwind-commerce/actions) |
| CI | [Frontend and API checks](https://github.com/scryr-app/ex-northwind-commerce/actions/workflows/ci.yml) |
| Integration tests | [Docker storefront/API tests](https://github.com/scryr-app/ex-northwind-commerce/actions/workflows/integration.yml) |
| Public uptime | [Scheduled availability checks and manual runs](https://github.com/scryr-app/ex-northwind-commerce/actions/workflows/uptime.yml) |
| Verify deployment | [Run smoke checks against an already deployed service](https://github.com/scryr-app/ex-northwind-commerce/actions/workflows/deploy.yml) |

Render, Grafana, and PostHog administration pages require access to the corresponding account.

## Stack

- React/Vite storefront in `web/`
- FastAPI service in `api/`
- Postgres for catalog, customer, and order data
- Redis for session, checkout, and risk-cache examples
- Stripe payment-intent integration with a safe stub path
- GitHub Actions for CI and uptime checks; Render for deployment
- Grafana Cloud Free for metrics, logs, and traces
- PostHog Cloud for storefront analytics and checkout funnels
- Terraform stubs for environment wiring

## Render Deployment

The simplest hosted demo uses **one free Render web service** for both React and
FastAPI. The root `Dockerfile` builds the frontend and serves it from FastAPI on
the same URL. [render.yaml](render.yaml) configures `northwind-commerce` in Ohio
with `plan: free`, branch `main`, `autoDeployTrigger: checksPass`, and the
`/health/live` health check. The existing deployment is linked above.

### Deploy an update

1. Open a pull request and let **Web**, **API**, and **Hosted app integration** pass.
2. Merge into `main`. GitHub Actions runs checks again on the merged commit.
3. Render's connected GitHub integration waits for that commit's checks to pass,
   then builds the root [Dockerfile](Dockerfile) and deploys the storefront and API.
4. In the Render service dashboard, confirm the deployment is **Live** and its
   commit matches the intended `main` commit. Open the storefront and catalog,
   or run **Verify deployment** with `https://northwind-commerce.onrender.com`.

GitHub Actions runs the checks; Render performs the deployment. **Verify
deployment** only tests an existing deployment. **Public uptime** checks the
public storefront, catalog, and liveness every 30 minutes independently.

To redeploy manually, open the Render service and choose **Manual Deploy → Deploy
latest commit**. **Restart service** restarts the currently deployed commit; it
does not pick up a newer merge. If a merge does not trigger a deployment, check
the checks on the merged `main` commit, Render's deploy events, the linked branch
and **After CI Checks Pass** setting, and that the Render GitHub app still has
access to `scryr-app/ex-northwind-commerce`. See
[Render's deployment guide](https://render.com/docs/deploys) for trigger details.

Manage secrets in the Render service's **Environment** settings. Grafana's
`OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` are already configured
there; keep the authorization header out of Git and frontend variables.
PostHog's `VITE_POSTHOG_PROJECT_TOKEN` and `VITE_POSTHOG_HOST` are also configured
there and embedded during the frontend build. Use **Save, rebuild, and deploy**
after changing them; a restart alone does not update the browser bundle.
The blueprint supplies the remaining demo
defaults and generates the protected `/metrics` token. See
[hosting setup and verification](docs/hosting.md) for runtime settings.

### Create another free deployment

Use [Deploy on Render](https://render.com/deploy?repo=https://github.com/scryr-app/ex-northwind-commerce),
sign in, connect the repository, and confirm the blueprint contains only one
**Free** web service. A new deployment gets its own URL and requires its own
[Grafana connection](docs/observability.md) and
[PostHog project configuration](docs/product-analytics.md). No database, payment key, custom
domain, or paid add-on is needed for catalog browsing and stubbed checkout.

This is a sample environment: orders are not persisted, authentication is not
enforced, and payments are stubbed.
Postgres and Redis remain available in local Docker Compose and can be connected
later. [Free Render services](https://render.com/docs/free) sleep after 15 minutes
without traffic, so the first request can take about a minute. This is one shared
demo environment; staging and production are not separately provisioned.

## Quick Start

```bash
cp .env.example .env
docker compose up
```

Open:

- Storefront: http://localhost:5173
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Local Development

Web:

```bash
cd web
npm install
npm run dev
```

API:

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn northwind_api.main:app --reload
```

Seed Postgres:

```bash
./scripts/seed-data.sh
```

Smoke test:

```bash
./scripts/smoke-test.sh
```

## Monitoring

The deployed Render service sends metrics, structured request logs, and traces
to the **nimbleomelette894 Grafana Cloud Free** stack. Use the dashboard and Explore
links above. Metrics export every minute; request traces and successful request
logs are sampled at 10%, while all error response logs are retained. New charts
can take a few minutes to populate; checkout charts require checkout traffic.

Render also provides runtime logs and CPU/memory charts. GitHub Actions supplies
scheduled public uptime checks, and Dependabot checks for updates weekly.
Cloud alert rules and email notification routing are **not activated**. See
[observability setup](docs/observability.md) for credentials, free-tier limits,
sampling, and alert configuration.

PostHog tracks catalog views, quantity changes, and checkout attempts/results with
explicit anonymous events. Session replay and automatic click capture are off.
Use the **Northwind dashboard** above for event counts and the catalog-to-payment-intent
funnel. The starter dashboard expects automatic pageviews, which this app does not
send, so its charts can remain empty even when custom events are arriving.
See [product analytics](docs/product-analytics.md) for the event definitions,
Render build-time configuration, and free-plan usage.

## Integration Tests

The [integration suite](tests/integration/test_hosted_app.py) exercises the shipped
frontend/API over HTTP, with real Postgres and Redis connections and with both
services stopped. It covers catalog-to-checkout flow, request validation,
inventory errors, frontend assets, CORS, and health reporting.

[Integration tests](.github/workflows/integration.yml) run on pull requests, pushes
to `main`, and manual dispatch. See [local instructions](docs/testing.md).

## Core Manifests

The sample surfaces five core manifests in `index.scry`:

- `northwind-web`
- `northwind-api`
- `northwind-postgres`
- `northwind-redis`
- `stripe-integration`

## Environment

Copy `.env.example` to `.env`. Use `STRIPE_SECRET_KEY=sk_test_stub` to keep checkout fully local. Set a real Stripe test key only when you want the API to create live test-mode payment intents.

## Repository Layout

```text
northwind-commerce/
├── README.md
├── index.scry
├── docker-compose.yml
├── .env.example
├── .github/workflows/
├── web/
├── api/
├── infra/
├── docs/
└── scripts/
```

## Report build status to Crystal

`.github/workflows/report-action-status.yml` sends the completed **CI** and
**Integration tests** workflow results to both `northwind-commerce/web` and
`northwind-commerce/api`. Both cards display the same latest reported workflow
result. The Rust `scryr report-action-status` command reads GitHub's completion
event, so a failed source workflow is reported too. Deployment and scheduled
uptime checks are excluded from build status. Reporting is opt-in: its job remains
skipped until `SCRYR_ENDPOINT` and `SCRYR_CLI_REF` are configured.

Configure these repository **Actions variables**:

| Variable | Value |
| --- | --- |
| `SCRYR_ENDPOINT` | Reachable HTTPS GraphQL URL, or loopback URL for a same-host runner |
| `SCRYR_CLERK_ORG_ID` | Organization containing the published map; remote mode only |
| `SCRYR_CLI_REF` | Reviewed full commit SHA in `scryr-app/scryr-dev` containing the Rust `report-action-status` command |
| `SCRYR_RUNNER` | Optional dedicated self-hosted label for loopback OSS; defaults to `ubuntu-24.04` |

For a remote Clerk-authenticated server, add the **Actions secret** `SCRYR_TOKEN`
with permission to report history to that organization. Local same-host mode does
not need it. `GITHUB_TOKEN` is supplied automatically with Contents read permission
for branch discovery. No GitHub credential is stored in the manifest.

Publish the Scryr CLI implementation first, then set `SCRYR_CLI_REF` to its
commit. Publish this repository's updated `index.scry` to the same Crystal
organization so the stable manifest IDs match the reports. The reporter workflow
must be present on this repository's default branch to receive completion events.

The reporter selects `main` if it exists, otherwise `master`, otherwise the
repository default branch. Runs from other branches are skipped. It reports the
whole workflow's conclusion, not individual job conclusions. The newer of CI and
Integration tests determines build status; this is not an aggregate of both checks.
An open map refreshes every 30 seconds after Crystal receives the report.
For a loopback OSS server, use a dedicated self-hosted runner; GitHub-hosted runners
cannot reach your machine's `127.0.0.1`. See the complete
[OSS credentials and connection guide](docs/scryr-connections.md#6-configure-github-actions-reporting).
