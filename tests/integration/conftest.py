"""HTTP integration fixtures: the application runs outside the test process."""

import time
from urllib.parse import urlsplit

import httpx
import pytest


def pytest_addoption(parser):
    group = parser.getgroup("northwind integration")
    group.addoption("--base-url", default="http://127.0.0.1:10000")
    group.addoption(
        "--dependency-state", choices=("healthy", "unavailable"), default="healthy"
    )


@pytest.fixture(scope="session")
def client(pytestconfig):
    base_url = pytestconfig.getoption("--base-url").rstrip("/")
    url = urlsplit(base_url)
    # These tests submit checkout requests; only target isolated local containers.
    if (url.scheme != "http" or url.hostname not in ("localhost", "127.0.0.1", "::1")
            or url.username or url.password or url.path or url.query or url.fragment):
        raise pytest.UsageError("--base-url must be a local HTTP origin for the stubbed test app")

    with httpx.Client(base_url=base_url, timeout=10, trust_env=False) as session:
        deadline = time.monotonic() + 60
        last_result = "no response"
        while time.monotonic() < deadline:
            try:
                response = session.get("/health/live")
                last_result = f"HTTP {response.status_code}: {response.text[:200]}"
                if response.status_code == 200 and response.json() == {"api": "ok"}:
                    break
            except (httpx.HTTPError, ValueError) as error:
                last_result = str(error)
            time.sleep(0.5)
        else:
            pytest.fail(f"Application did not become healthy at {base_url}: {last_result}")
        yield session


@pytest.fixture(scope="session")
def dependency_status(pytestconfig):
    return "ok" if pytestconfig.getoption("--dependency-state") == "healthy" else "unavailable"


@pytest.fixture(scope="session")
def products(client):
    response = client.get("/catalog")
    assert response.status_code == 200
    result = response.json()
    assert isinstance(result, list) and result
    return result
