# SaaS service configuration

All integrations are optional and disabled when their environment variables are blank.
Secrets belong in Render, never in Git or frontend build arguments.

## Monitoring and availability

- **Sentry:** create Python/FastAPI and React projects. Set `SENTRY_DSN` on Render;
  provide the public React DSN as the Docker build argument `VITE_SENTRY_DSN`.
  Releases use `RENDER_GIT_COMMIT`. Default PII collection is disabled.
- **Better Stack:** monitor `/health/live` for process availability and `/health` for
  dependency status. Add the public storefront and catalog as separate monitors, then
  expose them on one status page. No application credential is required.

## Runtime services

- **Supabase:** copy the transaction-pooler Postgres URI into `DATABASE_URL`. Apply
  `api/migrations/001_initial.sql` before enabling persistent order writes. Keep SSL
  required in the connection URI.
- **Resend:** verify a sending domain, then configure `RESEND_API_KEY`,
  `ORDER_EMAIL_FROM`, and `ORDER_EMAIL_TO`. Checkout succeeds even if email delivery
  fails; failures are logged and captured by Sentry.
- **Cloudflare Turnstile:** create a widget for the production hostname. Configure the
  public `VITE_TURNSTILE_SITE_KEY` at frontend build time and keep
  `TURNSTILE_SECRET_KEY` in Render. When the secret is configured, checkout fails closed
  if verification is missing or unavailable.

After provisioning, trigger a Render rebuild because Vite values are embedded in the
browser bundle. Better Stack and Sentry should then be tested with non-production test
events before relying on alerts.
