import logging

import httpx

from northwind_api.config import Settings

logger = logging.getLogger(__name__)


def verify_turnstile(settings: Settings, token: str, remote_ip: str | None) -> bool:
    secret = settings.turnstile_secret_key.get_secret_value()
    if not secret:
        return True
    if not token:
        return False
    response = httpx.post(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data={"secret": secret, "response": token, "remoteip": remote_ip or ""},
        timeout=5,
    )
    response.raise_for_status()
    return response.json().get("success") is True


def send_order_email(settings: Settings, checkout_id: str, total_cents: int) -> None:
    api_key = settings.resend_api_key.get_secret_value()
    if not api_key or not settings.order_email_from or not settings.order_email_to:
        return
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": settings.order_email_from,
                "to": [settings.order_email_to],
                "subject": f"Northwind checkout {checkout_id}",
                "text": f"Checkout {checkout_id} created for ${total_cents / 100:.2f}.",
            },
            timeout=5,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("order_email_failed", extra={"checkout_id": checkout_id})
