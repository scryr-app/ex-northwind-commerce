# Grafana and PostHog in Scryr

This follows `../scryr-dev/docs/diagram-metrics.md` and
`../scryr-dev/docs/posthog-analytics.md` (`scryr-dev` is the local reference repo).
Northwind already has ingestion integrations. Scryr needs separate read credentials
to populate the diagram; ingestion credentials cannot serve this purpose.

## Private server configuration

Create a JSON file outside source control, readable only by your user (`chmod 600`).
Merge both entries into any existing connections file, preserving other connections:

```json
{
  "local-dev-org": {
    "northwind-grafana-read": {
      "endpoint": "https://YOUR-METRICS-HOST/prometheus",
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

For authenticated deployments, replace `local-dev-org` with the authenticated
Scryr organization ID. Copy the Grafana Prometheus query endpoint and instance
ID from the existing stack's connection details. Use a separate `metrics:read`
access policy token, not the Render OTLP write token. PostHog requires a personal
API key with Query Read access to project 598963. Never put either read token in
`index.scry`, browser variables, command arguments, or Git.

Start/restart Scryr with the absolute file path, preserving its existing
`SCRYR_SQLITE_PATH` value so it continues using the same database:

```sh
SCRYR_METRICS_CONNECTIONS_FILE=/absolute/private/path/metrics-connections.json \
  ../scryr-dev/crystal/target/debug/scryr serve --auth-mode local --port 8001
```

Connections are read at startup. The Grafana endpoint resolves from the private
connection. PostHog's endpoint and project must match the public manifest settings.

## Deploy and verify

1. Build/deploy Northwind with `VITE_POSTHOG_ENVIRONMENT=production` and its existing
   public ingestion token and host. The Dockerfile accepts the environment build
   argument; `render.yaml` supplies the production value. Existing Render services
   may need the variable added manually and a rebuild. Local builds default to
   `local` and do not contribute to production counts.
2. Upload the updated manifest to the running local Scryr server:

   ```sh
   SCRYR_GRAPHQL_URL=http://127.0.0.1:8001/graphql \
     ../scryr-dev/crystal/target/debug/scryr generate upload \
     --path "$PWD/index.scry" --manifest-dir "$PWD" \
     --scryr-dir "$PWD/../scryr-dev/.scryr"
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
