# Integration tests

`tests/integration/` uses HTTPX and pytest against a separately running application.
It does not import FastAPI or replace database clients with mocks. The isolated
`docker-compose.integration.yml` builds the production Dockerfile and starts
Postgres 16 and Redis 7, without needing Render, secrets, or external paid services.

## Coverage

- The storefront HTML and compiled JavaScript/CSS are served from the API origin.
- The frontend bundle does not point at the local development API.
- API routes remain reachable alongside the static-file mount.
- Catalog responses satisfy the frontend contract and feed a stubbed checkout.
- Separate checkouts return distinct identifiers.
- Unknown products, insufficient inventory, invalid quantities, empty carts, and
  missing account IDs return the expected HTTP errors.
- CORS accepts the configured development origin and rejects untrusted origins.
- Static serving rejects missing assets, environment files, and path traversal.
- `/health` detects real Postgres/Redis availability. The entire suite repeats
  after both dependencies stop, demonstrating that liveness and demo checkout
  continue working while dependency health reports `unavailable`.

The current sample does not store checkout orders or use Redis for business
operations. These tests verify dependency connectivity, not order persistence or
payment-provider behavior. They fetch compiled frontend assets but do not execute
browser JavaScript. Real payments are never used.

## Run locally

Requirements: Docker with Compose, Python 3.12+, and uv. Run from the repository root:

```sh
uv sync --project api --locked --extra dev
docker compose -f docker-compose.integration.yml up --build --wait --wait-timeout 120
uv run --project api --locked --extra dev pytest tests/integration -v --dependency-state healthy

docker compose -f docker-compose.integration.yml stop postgres redis
uv run --project api --locked --extra dev pytest tests/integration -v --dependency-state unavailable

docker compose -f docker-compose.integration.yml down --volumes --remove-orphans
```

The app binds only to `127.0.0.1:10000`. To change the port, set
`INTEGRATION_PORT=10001` for Compose and pass `--base-url http://127.0.0.1:10001`
to pytest. The test target must be a local HTTP origin because tests submit
checkout requests. Do not point this suite at a live payment-enabled deployment.
Postgres and Redis are accessible only inside the isolated Compose network.

## GitHub Actions

`.github/workflows/integration.yml` runs on every pull request, on pushes to
`main`, and manually through **Actions → Integration tests → Run workflow**.
It builds the image once and runs the suite in both dependency states. A failure
in either phase fails the job. Container logs and JUnit reports are uploaded as
`integration-results`, retained for seven days; containers are cleaned up even
when a test fails. No repository secrets are required.

Existing **CI** jobs continue running unit tests. **Verify deployment** remains a
separate smoke test for the public Render URL, so a hosting routing outage is
reported independently of application integration failures.
