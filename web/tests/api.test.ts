import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
});

afterEach(() => vi.unstubAllGlobals());

describe("catalog API", () => {
  it("returns products from the configured API", async () => {
    vi.stubEnv("VITE_API_URL", "https://api.example.test");
    const products = [{ id: "test-product", sku: "TEST-1" }];
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => products });
    vi.stubGlobal("fetch", fetch);
    const { listProducts } = await import("../src/api");
    await expect(listProducts()).resolves.toEqual(products);
    expect(fetch).toHaveBeenCalledWith("https://api.example.test/catalog");
  });

  it.each([
    ["an HTTP error", vi.fn().mockResolvedValue({ ok: false, status: 503 })],
    ["a network error", vi.fn().mockRejectedValue(new Error("offline"))]
  ])("uses the demo catalog after %s", async (_case, fetch) => {
    vi.stubGlobal("fetch", fetch);
    const { listProducts } = await import("../src/api");
    const products = await listProducts();
    expect(products.map((product) => product.id)).toEqual([
      "chai-001", "ikura-002", "tarte-003"
    ]);
  });
});

describe("checkout API", () => {
  it("submits the checkout and verification contract", async () => {
    vi.stubEnv("VITE_API_URL", "https://api.example.test");
    const checkout = {
      checkoutId: "chk_test", paymentIntentId: "pi_test", clientSecret: "secret",
      riskScore: 28, status: "stubbed"
    };
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => checkout });
    vi.stubGlobal("fetch", fetch);
    const { createCheckout } = await import("../src/api");
    await expect(createCheckout([{ productId: "chai-001", quantity: 2 }], "captcha-token"))
      .resolves.toEqual(checkout);
    expect(fetch).toHaveBeenCalledWith("https://api.example.test/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        accountId: "northwind-wholesale", currency: "usd", shippingSpeed: "expedited",
        lines: [{ productId: "chai-001", quantity: 2 }], turnstileToken: "captcha-token"
      })
    });
  });

  it("reports the response status when checkout is rejected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409 }));
    const { createCheckout } = await import("../src/api");
    await expect(createCheckout([{ productId: "chai-001", quantity: 999 }]))
      .rejects.toThrow("Checkout failed with 409");
  });
});
