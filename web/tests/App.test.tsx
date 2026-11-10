// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";

const api = vi.hoisted(() => ({ listProducts: vi.fn(), createCheckout: vi.fn() }));
const analytics = vi.hoisted(() => ({ trackEvent: vi.fn() }));
vi.mock("../src/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../src/api")>()),
  ...api
}));
vi.mock("../src/analytics", () => analytics);
vi.mock("../src/Turnstile", () => ({
  Turnstile: ({ onToken }: { onToken: (token: string) => void }) => (
    <button type="button" onClick={() => onToken("captcha-token")}>Verify buyer</button>
  )
}));

const products = [
  {
    id: "chai-001", sku: "BEV-CHAI-48", name: "Chai Tea Master Case",
    category: "Beverages", imageUrl: "chai.jpg", unitPriceCents: 18900,
    inventory: 128, leadTimeDays: 3
  },
  {
    id: "ikura-002", sku: "SEA-IKURA-24", name: "Ikura Cold Chain Pack",
    category: "Seafood", imageUrl: "ikura.jpg", unitPriceCents: 62400,
    inventory: 42, leadTimeDays: 2
  }
];

beforeEach(() => {
  api.listProducts.mockResolvedValue(products);
  api.createCheckout.mockResolvedValue({
    checkoutId: "chk_test", paymentIntentId: "pi_test", clientSecret: "secret",
    riskScore: 86, status: "stubbed"
  });
  analytics.trackEvent.mockReset();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("storefront checkout", () => {
  it("loads the catalog and initializes the default cart", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Chai Tea Master Case" })).toBeTruthy();
    expect(screen.getByText("2 x $189")).toBeTruthy();
    expect(screen.getAllByText("$378").length).toBeGreaterThan(0);
    expect(analytics.trackEvent).toHaveBeenCalledWith("catalog_viewed", { product_count: 2 });
  });

  it("updates quantities and completes verified checkout", async () => {
    const user = userEvent.setup();
    render(<App />);
    const inputs = await screen.findAllByRole("spinbutton", { name: "Quantity" });
    await user.clear(inputs[1]);
    await user.type(inputs[1], "1");
    await user.click(screen.getByRole("button", { name: "Verify buyer" }));
    await user.click(screen.getByRole("button", { name: "Create payment intent" }));
    await waitFor(() => expect(api.createCheckout).toHaveBeenCalledWith([
      { productId: "chai-001", quantity: 2 },
      { productId: "ikura-002", quantity: 1 }
    ], "captcha-token"));
    expect(await screen.findByText("Risk score")).toBeTruthy();
    expect(screen.getByText("86")).toBeTruthy();
    expect(screen.getByText(/Payment intent pi_test is stubbed/)).toBeTruthy();
  });

  it("disables an empty cart and surfaces checkout failures", async () => {
    api.createCheckout.mockRejectedValue(new Error("Checkout failed with 503"));
    const user = userEvent.setup();
    render(<App />);
    const inputs = await screen.findAllByRole("spinbutton", { name: "Quantity" });
    fireEvent.change(inputs[0], { target: { value: "0" } });
    expect(screen.getByText("No cases selected.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Create payment intent" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(inputs[0], { target: { value: "1" } });
    await user.click(screen.getByRole("button", { name: "Create payment intent" }));
    expect(await screen.findByText("Checkout failed with 503")).toBeTruthy();
    expect(analytics.trackEvent).toHaveBeenCalledWith(
      "checkout_failed", { line_count: 1, quantity: 1, total_cents: 18900 }
    );
  });
});
