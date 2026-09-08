# Product analytics with PostHog

Northwind uses PostHog Cloud's free product analytics allowance for the storefront
funnel. It needs no extra Render service or collector.

- [PostHog project](https://us.posthog.com/project/598963)
- [Live events](https://us.posthog.com/project/598963/activity/explore)
- [Dashboards](https://us.posthog.com/project/598963/dashboard)
- [Usage and billing](https://us.posthog.com/organization/billing)

## Events

| Event | Trigger | Application properties |
| --- | --- | --- |
| `catalog_viewed` | Catalog rendered, including the local fallback catalog | `product_count` |
| `cart_updated` | Buyer changes a product quantity | `product_id`, `quantity` |
| `checkout_started` | Buyer submits the cart | `line_count`, `quantity`, `total_cents` |
| `checkout_intent_created` | API returns a payment intent | Cart summary plus `payment_mode` (`stubbed` or `stripe`) |
| `checkout_failed` | Checkout request fails | Cart summary |

The funnel is `catalog_viewed` → `checkout_started` → `checkout_intent_created`.
The last step means an intent was created, **not that a payment completed**.
These are browser-observed events, not an order ledger; blockers, network failures,
or closing the page can prevent delivery.

## Render configuration

Set these in the existing Render service's **Environment** settings:

```text
VITE_POSTHOG_PROJECT_TOKEN=<public project token from PostHog project settings>
VITE_POSTHOG_HOST=https://us.i.posthog.com
```

Render supplies these as Docker build arguments. The root Dockerfile makes them
available during the Vite build. Use **Save, rebuild, and deploy** after changing
them; restarting an existing image does not rebuild its frontend configuration.
An empty project token disables analytics. Remove it and rebuild to disconnect.

The project token is a public, write-only ingestion credential intentionally
included in the browser bundle. Never use a personal API key or management token
in a `VITE_` variable. New deployments need their own project configuration; it
is not embedded in `render.yaml` or committed to Git.

For local development, copy `web/.env.example` to `web/.env.local`, fill in the
public project token, and restart Vite. Leave it empty for ordinary development
and automated tests so they do not generate production analytics.

## Data collection and free usage

Only the five events above are sent. Autocapture, automatic page views, session
replay, surveys, feature flags, performance capture, and exception capture are
disabled. The app does not identify customers or create person profiles.
Anonymous identity is kept in memory, so a page reload starts a new identity;
this supports a funnel within a page visit, not returning-user retention.

An allowlist removes URL/query strings, referrers, DOM text, customer details,
payment IDs/secrets, and exception messages from event properties. PostHog still
receives ordinary network connection metadata; geolocation enrichment is disabled.
The integration respects browser Do Not Track. Analytics failures do not block
the catalog or checkout.

The [free allowance](https://posthog.com/pricing) includes one million product
analytics events per month. Keep the account without a payment method and do not
enable paid usage or add-ons. Check the billing page for actual usage; the event
allowance is shared with other use of the account as described there.

## Verification

After deployment, open the storefront, change a quantity, and create a stubbed
payment intent. In **Activity**, confirm the catalog, cart, checkout-start, and
intent-created events, then inspect their properties. An over-inventory checkout
can verify `checkout_failed` without a real payment. Allow a short ingestion delay.

Unit tests verify disabled mode, failure isolation, and property/event filtering.
The existing CI builds the frontend, while Docker integration tests continue to
verify the storefront and checkout with analytics disabled.

References: [PostHog JavaScript configuration](https://posthog.com/docs/libraries/js/config),
[Render Docker environment variables](https://render.com/docs/docker#environment-variable-translation).
