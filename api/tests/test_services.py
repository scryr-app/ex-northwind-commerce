from pydantic import SecretStr

from northwind_api.config import Settings
from northwind_api.services import send_order_email, verify_turnstile


def settings(**changes):
    return Settings(_env_file=None, **changes)


def test_turnstile_is_optional_without_secret(monkeypatch):
    monkeypatch.setattr(
        "northwind_api.services.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected HTTP")),
    )
    assert verify_turnstile(settings(), "", "127.0.0.1") is True


def test_turnstile_requires_token_when_configured():
    assert verify_turnstile(
        settings(turnstile_secret_key=SecretStr("secret")), "", None
    ) is False


def test_turnstile_forwards_verification_contract(monkeypatch):
    received = {}

    class Response:
        def raise_for_status(self):
            received["checked"] = True

        def json(self):
            return {"success": True}

    def post(url, **kwargs):
        received.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr("northwind_api.services.httpx.post", post)
    assert verify_turnstile(
        settings(turnstile_secret_key=SecretStr("secret")), "token", "192.0.2.1"
    ) is True
    assert received == {
        "url": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        "data": {"secret": "secret", "response": "token", "remoteip": "192.0.2.1"},
        "timeout": 5,
        "checked": True,
    }


def test_order_email_is_optional_without_complete_configuration(monkeypatch):
    monkeypatch.setattr(
        "northwind_api.services.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected HTTP")),
    )
    send_order_email(settings(resend_api_key=SecretStr("key")), "chk_test", 1234)


def test_order_email_sends_expected_payload_and_swallows_provider_errors(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "northwind_api.services.httpx.post",
        lambda *args, **kwargs: calls.append((args, kwargs)) or Response(),
    )
    configured = settings(
        resend_api_key=SecretStr("key"),
        order_email_from="orders@example.test",
        order_email_to="buyer@example.test",
    )
    send_order_email(configured, "chk_test", 1234)
    assert calls[0][1]["headers"] == {"Authorization": "Bearer key"}
    assert calls[0][1]["json"]["text"] == "Checkout chk_test created for $12.34."

    monkeypatch.setattr(
        "northwind_api.services.httpx.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    send_order_email(configured, "chk_test", 1234)
