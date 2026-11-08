from pydantic import BaseModel, Field


class ProductResponse(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    image_url: str = Field(serialization_alias="imageUrl")
    unit_price_cents: int = Field(serialization_alias="unitPriceCents")
    inventory: int
    lead_time_days: int = Field(serialization_alias="leadTimeDays")

    model_config = {"populate_by_name": True}


class CheckoutLine(BaseModel):
    product_id: str = Field(validation_alias="productId")
    quantity: int = Field(gt=0, le=250)


class CheckoutRequest(BaseModel):
    account_id: str = Field(validation_alias="accountId")
    currency: str = "usd"
    shipping_speed: str = Field("standard", validation_alias="shippingSpeed")
    lines: list[CheckoutLine] = Field(min_length=1)
    turnstile_token: str = Field("", validation_alias="turnstileToken", max_length=4096)


class CheckoutResponse(BaseModel):
    checkout_id: str = Field(serialization_alias="checkoutId")
    payment_intent_id: str = Field(serialization_alias="paymentIntentId")
    client_secret: str = Field(serialization_alias="clientSecret")
    risk_score: int = Field(serialization_alias="riskScore")
    status: str

    model_config = {"populate_by_name": True}
