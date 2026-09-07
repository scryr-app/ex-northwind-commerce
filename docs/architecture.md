# Architecture

Northwind Commerce is organized around a buyer-facing React storefront and a FastAPI backend.

## Request Flow

1. The web app loads `/catalog` from `northwind-api`.
2. The buyer selects case quantities and submits a checkout request.
3. The API validates inventory, calculates order value, scores payment risk, and creates a Stripe payment intent.
4. Postgres is the source of record for products and orders.
5. Redis is reserved for session state, checkout idempotency, and risk-score caching.

## Services

- `northwind-web`: React/Vite storefront.
- `northwind-api`: FastAPI catalog and checkout service.
- `northwind-postgres`: relational data store.
- `northwind-redis`: cache and ephemeral checkout state.
- `stripe-integration`: payment intent creation and webhook target.

## Payment Risk

The sample risk model is deliberately transparent. It increases score for high order value, large quantities, expedited shipping, and cold-chain seafood items. Production systems should replace this with a policy engine or model that uses audited features.

## Hosted demo

`render.yaml` defines one free Docker service that serves the React build through
FastAPI. Render deploys `main` after GitHub Actions checks pass; `deploy.yml`
verifies an existing deployment. See [hosting](hosting.md) for setup and limits.
The demo currently uses an in-memory catalog and does not persist checkout orders.
Postgres and Redis are optional future hosted dependencies; the Terraform files
remain illustrative stubs and are not used by this deployment.
