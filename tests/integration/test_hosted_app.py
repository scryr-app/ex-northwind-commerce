"""Exercise the shipped frontend/API and real dependency connections over HTTP.

The sample uses an in-memory catalog and stubbed Stripe payments. These tests do
not claim that checkout persists an order or that Redis backs business flows.
"""

from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []
        self.has_root = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.has_root |= attrs.get("id") == "root"
        if tag == "script" and attrs.get("src"):
            self.assets.append((attrs["src"], "javascript"))
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.assets.append((attrs["href"], "text/css"))


def payload(product_id, quantity=1, **changes):
    result = {
        "accountId": "integration-test-account",
        "currency": "usd",
        "shippingSpeed": "standard",
        "lines": [{"productId": product_id, "quantity": quantity}],
    }
    result.update(changes)
    return result


def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"api": "ok"}


def test_real_dependency_health(client, dependency_status):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "api": "ok", "postgres": dependency_status, "redis": dependency_status
    }


def test_storefront_and_compiled_assets(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    page = AssetParser()
    page.feed(response.text)
    assert page.has_root
    assert {kind for _, kind in page.assets} == {"javascript", "text/css"}
    for path, content_type in page.assets:
        parsed = urlsplit(path)
        assert not parsed.netloc and not parsed.scheme
        assert path.startswith("/assets/")
        asset = client.get(path)
        assert asset.status_code == 200, path
        assert content_type in asset.headers["content-type"]
        assert asset.content
        if content_type == "javascript":
            assert "http://localhost:8000" not in asset.text


def test_catalog_contract(products):
    assert len({product["id"] for product in products}) == len(products)
    for product in products:
        assert {"id", "sku", "name", "category", "imageUrl", "unitPriceCents",
                "inventory", "leadTimeDays"} <= product.keys()
        assert product["unitPriceCents"] > 0
        assert product["inventory"] >= 0
        assert product["leadTimeDays"] >= 0


def test_catalog_to_checkout_flow(client, products):
    product = next(product for product in products if product["inventory"] >= 2)
    response = client.post("/checkout", json=payload(product["id"], 2))
    assert response.status_code == 200
    checkout = response.json()
    assert checkout["status"] == "stubbed"
    assert checkout["checkoutId"].startswith("chk_")
    assert checkout["paymentIntentId"].startswith("pi_stub_")
    assert checkout["clientSecret"].startswith(checkout["paymentIntentId"])
    assert 0 <= checkout["riskScore"] <= 100


def test_separate_checkouts_have_distinct_ids(client, products):
    request = payload(products[0]["id"])
    first = client.post("/checkout", json=request)
    second = client.post("/checkout", json=request)
    assert first.status_code == second.status_code == 200
    assert first.json()["checkoutId"] != second.json()["checkoutId"]
    assert first.json()["paymentIntentId"] != second.json()["paymentIntentId"]


def test_checkout_rejects_unknown_product(client):
    response = client.post("/checkout", json=payload("missing-product"))
    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


def test_checkout_rejects_insufficient_inventory(client, products):
    product = next(product for product in products if product["inventory"] < 250)
    response = client.post("/checkout", json=payload(product["id"], product["inventory"] + 1))
    assert response.status_code == 409
    assert "Insufficient inventory" in response.json()["detail"]


@pytest.mark.parametrize("quantity", [0, -1, 251])
def test_checkout_validates_quantity(client, products, quantity):
    response = client.post("/checkout", json=payload(products[0]["id"], quantity))
    assert response.status_code == 422
    assert any(error["loc"][-1] == "quantity" for error in response.json()["detail"])


@pytest.mark.parametrize("request_body, field", [
    ({"accountId": "integration-test-account", "lines": []}, "lines"),
    ({"lines": [{"productId": "chai-001", "quantity": 1}]}, "accountId"),
])
def test_checkout_requires_cart_and_account(client, request_body, field):
    response = client.post("/checkout", json=request_body)
    assert response.status_code == 422
    assert any(error["loc"][-1] == field for error in response.json()["detail"])


def test_cors_allows_configured_storefront(client):
    response = client.options("/checkout", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_rejects_untrusted_origin(client):
    response = client.options("/checkout", headers={
        "Origin": "https://untrusted.example",
        "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("path", ["/assets/missing.js", "/.env", "/%2e%2e/%2e%2e/README.md"])
def test_static_files_do_not_expose_private_or_missing_files(client, path):
    assert client.get(path).status_code == 404


def test_api_routes_take_precedence_over_static_mount(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/checkout" in response.json()["paths"]
    assert "/health/live" in response.json()["paths"]


def test_response_has_a_generated_request_id(client):
    response = client.get("/catalog", headers={"X-Request-ID": "untrusted-client-value"})
    assert response.status_code == 200
    assert len(response.headers["x-request-id"]) == 32
    assert response.headers["x-request-id"] != "untrusted-client-value"


def test_metrics_require_bearer_authentication(client):
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_metrics_cover_requests_checkout_and_latency(client, products):
    client.get("/catalog")
    client.post("/checkout", json=payload(products[0]["id"]))
    response = client.get("/metrics", headers={"Authorization": "Bearer integration-metrics-token"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "northwind_http_requests_total" in response.text
    assert "northwind_http_request_duration_seconds_bucket" in response.text
    assert 'northwind_checkout_attempts_total{outcome="accepted"}' in response.text
    assert "integration-metrics-token" not in response.text
