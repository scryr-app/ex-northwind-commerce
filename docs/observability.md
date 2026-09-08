# Free observability

Use one Render Free service and one Grafana Cloud Free stack. No separate
collector, worker, paid monitoring agent, or persistent disk is needed.

## Included in this change

- JSON request logs on stdout, visible in Render after deployment.
- Protected Prometheus metrics at `/metrics`: request counts, latency histograms,
  and accepted/rejected/failed checkout attempts.
- Optional OTLP/HTTP export of metrics, logs, and sampled request traces directly
  to Grafana Cloud. Checkout traces include risk and payment-processing spans.
- An importable Grafana dashboard in `infra/monitoring/grafana-dashboard.json`.
- Optional Prometheus/Mimir alert rules in `infra/monitoring/alerts.yml`.
- A **Public uptime** GitHub Actions workflow that checks liveness, storefront
  HTML, and the catalog every 30 minutes and on manual dispatch.
- Weekly Dependabot updates for Python/uv, npm, GitHub Actions, and the Dockerfile.

Grafana export is disabled until its endpoint is configured. Adding these files
does not create a Grafana account, import a dashboard, or activate cloud alerts.
Changes must be merged into `main` and deployed before they affect the live app.

## Connect Grafana Cloud Free

1. Sign in at https://grafana.com/auth/sign-in/ and create/select a **Free** stack.
   No payment method is needed. Do not upgrade the plan or enable paid add-ons.
2. In the stack's connections, open **OpenTelemetry** and copy the supplied
   OTLP/HTTP endpoint and authorization-header configuration. Use an ingest token
   scoped only to writing metrics, logs, and traces in this stack.
3. Add these secret environment variables to the Render service:

   ```text
   OTEL_EXPORTER_OTLP_ENDPOINT=<the supplied base endpoint, usually ending in /otlp>
   OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<the supplied encoded credentials>
   ```

   Copy the credentials exactly from Grafana; never commit them or put them in
   a frontend `VITE_` variable. Do not append `/v1/traces` to the base endpoint:
   the app adds the appropriate path for each signal. Render environment changes
   require a deployment to take effect.
4. Browse the catalog and run a stub checkout. Metrics export once a minute;
   traces and logs are batched. By default only 10% of traces and successful
   request logs are retained. All 4xx/5xx request logs are retained. Temporarily
   set both sampling ratios to `1` when verifying, then restore them to `0.1`.
5. Import `infra/monitoring/grafana-dashboard.json` through **Dashboards → New →
   Import**, selecting your stack's Prometheus and Loki data sources. Metrics use
   `job="northwind-api"`; request logs use `service_name="northwind-api"`.
6. In Explore, choose Tempo and search `service.name="northwind-api"` to inspect
   sampled request traces. Request log metadata includes a `trace_id` for
   correlation. A log can refer to an unsampled trace that was not stored.

For authenticated automation, use a separate least-privilege Grafana service
account; an OTLP ingest token cannot create dashboards or alert rules.

## Local metrics and Render settings

The Render blueprint generates a `METRICS_TOKEN`. `/metrics` returns 404 if the
secret is unset and 401 if authorization is missing or incorrect. Read it with:

```sh
curl -H "Authorization: Bearer $METRICS_TOKEN" https://northwind-commerce.onrender.com/metrics
```

The token is only needed for scraping metrics directly, not for OTLP export.
For local testing, set your own token in `.env`; the integration stack uses a
fixed disposable test token. Metrics reset when an instance restarts. Grafana
receives a unique service instance ID so overlapping deploys do not collide.
Render's built-in CPU and memory charts remain available in its dashboard.

