"""Read-only public deployment checks; no checkout or database probes."""

import json
import os
import sys
import time
from http.client import HTTPException
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def check(base_url):
    url = urlsplit(base_url)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in ("", "/")
    ):
        raise ValueError(
            "UPTIME_URL must be an HTTPS origin without credentials, paths, or query parameters"
        )
    base_url = base_url.rstrip("/")
    for path in ("/health/live", "/", "/catalog"):
        request = Request(
            base_url + path, headers={"User-Agent": "northwind-uptime/1.0"}
        )
        with urlopen(request, timeout=90) as response:
            if response.status != 200:
                raise RuntimeError(f"{path} returned HTTP {response.status}")
            body = response.read(1_000_000).decode()
        if path == "/health/live" and json.loads(body) != {"api": "ok"}:
            raise RuntimeError("Unexpected liveness response")
        if path == "/" and '<div id="root">' not in body:
            raise RuntimeError("Storefront HTML is missing the application root")
        if path == "/catalog":
            products = json.loads(body)
            if (
                not isinstance(products, list)
                or not products
                or not all(
                    isinstance(p, dict) and "id" in p and "unitPriceCents" in p
                    for p in products
                )
            ):
                raise RuntimeError(
                    "Catalog response does not match the storefront contract"
                )


def main():
    url = os.environ.get("UPTIME_URL", "https://northwind-commerce.onrender.com")
    for attempt in range(3):
        try:
            check(url)
            print("Public liveness, storefront, and catalog checks passed.")
            return 0
        except (OSError, ValueError, RuntimeError, HTTPException) as error:
            print(f"Check {attempt + 1}/3 failed: {error}", file=sys.stderr)
            if attempt < 2:
                time.sleep(5)
    return 1


if __name__ == "__main__":
    sys.exit(main())
