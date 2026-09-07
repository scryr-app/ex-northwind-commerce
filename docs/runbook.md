# Runbook

## Start Local Stack

```bash
cp .env.example .env
docker compose up
```

## Verify Services

```bash
curl http://localhost:8000/health
curl http://localhost:8000/catalog
./scripts/smoke-test.sh
```

## Seed Data

```bash
DATABASE_URL=postgresql://northwind:northwind@localhost:5432/northwind ./scripts/seed-data.sh
```

## Stripe Mode

Use `STRIPE_SECRET_KEY=sk_test_stub` for local development. The API will return deterministic stub-shaped payment intent data without contacting Stripe.

Use a real Stripe test key only in isolated test environments. Never commit real keys.

## Hosted demo

Follow [the free hosting guide](hosting.md) to provision one Render Free service.
Render deploys `main` after CI passes. Run **Verify deployment** in GitHub Actions
with the assigned Render URL to check the storefront and stubbed checkout.
Use `/health/live` for platform probes; `/health` also checks optional databases.
This setup has one demo environment, with no staging/production promotion.
