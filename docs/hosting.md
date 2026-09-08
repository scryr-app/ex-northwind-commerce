# Free hosting

## Architecture

One Render Free Docker web service serves the compiled React storefront and the
existing FastAPI endpoints from a single HTTPS `onrender.com` URL. This avoids
separate frontend hosting, API URL configuration, CORS setup, and extra accounts.

The deployed demo uses the existing in-memory catalog and stubbed checkout.
It does not persist orders, enforce authentication, or process real payments.
No Postgres or Redis is provisioned by the blueprint. Both remain in local Docker
Compose for development; connect managed instances when implementing persistence.

## Initial deployment

1. Push the hosting changes to `main` in
   `https://github.com/scryr-app/ex-northwind-commerce`.
2. Open https://render.com/deploy?repo=https://github.com/scryr-app/ex-northwind-commerce
   and sign in to Render. Connect the repository if prompted.
3. Review the `render.yaml` blueprint. It must show one Docker web service named
   `northwind-commerce` on the **Free** plan, with no databases, disks, or workers.
4. Create the blueprint and wait for the initial deployment. Use the actual
   service URL shown in Render; the hostname may have a uniqueness suffix.
5. Browse the storefront, select a product, and run stubbed checkout. Check
   `/health/live`, `/catalog`, and `/docs` on the same URL.
6. Run GitHub Actions → **Verify deployment** with the assigned URL, or run:

   ```sh
   API_URL=https://YOUR-SERVICE.onrender.com ./scripts/smoke-test.sh
   ```

## CI/CD

GitHub Actions runs frontend tests/build and API unit tests. The dedicated
**Integration tests** workflow builds the actual deployment image and tests it
over HTTP with real Postgres/Redis, then repeats with those dependencies stopped.
See [testing](testing.md) for coverage and local commands. Render's `checksPass` trigger deploys
`main` after its checks pass. The initial blueprint creation also builds the image.
The separate **Verify deployment** workflow checks an already deployed service;
it does not trigger a deployment or claim that one has succeeded.

For a manual redeploy or rollback, use the Render service dashboard. There is one
shared demo environment, not separate staging and production services.

## Runtime settings

The Docker image sets `STATIC_DIR=/app/web/dist` and respects Render's `PORT`.
The Vite build uses an empty `VITE_API_URL`, so requests go to the same origin.
Local Vite development retains its existing `http://localhost:8000` fallback.
`STRIPE_SECRET_KEY=sk_test_stub` is a harmless sentinel, not a real credential.

If adding Neon and Upstash later, enter `DATABASE_URL` and `REDIS_URL` in Render's
secret environment settings. Use TLS connection strings. The `/health` endpoint
reports dependency availability and will report `unavailable` until they exist.
It currently returns HTTP 200 even for unavailable dependencies, so inspect its
JSON rather than using HTTP status alone as a readiness signal.

## Monitoring and limits

Render uses `/health/live` for health probes; it checks only the API process.
Runtime/access logs are available in the service dashboard. This initial setup
does not provision Grafana, external uptime alerts, or a public status page.
Do not use frequent `/health` probes: they query the database and can prevent a
future Neon database from scaling to zero.

The [Render free tier](https://render.com/docs/free) sleeps after 15 minutes without
traffic and may take about a minute to wake. Its 750 monthly instance-hours are
shared across the workspace. Filesystem changes disappear on restart/redeploy.
Keep the workspace on a free plan, avoid paid resources, and do not add a payment
method just to increase quotas. With no payment method, excess bandwidth suspends
free services instead of generating an overage charge; exhausted build minutes
disable new builds. This is a demonstration environment, not an always-on B2B SLA.

## Local production check

```sh
docker build -t northwind-commerce .
docker run --rm -p 10000:10000 northwind-commerce
```

Open http://localhost:10000 and run the smoke test with that `API_URL`. No `.env`
file is copied into the image, and the runtime runs as a non-root user.

## Scryr follow-up

Keep the five logical manifests in `index.scry`. Once the service exists, record
its actual URL and Render deployment on the web/API manifests and link the CI and
Render dashboards. Do not label Postgres, Redis, or external monitoring as deployed
until they are provisioned. The web and API share one physical runtime initially.
