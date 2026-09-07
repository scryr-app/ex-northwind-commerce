# Northwind Commerce

Northwind Commerce is a modern B2B storefront sample that demonstrates web, API, database, cache, payment, CI, and deployment-promotion flows.

## Stack

- React/Vite storefront in `web/`
- FastAPI service in `api/`
- Postgres for catalog, customer, and order data
- Redis for session, checkout, and risk-cache examples
- Stripe payment-intent integration with a safe stub path
- GitHub Actions for CI and deploy promotion
- Terraform stubs for environment wiring

## Free Hosting

The simplest hosted demo uses **one free Render web service** for both React and
FastAPI. The root `Dockerfile` builds the frontend and serves it from FastAPI on
the same URL. `render.yaml` selects the free plan and deploys `main` after CI passes.

[Deploy on Render](https://render.com/deploy?repo=https://github.com/scryr-app/ex-northwind-commerce)

The deployment files must be pushed to GitHub before using that link. Sign in to
Render, connect this repository, and confirm the blueprint contains only one
**Free** web service. No database, payment key, custom domain, or paid add-on is
needed for catalog browsing and stubbed checkout.

This is a sample environment: orders are not persisted and payments are stubbed.
Postgres and Redis remain available in local Docker Compose and can be connected
later. Free Render services sleep when idle, so the first request can take about
a minute. See [hosting setup and verification](docs/hosting.md).

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
