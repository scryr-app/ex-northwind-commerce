import { beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({ init: vi.fn(), capture: vi.fn() }));
vi.mock("posthog-js", () => ({ default: sdk }));

beforeEach(() => {
  vi.resetModules();
  vi.resetAllMocks();
});

describe("optional product analytics", () => {
  it("sends nothing and does not initialize without a project token", async () => {
    const { initializeAnalytics, trackEvent } = await import("../src/analytics");
    initializeAnalytics("");
    trackEvent("catalog_viewed", { product_count: 3 });
    expect(sdk.init).not.toHaveBeenCalled();
    expect(sdk.capture).not.toHaveBeenCalled();
  });

  it("initializes once and records explicit events without enabling other products", async () => {
    const { initializeAnalytics, trackEvent } = await import("../src/analytics");
    initializeAnalytics("phc_test", "https://eu.i.posthog.com");
    initializeAnalytics("phc_test", "https://eu.i.posthog.com");
    trackEvent("catalog_viewed", { product_count: 3 });
    expect(sdk.init).toHaveBeenCalledTimes(1);
    expect(sdk.init).toHaveBeenCalledWith("phc_test", expect.objectContaining({
      api_host: "https://eu.i.posthog.com",
      autocapture: false,
      capture_pageview: false,
      disable_session_recording: true,
      advanced_disable_flags: true,
      disable_persistence: true,
      person_profiles: "never"
    }));
    expect(sdk.capture).toHaveBeenCalledWith("catalog_viewed", { product_count: 3 });
  });

  it("does not throw into the storefront when SDK initialization fails", async () => {
    const { initializeAnalytics, trackEvent } = await import("../src/analytics");
    sdk.init.mockImplementation(() => { throw new Error("blocked"); });
    expect(() => initializeAnalytics("phc_test")).not.toThrow();
    trackEvent("checkout_failed", { line_count: 1, quantity: 2, total_cents: 37800 });
    expect(sdk.capture).not.toHaveBeenCalled();
  });

  it("does not throw into checkout when capture fails", async () => {
    const { initializeAnalytics, trackEvent } = await import("../src/analytics");
    initializeAnalytics("phc_test");
    sdk.capture.mockImplementation(() => { throw new Error("offline"); });
    expect(() => trackEvent("checkout_started", {
      line_count: 1, quantity: 2, total_cents: 37800
    })).not.toThrow();
  });

  it("preserves ingestion credentials and anonymous identity while removing sensitive properties", async () => {
    const { sanitizeEvent } = await import("../src/analytics");
    const result = sanitizeEvent({
      uuid: "test-event",
      event: "checkout_intent_created",
      properties: {
        token: "phc_public_ingestion_token",
        distinct_id: "anonymous-random-id",
        $session_id: "random-session",
        line_count: 1, quantity: 2, total_cents: 37800, payment_mode: "stubbed",
        $current_url: "https://demo.test/?email=buyer@example.com",
        $referrer: "https://demo.test/private",
        $set: { email: "buyer@example.com" },
        clientSecret: "secret", paymentIntentId: "pi_private",
        accountId: "customer", error: "private exception text"
      }
    });
    expect(result?.properties).toEqual({
      token: "phc_public_ingestion_token",
      distinct_id: "anonymous-random-id", $session_id: "random-session",
      line_count: 1, quantity: 2, total_cents: 37800, payment_mode: "stubbed",
      $process_person_profile: false, $geoip_disable: true
    });
  });

  it("drops automatic or unknown events", async () => {
    const { sanitizeEvent } = await import("../src/analytics");
    for (const event of ["$autocapture", "$pageview", "$snapshot", "unknown", "toString"]) {
      expect(sanitizeEvent({ uuid: "test-event", event, properties: { secret: "private" } })).toBeNull();
    }
  });
});
