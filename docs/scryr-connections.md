# Grafana and PostHog in Scryr

This follows Scryr's
[`query` workflow](https://github.com/scryr-app/scryr-dev/tree/main/crystal/crystal-cli#query-declared-providers).
Northwind already has ingestion integrations. Scryr needs separate read credentials
to populate the diagram; ingestion credentials cannot serve this purpose.

## Choose the OSS topology

- **Local OSS (recommended for trying it out):** run Scryr on `127.0.0.1` with
  local auth and SQLite. Cloud metrics work from your machine. GitHub Actions
  history can be replayed with the CLI, or automated with a self-hosted GitHub
  runner on the same machine.
- **Hosted OSS:** deploy Scryr behind HTTPS with `AUTH_MODE=clerk`. A GitHub-hosted
  runner can then report workflow history, but it needs a valid Clerk bearer token
  and organization ID. Never expose Scryr's shared local-auth mode publicly.

The commands below use local OSS.

## 1. Create the Grafana read credential

1. Open the [Grafana Cloud Portal](https://grafana.com/profile/org), select the
   `nimbleomelette894` stack, and open
   **Prometheus → Details**.
2. Copy the **query endpoint** and **user/instance ID**. Use the query endpoint,
   not the remote-write or OTLP ingestion endpoint.
3. Create a stack-scoped Cloud Access Policy named `scryr-northwind-read` with only
   `metrics:read`, then create a short-lived token for it. This token is the Basic
   Auth password used by Scryr. Do not reuse the application's write token.

## 2. Create the PostHog read credential

1. Open [PostHog project `598963`](https://us.posthog.com/project/598963), then
   **Settings → User → Personal API keys**.
2. Create a key named `scryr-northwind-read` with query/read access to this project.
3. Copy the personal API key once. Do not use the public project ingestion token;
   it cannot query analytics and is intentionally safe to expose in the storefront.

The PostHog project is in the US region, so its query base URL is
`https://us.posthog.com`.

## 3. Create the private Scryr connection file

Create a JSON file outside source control, readable only by your user. For example,
save this as `$HOME/.config/scryr/northwind-connections.json`, replace every
placeholder, and then run `chmod 600` on it. Merge these entries into any existing
connections file, preserving other connections:

```json
{
  "local-dev-org": {
    "northwind-grafana-read": {
      "endpoint": "https://YOUR-GRAFANA-QUERY-HOST/prometheus",
      "username": "YOUR-METRICS-INSTANCE-ID",
      "token": "YOUR-METRICS-READ-TOKEN"
    },
    "northwind-posthog-read": {
      "endpoint": "https://us.posthog.com",
      "project_id": 598963,
      "token": "YOUR-POSTHOG-QUERY-READ-PERSONAL-API-KEY"
    }
  }
}
```

For hosted authenticated deployments, replace `local-dev-org` with the authenticated
Scryr organization ID. Copy the Grafana Prometheus query endpoint and instance
ID from the existing stack's connection details. Use a separate `metrics:read`
access policy token, not the Render OTLP write token. PostHog requires a personal
API key with Query Read access to project 598963. Never put either read token in
`index.scry`, browser variables, command arguments, or Git.

## 4. Start OSS Scryr and load Northwind

From `scryr-dev`, build the distributed binary once:

```sh
mise install
mise run contribute:setup
mise run release:build
```

Start/restart Scryr with the absolute connection-file path and a stable SQLite
path so reports survive restarts:

```sh
env -u DATABASE_URL -u TURSO_DATABASE_URL -u TURSO_AUTH_TOKEN \
SCRYR_SQLITE_PATH="$PWD/.scryr/scryr.db" \
SCRYR_METRICS_CONNECTIONS_FILE="$HOME/.config/scryr/northwind-connections.json" \
  ./crystal/target/release/scryr serve --server-only --auth-mode local --port 8001
```

Unsetting other database variables is important because they take precedence over
`SCRYR_SQLITE_PATH`.

Connections are read at startup. The Grafana endpoint resolves from the private
connection. PostHog's endpoint and project must match the public manifest settings.

In a second terminal, load the Northwind manifest and list its queries:

```sh
cd ../ex-northwind-commerce
../scryr-dev/crystal/target/release/scryr push \
  --path index.scry --manifest-dir . \
  --endpoint http://127.0.0.1:8001/graphql

../scryr-dev/crystal/target/release/scryr query --list \
  --path index.scry --manifest-dir .
```

## 5. Verify Grafana and PostHog

Run one query from each provider through the server-side credential boundary:

```sh
../scryr-dev/crystal/target/release/scryr query requestRate \
  --path index.scry --manifest-dir . \
  --endpoint http://127.0.0.1:8001/graphql --json

../scryr-dev/crystal/target/release/scryr query catalogViews \
  --path index.scry --manifest-dir . \
  --endpoint http://127.0.0.1:8001/graphql --json
```

Then open `http://127.0.0.1:8001`, select Northwind, and inspect the API metrics
and web analytics cards. A `ready` response with an empty series means there was
no data in the window; authentication and connection failures remain explicit
errors and are never displayed as zero.

## 6. Configure GitHub Actions reporting

The checked-in reporter is opt-in. Without `SCRYR_ENDPOINT` and `SCRYR_CLI_REF`,
its job is skipped instead of making otherwise-successful workflows look broken.

For a hosted, Clerk-authenticated OSS server, configure the repository after the
Scryr commit containing the reporter has been pushed:

```sh
gh variable set SCRYR_ENDPOINT --repo scryr-app/ex-northwind-commerce \
  --body 'https://YOUR-SCRYR-HOST/graphql'
gh variable set SCRYR_CLERK_ORG_ID --repo scryr-app/ex-northwind-commerce \
  --body 'org_YOUR_ORGANIZATION_ID'
gh variable set SCRYR_CLI_REF --repo scryr-app/ex-northwind-commerce \
  --body 'FULL_40_CHARACTER_REVIEWED_SCRYR_COMMIT_SHA'
gh secret set SCRYR_TOKEN --repo scryr-app/ex-northwind-commerce
```

The last command prompts without echoing the token. Do not put the token directly
in shell history. The remote endpoint must be HTTPS.

For loopback local auth, install a GitHub self-hosted runner on the Scryr machine,
give it a dedicated label such as `scryr-local`, and set:

```sh
gh variable set SCRYR_RUNNER --repo scryr-app/ex-northwind-commerce \
  --body 'scryr-local'
gh variable set SCRYR_ENDPOINT --repo scryr-app/ex-northwind-commerce \
  --body 'http://127.0.0.1:8001/graphql'
gh variable set SCRYR_CLI_REF --repo scryr-app/ex-northwind-commerce \
  --body 'FULL_40_CHARACTER_REVIEWED_SCRYR_COMMIT_SHA'
```

This local mode does not need `SCRYR_TOKEN` or `SCRYR_CLERK_ORG_ID`, but the runner
and Scryr process must share the same host and Scryr must remain loopback-bound.
Use a dedicated runner because Actions jobs execute repository code.

After configuration, manually run CI or push to `main`. The completion event is
written to both `northwind-commerce/web` and `northwind-commerce/api`; the cards
refresh within 30 seconds. Identical delivery retries are idempotent.

## 7. Generate production traffic and verify windows

1. Build/deploy Northwind with `VITE_POSTHOG_ENVIRONMENT=production` and its existing
   public ingestion token and host. The Dockerfile accepts the environment build
   argument; `render.yaml` supplies the production value. Existing Render services
   may need the variable added manually and a rebuild. Local builds default to
   `local` and do not contribute to production counts.
2. If the manifest changed, upload it again to the running local Scryr server:

   ```sh
   ../scryr-dev/crystal/target/release/scryr push \
     --path index.scry --manifest-dir . \
     --endpoint http://127.0.0.1:8001/graphql
   ```

3. Browse the storefront and, if desired, exercise stub checkout. Allow at least
   two minutes for ingestion. Open/reopen the Northwind diagram and inspect
   `diagramMetrics` in browser DevTools. Compare the displayed UTC window with
   Grafana and PostHog. A successful empty response is no data; authentication
   failures are unavailable, never zero.

The API card requests five metrics over 15 minutes; the web analytics card requests
six event counts over 24 hours. Both filter/configure production, delay the window
by two minutes, and cache for 60 seconds. Only diagram loads collect data; routine
block polling does not. Checkout intents are not completed payments.

Repository configuration alone does not install private credentials, restart
Scryr, upload the manifest, or deploy Northwind. Live verification requires those
steps and actual provider access.

References: [Grafana query authentication](https://grafana.com/docs/grafana-cloud/observe-and-act/send-data/metrics/metrics-prometheus/query-http-api/),
[PostHog Query API](https://posthog.com/docs/api/queries).
