from fastapi.testclient import TestClient
from pydantic import SecretStr

from northwind_api import main


app = main.app
client = TestClient(app)


def test_liveness_does_not_contact_dependencies(monkeypatch):
    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Liveness must not contact Postgres or Redis")

    monkeypatch.setattr("northwind_api.main.psycopg.connect", unexpected_connection)
    monkeypatch.setattr("northwind_api.main.redis.from_url", unexpected_connection)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"api": "ok"}


def test_catalog_returns_products():
    response = client.get("/catalog")

    assert response.status_code == 200
    products = response.json()
    assert products[0]["sku"] == "BEV-CHAI-48"
    assert "unitPriceCents" in products[0]


def test_sentry_test_route_is_disabled_without_token(monkeypatch):
    monkeypatch.setattr(main.settings, "sentry_test_token", SecretStr(""))
    assert client.post("/__sentry-test").status_code == 404


def test_sentry_test_route_requires_token_and_raises(monkeypatch):
    monkeypatch.setattr(main.settings, "sentry_test_token", SecretStr("test-token"))
    assert client.post("/__sentry-test").status_code == 401

    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/__sentry-test", headers={"Authorization": "Bearer test-token"}
        )
    assert response.status_code == 500


def test_checkout_creates_stubbed_payment_intent():
    response = client.post(
        "/checkout",
        json={
            "accountId": "northwind-wholesale",
            "currency": "usd",
            "shippingSpeed": "expedited",
            "lines": [{"productId": "chai-001", "quantity": 2}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["paymentIntentId"].startswith("pi_stub_")
    assert body["status"] == "stubbed"
    assert body["riskScore"] > 0


def test_checkout_rejects_unknown_product():
    response = client.post(
        "/checkout",
        json={
            "accountId": "northwind-wholesale",
            "lines": [{"productId": "missing", "quantity": 1}],
        },
    )

    assert response.status_code == 404


def test_checkout_rejects_failed_turnstile(monkeypatch):
    monkeypatch.setattr("northwind_api.main.verify_turnstile", lambda *_: False)

    response = client.post(
        "/checkout",
        json={
            "accountId": "northwind-wholesale",
            "lines": [{"productId": "chai-001", "quantity": 1}],
            "turnstileToken": "invalid",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Checkout verification failed"}
