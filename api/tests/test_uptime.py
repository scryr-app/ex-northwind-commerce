import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

spec = importlib.util.spec_from_file_location(
    "northwind_uptime", Path(__file__).parents[2] / "scripts/check-uptime.py"
)
uptime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uptime)


class Response(io.BytesIO):
    status = 200


def test_uptime_validates_all_public_surfaces(monkeypatch):
    paths = []
    responses = [
        json.dumps({"api": "ok"}),
        '<div id="root"></div>',
        json.dumps([{"id": "chai", "unitPriceCents": 100}]),
    ]

    def fetch(request, timeout):
        paths.append(request.full_url)
        return Response(responses.pop(0).encode())

    monkeypatch.setattr(uptime, "urlopen", fetch)
    uptime.check("https://example.onrender.com/")
    assert paths == [
        "https://example.onrender.com/health/live",
        "https://example.onrender.com/",
        "https://example.onrender.com/catalog",
    ]


def test_uptime_fails_on_render_routing_errors(monkeypatch):
    def fetch(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(uptime, "urlopen", fetch)
    with pytest.raises(HTTPError):
        uptime.check("https://example.onrender.com")


def test_uptime_does_not_accept_generic_200_error_pages(monkeypatch):
    monkeypatch.setattr(
        uptime, "urlopen", lambda *args, **kwargs: Response(b"Not Found")
    )
    with pytest.raises(ValueError):
        uptime.check("https://example.onrender.com")
