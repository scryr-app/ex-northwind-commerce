import { useEffect, useMemo, useState } from "react";
import { CartLine, CheckoutResponse, Product, createCheckout, listProducts } from "./api";
import { cartTotalCents, formatCurrency, riskTone } from "./domain";
import { trackEvent } from "./analytics";

type QuantityMap = Record<string, number>;

export function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [quantities, setQuantities] = useState<QuantityMap>({});
  const [checkout, setCheckout] = useState<CheckoutResponse | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);

  useEffect(() => {
    let active = true;
    listProducts().then((items) => {
      if (!active) return;
      setProducts(items);
      setQuantities(Object.fromEntries(items.map((item) => [item.id, item.id === "chai-001" ? 2 : 0])));
      trackEvent("catalog_viewed", { product_count: items.length });
    });
    return () => { active = false; };
  }, []);

  const cartLines = useMemo(
    () =>
      products
        .map((product) => ({ product, quantity: quantities[product.id] ?? 0 }))
        .filter((line) => line.quantity > 0),
    [products, quantities]
  );

  const totalCents = cartTotalCents(
    cartLines.map((line) => ({
      unitPriceCents: line.product.unitPriceCents,
      quantity: line.quantity
    }))
  );

  function updateQuantity(productId: string, quantity: number) {
    setQuantities((current) => ({
      ...current,
      [productId]: Math.max(0, quantity)
    }));
    setCheckout(null);
    setCheckoutError(null);
    if (Number.isFinite(quantity)) {
      trackEvent("cart_updated", { product_id: productId, quantity: Math.max(0, quantity) });
    }
  }

  async function submitCheckout() {
    setIsCheckingOut(true);
    setCheckoutError(null);

    const summary = {
      line_count: cartLines.length,
      quantity: cartLines.reduce((total, line) => total + line.quantity, 0),
      total_cents: totalCents
    };
    trackEvent("checkout_started", summary);

    try {
      const lines: CartLine[] = cartLines.map((line) => ({
        productId: line.product.id,
        quantity: line.quantity
      }));
      const result = await createCheckout(lines);
      setCheckout(result);
      trackEvent("checkout_intent_created", {
        ...summary,
        payment_mode: result.status === "stubbed" ? "stubbed" : "stripe"
      });
    } catch (error) {
      trackEvent("checkout_failed", summary);
      setCheckoutError(error instanceof Error ? error.message : "Checkout failed");
    } finally {
      setIsCheckingOut(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="toolbar" aria-label="Storefront summary">
        <div>
          <p className="eyebrow">Northwind Commerce</p>
          <h1>Wholesale ordering for regional buyers</h1>
        </div>
        <div className="metrics">
          <div>
            <span>Open terms</span>
            <strong>Net 30</strong>
          </div>
          <div>
            <span>Fulfillment</span>
            <strong>97.8%</strong>
          </div>
          <div>
            <span>Cart value</span>
            <strong>{formatCurrency(totalCents)}</strong>
          </div>
        </div>
      </section>

      <section className="commerce-grid">
        <div className="catalog" aria-label="Product catalog">
          {products.map((product) => (
            <article className="product-card" key={product.id}>
              <img src={product.imageUrl} alt="" />
              <div className="product-card__body">
                <div>
                  <p>{product.category}</p>
                  <h2>{product.name}</h2>
                  <span>{product.sku}</span>
                </div>
                <dl>
                  <div>
                    <dt>Case price</dt>
                    <dd>{formatCurrency(product.unitPriceCents)}</dd>
                  </div>
                  <div>
                    <dt>Inventory</dt>
                    <dd>{product.inventory}</dd>
                  </div>
                  <div>
                    <dt>Lead time</dt>
                    <dd>{product.leadTimeDays} days</dd>
                  </div>
                </dl>
                <label>
                  Quantity
                  <input
                    min="0"
                    type="number"
                    value={quantities[product.id] ?? 0}
                    onChange={(event) => updateQuantity(product.id, Number(event.target.value))}
                  />
                </label>
              </div>
            </article>
          ))}
        </div>

        <aside className="checkout-panel" aria-label="Checkout">
          <div className="panel-header">
            <p className="eyebrow">Buyer cart</p>
            <h2>Purchase order preview</h2>
          </div>

          <div className="cart-lines">
            {cartLines.length === 0 ? (
              <p className="empty">No cases selected.</p>
            ) : (
              cartLines.map((line) => (
                <div className="cart-line" key={line.product.id}>
                  <span>{line.product.name}</span>
                  <strong>
                    {line.quantity} x {formatCurrency(line.product.unitPriceCents)}
                  </strong>
                </div>
              ))
            )}
          </div>

          <div className="total-row">
            <span>Estimated total</span>
            <strong>{formatCurrency(totalCents)}</strong>
          </div>

          <button disabled={cartLines.length === 0 || isCheckingOut} onClick={submitCheckout}>
            {isCheckingOut ? "Authorizing..." : "Create payment intent"}
          </button>

          {checkout ? (
            <div className={`risk-result risk-result--${riskTone(checkout.riskScore)}`}>
              <span>Risk score</span>
              <strong>{checkout.riskScore}</strong>
              <p>Payment intent {checkout.paymentIntentId} is {checkout.status}.</p>
            </div>
          ) : null}

          {checkoutError ? <p className="error">{checkoutError}</p> : null}
        </aside>
      </section>
    </main>
  );
}
