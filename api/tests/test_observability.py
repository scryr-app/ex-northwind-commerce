import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from northwind_api import main
from northwind_api.config import Settings
from northwind_api.observability import RequestTelemetryMiddleware, Telemetry
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from pydantic import SecretStr, ValidationError


def make_telemetry(**changes):
    defaults = {
        "_env_file": None,
        "otel_exporter_otlp_endpoint": None,
        "request_log_sample_ratio": 1,
        "otel_trace_sample_ratio": 1,
    }
    defaults.update(changes)
    telemetry = Telemetry(Settings(**defaults))
    output = io.StringIO()
    telemetry.logger.handlers[0].setStream(output)
    return telemetry, output


def test_request_telemetry_is_bounded_and_omits_sensitive_data():
    telemetry, output = make_telemetry()
    app = FastAPI()
    app.add_middleware(RequestTelemetryMiddleware, telemetry=telemetry)
    with TestClient(app) as client:
        for path in ("/customer/alice", "/customer/bob"):
            response = client.post(
                path + "?token=SECRET",
                json={"password": "SECRET"},
                headers={"Authorization": "Bearer SECRET", "X-Request-ID": "SECRET"},
            )
            assert response.status_code == 404
            assert len(response.headers["x-request-id"]) == 32
        client.get("/health/live")
        client.get("/assets/not-found.js")
    assert (
        telemetry.registry.get_sample_value(
            "northwind_http_requests_total",
            {"method": "POST", "route": "unmatched", "status_code": "404"},
        )
        == 2
    )
    text = output.getvalue()
    assert "SECRET" not in text and "alice" not in text and "bob" not in text
    logs = [json.loads(line) for line in text.splitlines()]
    assert len(logs) == 2
    assert logs[0]["request_id"] != logs[1]["request_id"]
    assert all(log["route"] == "unmatched" for log in logs)


def test_metrics_endpoint_is_protected_and_disabled_without_token(monkeypatch):
    monkeypatch.setattr(main.settings, "otel_exporter_otlp_endpoint", None)
    with TestClient(main.app) as client:
        monkeypatch.setattr(main.settings, "metrics_token", SecretStr(""))
        assert client.get("/metrics").status_code == 404
        monkeypatch.setattr(
            main.settings, "metrics_token", SecretStr("private-test-token")
        )
        assert client.get("/metrics").status_code == 401
        assert (
            client.get(
                "/metrics", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        client.get("/catalog")
        response = client.get(
            "/metrics", headers={"Authorization": "Bearer private-test-token"}
        )
        assert response.status_code == 200
        assert "northwind_http_requests_total" in response.text
        assert "private-test-token" not in response.text


def test_unhandled_errors_are_counted_without_exporting_exception_messages():
    telemetry, output = make_telemetry()
    app = FastAPI()
    app.add_middleware(RequestTelemetryMiddleware, telemetry=telemetry)

    @app.get("/checkout")
    def fail():
        raise RuntimeError("private database password")

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/checkout").status_code == 500
    log = json.loads(output.getvalue())
    assert log["status_code"] == 500 and log["error_type"] == "RuntimeError"
    assert "private database password" not in output.getvalue()


def test_cloud_export_is_disabled_by_default():
    telemetry, _ = make_telemetry()
    telemetry.start()
    assert telemetry.tracer_provider is None
    assert telemetry.meter_provider is None
    assert telemetry.log_provider is None
    telemetry.close()


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/otlp",
        "https://user:password@example.com",
        "https://example.com?token=secret",
    ],
)
def test_otlp_rejects_insecure_or_embedded_credentials(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, otel_exporter_otlp_endpoint=url)


def test_all_signals_are_exported_via_otlp_with_authentication():
    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(
                (
                    self.path,
                    self.headers.get("Authorization"),
                    self.rfile.read(int(self.headers["Content-Length"])),
                )
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    telemetry, output = make_telemetry(
        otel_exporter_otlp_endpoint=f"http://127.0.0.1:{server.server_port}/otlp",
        otel_exporter_otlp_headers="Authorization=Basic%20test-token",
    )
    try:
        telemetry.start()
        app = FastAPI()
        app.add_middleware(RequestTelemetryMiddleware, telemetry=telemetry)

        @app.get("/catalog")
        def catalog():
            return []

        with TestClient(app) as client:
            assert client.get("/catalog?password=PRIVATE").status_code == 200
        assert telemetry.tracer_provider.force_flush()
        assert telemetry.log_provider.force_flush()
        assert telemetry.meter_provider.force_flush()
        decoded = {}
        types = {
            "/otlp/v1/traces": ExportTraceServiceRequest,
            "/otlp/v1/logs": ExportLogsServiceRequest,
            "/otlp/v1/metrics": ExportMetricsServiceRequest,
        }
        for path, auth, body in received:
            assert auth == "Basic test-token"
            assert b"PRIVATE" not in body
            decoded[path] = types[path].FromString(body)
        assert set(decoded) == set(types)
        spans = decoded["/otlp/v1/traces"].resource_spans[0].scope_spans[0].spans
        assert spans[0].name == "GET /catalog"
        logs = decoded["/otlp/v1/logs"].resource_logs[0].scope_logs[0].log_records
        assert logs[0].trace_id == spans[0].trace_id
        metrics = (
            decoded["/otlp/v1/metrics"].resource_metrics[0].scope_metrics[0].metrics
        )
        assert {metric.name for metric in metrics} >= {
            "northwind_http_requests_total",
            "northwind_http_request_duration_seconds",
        }
        assert "PRIVATE" not in output.getvalue()
    finally:
        telemetry.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_requests_succeed_when_otlp_receiver_is_unreachable():
    telemetry, _ = make_telemetry(otel_exporter_otlp_endpoint="http://127.0.0.1:1/otlp")
    try:
        telemetry.start()
        app = FastAPI()
        app.add_middleware(RequestTelemetryMiddleware, telemetry=telemetry)

        @app.get("/catalog")
        def catalog():
            return []

        with TestClient(app) as client:
            assert client.get("/catalog").status_code == 200
        # Force an actual failed delivery; it must not disable the application.
        telemetry.tracer_provider.force_flush(timeout_millis=5000)
        with TestClient(app) as client:
            assert client.get("/catalog").status_code == 200
    finally:
        telemetry.close()