| Setting | Default | Purpose |
| --- | --- | --- |
| `OTEL_TRACE_SAMPLE_RATIO` | `0.1` | Fraction of request traces exported |
| `REQUEST_LOG_SAMPLE_RATIO` | `0.1` | Fraction of successful request logs retained |
| `OTEL_METRIC_EXPORT_INTERVAL` | `60` | Seconds between metric exports; minimum 60 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | empty | Empty disables all cloud export |
| `OTEL_EXPORTER_OTLP_HEADERS` | empty | Secret OTLP authentication headers |
| `METRICS_TOKEN` | empty locally | Bearer token enabling `/metrics` |

The app propagates valid W3C traceparent IDs. Metric labels use only a fixed set
of routes, HTTP methods, status codes, and checkout outcomes. Request IDs and
customer IDs are never metric labels. Request logs and exported spans exclude
raw URLs, query strings, headers, payloads, payment secrets, and exception
messages. Unknown paths are grouped as `unmatched`. Render's Docker start command
disables Uvicorn's duplicate raw access logs. Runtime exception tracebacks remain
separate server logs; this is not a blanket redaction layer for third-party code.

Cloud export uses background batches, small queues, three-second exporter timeouts,
and limited trace/log sampling. If Grafana is unavailable, requests continue;
telemetry may be dropped. Failed responses are always counted in metrics.

## Availability and alerts

**Public uptime** runs at minutes 7 and 37, leaves time for Render cold starts,
and never calls checkout or `/health` (which queries optional databases).
`NORTHWIND_PUBLIC_URL`, a repository variable, can override the default service URL.
Check GitHub's notification settings to receive email for failed Actions runs.
No workflow sends Slack messages, opens incidents, or sends customer email.

Schedules are best-effort, run from the default branch, and may be delayed or
paused by GitHub. They are suitable for this demo, not a continuous uptime SLA.
They can wake the Render service twice an hour, consuming part of the shared free
instance-hours allowance. Health probes and static assets are excluded from app
request telemetry; the synthetic storefront/catalog checks count as requests.

For cloud alerts, load `infra/monitoring/alerts.yml` into the stack's Prometheus/
Mimir ruler or reproduce the expressions in Grafana Alerting. Configure and test
an email contact point before relying on notifications. The rules cover sustained
5xx errors above 5% and p95 request latency above one second, with at least 20
requests in ten minutes. There is no absent-metrics alert because Render sleeps.
These rules are supplied as configuration, not automatically provisioned.

## Stay within the free plans

Grafana Cloud Free currently includes 10,000 active metric series, 50 GB each of
logs and traces per month, and 14 days of retention. This app limits route labels,
samples telemetry, and avoids instrumenting health/static requests. Monitor
actual usage in Grafana; low-volume operation is intended, not guaranteed under
arbitrary traffic. Stay on the Free plan without a payment method. The uptime
workflow uses standard GitHub-hosted runners in this public repository. It does
not require another monitoring account.

Primary references: [Grafana pricing](https://grafana.com/pricing/),
[OTLP ingestion](https://grafana.com/docs/opentelemetry/ingest/),
[OTLP format mapping](https://grafana.com/docs/grafana-cloud/observe-and-act/send-data/otlp/otlp-format-considerations/),
[Render free limits](https://render.com/docs/free).

## Troubleshooting and Scryr

If Render says Live but the public URL responds with `x-render-routing: no-server`,
inspect the **Public uptime** result and Render events. An internal healthy process
is not proof of public availability. Missing telemetry can also mean an idle
service, sampling, an incorrect OTLP endpoint/token, or exhausted free quotas.

Once cloud setup is verified, link the Grafana dashboard, uptime workflow, and
Render logs from the Scryr manifests. Declare Grafana/Loki as active integrations
only after provisioning; the checked-in manifest should not claim services that
have not been connected. The SDK's Tempo representation still needs verification.

## Verification

Unit tests verify token protection, bounded labels, sensitive-data omission,
receiver failures, and authenticated OTLP delivery of all three signal types to
a temporary local receiver. Integration tests check metrics and request IDs
against the production Docker image in both dependency states. The public uptime
checker is tested against HTTP errors and misleading HTTP-200 error pages.
