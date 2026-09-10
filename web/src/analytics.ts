import posthog, { type BeforeSendFn } from "posthog-js";

type CartSummary = { line_count: number; quantity: number; total_cents: number };
type Events = {
  catalog_viewed: { product_count: number };
  cart_updated: { product_id: string; quantity: number };
  checkout_started: CartSummary;
  checkout_intent_created: CartSummary & { payment_mode: "stubbed" | "stripe" };
  checkout_failed: CartSummary;
};

const eventProperties: Record<keyof Events, readonly string[]> = {
  catalog_viewed: ["product_count"],
  cart_updated: ["product_id", "quantity"],
  checkout_started: ["line_count", "quantity", "total_cents"],
  checkout_intent_created: ["line_count", "quantity", "total_cents", "payment_mode"],
  checkout_failed: ["line_count", "quantity", "total_cents"]
};

// Keep the public ingestion token and identity fields needed for anonymous funnels, but exclude URLs,
// referrers, DOM text, person properties, and arbitrary response/error data.
const sdkProperties = new Set([
  "token", "distinct_id", "$device_id", "$session_id", "$window_id", "$lib", "$lib_version"
]);

export const sanitizeEvent: BeforeSendFn = (event) => {
  if (!event || !Object.hasOwn(eventProperties, event.event)) return null;
  const allowed = eventProperties[event.event as keyof Events];
  event.properties = Object.fromEntries(
    Object.entries(event.properties).filter(([key]) => sdkProperties.has(key) || allowed.includes(key))
  );
  event.properties.environment = analyticsEnvironment;
  event.properties.$process_person_profile = false;
  event.properties.$geoip_disable = true;
  return event;
};

let enabled = false;
const analyticsEnvironment = import.meta.env.VITE_POSTHOG_ENVIRONMENT || "local";

export function initializeAnalytics(
  token = import.meta.env.VITE_POSTHOG_PROJECT_TOKEN ?? "",
  host = import.meta.env.VITE_POSTHOG_HOST ?? "https://us.i.posthog.com"
) {
  if (enabled || !token.trim()) return;
  try {
    posthog.init(token, {
      api_host: host,
      autocapture: false,
      capture_pageview: false,
      capture_pageleave: false,
      capture_dead_clicks: false,
      capture_exceptions: false,
      capture_heatmaps: false,
      capture_performance: false,
      disable_session_recording: true,
      disable_surveys: true,
      disable_external_dependency_loading: true,
      advanced_disable_flags: true,
      person_profiles: "never",
      persistence: "memory",
      disable_persistence: true,
      ip: false,
      respect_dnt: true,
      before_send: sanitizeEvent
    });
    enabled = true;
  } catch {
    // Analytics must not prevent the storefront from loading.
  }
}

export function trackEvent<E extends keyof Events>(event: E, properties: Events[E]) {
  if (!enabled) return;
  try {
    posthog.capture(event, properties);
  } catch {
    // A blocked or unavailable analytics service must not break checkout.
  }
}
