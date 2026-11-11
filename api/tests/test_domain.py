import pytest
from pydantic import ValidationError

from northwind_api.catalog import CATALOG, get_product
from northwind_api.config import Settings
from northwind_api.risk import score_checkout
from northwind_api.schemas import CheckoutRequest, ProductResponse
from northwind_api.stripe_client import create_payment_intent


def test_catalog_lookup_and_serialization_contract():
    product = get_product("chai-001")
    assert product is CATALOG[0]
    assert get_product("missing") is None
    assert ProductResponse.model_validate(product.__dict__).model_dump(by_alias=True) == {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "category": product.category,
        "imageUrl": product.image_url,
        "unitPriceCents": product.unit_price_cents,
        "inventory": product.inventory,
        "leadTimeDays": product.lead_time_days,
    }


@pytest.mark.parametrize(
    ("total", "quantity", "shipping", "products", "expected"),
    [
        (100_000, 12, "standard", [], 12),
        (100_001, 13, "standard", [], 58),
        (250_001, 1, "standard", [], 64),
        (1, 1, "expedited", [CATALOG[1]], 36),
        (999_999, 99, "expedited", [CATALOG[1]], 100),
    ],
)
def test_checkout_risk_rules(total, quantity, shipping, products, expected):
    assert score_checkout(
        order_total_cents=total,
        total_quantity=quantity,
        shipping_speed=shipping,
        products=products,
    ) == expected


@pytest.mark.parametrize("quantity", [0, -1, 251])
def test_checkout_schema_rejects_invalid_quantities(quantity):
    with pytest.raises(ValidationError):
        CheckoutRequest.model_validate(
            {
                "accountId": "buyer",
                "lines": [{"productId": "chai-001", "quantity": quantity}],
            }
        )


def test_stubbed_payment_intent_is_unique_and_does_not_call_stripe(monkeypatch):
    called = False

    def unexpected_create(**kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "northwind_api.stripe_client.stripe.PaymentIntent.create", unexpected_create
    )
    first = create_payment_intent(
        stripe_secret_key="sk_test_stub", amount_cents=100, currency="usd", metadata={}
    )
    second = create_payment_intent(
        stripe_secret_key="", amount_cents=100, currency="usd", metadata={}
    )
    assert not called
    assert first["status"] == second["status"] == "stubbed"
    assert first["payment_intent_id"] != second["payment_intent_id"]
    assert first["client_secret"].startswith(first["payment_intent_id"])


def test_live_payment_intent_forwards_provider_contract(monkeypatch):
    intent = {
        "id": "pi_live",
        "client_secret": "secret_live",
        "status": "requires_payment_method",
    }
    received = {}

    def create(**kwargs):
        received.update(kwargs)
        return intent

    monkeypatch.setattr(
        "northwind_api.stripe_client.stripe.PaymentIntent.create", create
    )
    result = create_payment_intent(
        stripe_secret_key="sk_test_live",
        amount_cents=4242,
        currency="eur",
        metadata={"checkout_id": "chk_test"},
    )
    assert result == {
        "payment_intent_id": "pi_live",
        "client_secret": "secret_live",
        "status": "requires_payment_method",
    }
    assert received == {
        "amount": 4242,
        "currency": "eur",
        "automatic_payment_methods": {"enabled": True},
        "metadata": {"checkout_id": "chk_test"},
    }


def test_settings_parse_origins_and_headers():
    settings = Settings(
        _env_file=None,
        cors_origins=" https://one.test, ,https://two.test ",
        otel_exporter_otlp_headers="Authorization=Basic%20token,X-Tenant=northwind",
    )
    assert settings.allowed_origins == ["https://one.test", "https://two.test"]
    assert settings.otlp_headers == {
        "Authorization": "Basic token",
        "X-Tenant": "northwind",
    }


@pytest.mark.parametrize("headers", ["missing-separator", "=value", "key=line%0Abreak"])
def test_settings_reject_invalid_otlp_headers(headers):
    settings = Settings(_env_file=None, otel_exporter_otlp_headers=headers)
    with pytest.raises(ValueError):
        settings.otlp_headers
