export type Product = {
  id: string;
  sku: string;
  name: string;
  category: string;
  imageUrl: string;
  unitPriceCents: number;
  inventory: number;
  leadTimeDays: number;
};

export type CartLine = {
  productId: string;
  quantity: number;
};

export type CheckoutResponse = {
  checkoutId: string;
  paymentIntentId: string;
  clientSecret: string;
  riskScore: number;
  status: "requires_payment_method" | "stubbed";
};

const fallbackProducts: Product[] = [
  {
    id: "chai-001",
    sku: "BEV-CHAI-48",
    name: "Chai Tea Master Case",
    category: "Beverages",
    imageUrl: "https://images.unsplash.com/photo-1564890369478-c89ca6d9cde9?auto=format&fit=crop&w=640&q=80",
    unitPriceCents: 18900,
    inventory: 128,
    leadTimeDays: 3
  },
  {
    id: "ikura-002",
    sku: "SEA-IKURA-24",
    name: "Ikura Cold Chain Pack",
    category: "Seafood",
    imageUrl: "https://images.unsplash.com/photo-1617196034796-73dfa7b1fd56?auto=format&fit=crop&w=640&q=80",
    unitPriceCents: 62400,
    inventory: 42,
    leadTimeDays: 2
  },
  {
    id: "tarte-003",
    sku: "CON-TARTE-36",
    name: "Tarte au Sucre Tray",
    category: "Confections",
    imageUrl: "https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=640&q=80",
    unitPriceCents: 27600,
    inventory: 75,
    leadTimeDays: 5
  }
];

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function listProducts(): Promise<Product[]> {
  try {
    const response = await fetch(`${apiUrl}/catalog`);
    if (!response.ok) {
      throw new Error(`Catalog failed with ${response.status}`);
    }
    return response.json();
  } catch {
    return fallbackProducts;
  }
}

export async function createCheckout(lines: CartLine[], turnstileToken = ""): Promise<CheckoutResponse> {
  const response = await fetch(`${apiUrl}/checkout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      accountId: "northwind-wholesale",
      currency: "usd",
      shippingSpeed: "expedited",
      lines,
      turnstileToken
    })
  });

  if (!response.ok) {
    throw new Error(`Checkout failed with ${response.status}`);
  }

  return response.json();
}
