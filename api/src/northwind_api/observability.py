"""Bounded request telemetry; cloud export is opt-in via OTLP credentials."""

import json
import logging
import random
import re
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

from opentelemetry import trace
from opentelemetry._logs import SeverityNumber
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import CollectorRegistry, Counter, Histogram

from northwind_api.config import Settings

BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
ROUTES = {"/", "/catalog", "/checkout"}
EXCLUDED = {"/health", "/health/live", "/metrics", "/docs", "/redoc", "/openapi.json"}
METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}


class Telemetry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "northwind_http_requests_total",
            "HTTP requests",
            ["method", "route", "status_code"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "northwind_http_request_duration_seconds",
            "HTTP request duration",
            ["method", "route"],
            buckets=BUCKETS,
            registry=self.registry,
        )
        self.checkouts = Counter(
            "northwind_checkout_attempts_total",
            "Checkout results",
            ["outcome"],
            registry=self.registry,
        )
        # Keep handlers isolated across application/test instances.
        self.logger = logging.Logger("northwind.requests", level=logging.INFO)  # noqa: LOG001
        self.logger.addHandler(logging.StreamHandler(sys.stdout))
        self.tracer_provider = None
        self.meter_provider = None
        self.log_provider = None
        self.tracer = trace.NoOpTracer()
        self.cloud_logger = None
        self.cloud_requests = self.cloud_duration = self.cloud_checkouts = None

    def start(self):
        endpoint = self.settings.otel_exporter_otlp_endpoint
        if not endpoint:
            return
        resource = Resource.create(
            {
                "service.name": "northwind-api",
                "service.instance.id": self.settings.render_instance_id or uuid4().hex,
                "service.version": self.settings.render_git_commit or "0.1.0",
                "deployment.environment.name": self.settings.app_env,
            }
        )
        options = {"headers": self.settings.otlp_headers, "timeout": 3}
        self.tracer_provider = TracerProvider(
            resource=resource,
            sampler=TraceIdRatioBased(self.settings.otel_trace_sample_ratio),
        )
        self.tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=endpoint + "/v1/traces", **options),
                max_queue_size=256,
                max_export_batch_size=64,
            )
        )
        self.tracer = self.tracer_provider.get_tracer("northwind.http")
        self.log_provider = LoggerProvider(resource=resource)
        self.log_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                OTLPLogExporter(endpoint=endpoint + "/v1/logs", **options),
                max_queue_size=256,
                max_export_batch_size=64,
            )
        )
        self.cloud_logger = self.log_provider.get_logger("northwind.requests")
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint + "/v1/metrics", **options),
            export_interval_millis=self.settings.otel_metric_export_interval * 1000,
            export_timeout_millis=5000,
        )
        self.meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[reader],
            views=[
                View(
                    instrument_name="northwind_http_request_duration_seconds",
                    aggregation=ExplicitBucketHistogramAggregation(BUCKETS),
                )
            ],
        )
        meter = self.meter_provider.get_meter("northwind.http")
        self.cloud_requests = meter.create_counter("northwind_http_requests_total")
        self.cloud_duration = meter.create_histogram(
            "northwind_http_request_duration_seconds", unit="s"
        )
        self.cloud_checkouts = meter.create_counter("northwind_checkout_attempts_total")

    def close(self):
        for provider in (self.meter_provider, self.log_provider, self.tracer_provider):
            if provider:
                provider.shutdown()

    def record(self, method, route, status, duration, request_id, error_type=None):
        labels = {"method": method, "route": route, "status_code": str(status)}
        self.requests.labels(**labels).inc()
        self.duration.labels(method=method, route=route).observe(duration)
        if self.cloud_requests:
            self.cloud_requests.add(1, labels)
            self.cloud_duration.record(duration, {"method": method, "route": route})
        if route == "/checkout" and method == "POST":
            outcome = (
                "accepted" if status < 400 else "rejected" if status < 500 else "error"
            )
            self.checkouts.labels(outcome=outcome).inc()
            if self.cloud_checkouts:
                self.cloud_checkouts.add(1, {"outcome": outcome})
        if status < 400 and random.random() >= self.settings.request_log_sample_ratio:
            return
        fields = {
            "event": "http.request",
            "service": "northwind-api",
            "environment": self.settings.app_env,
            "version": self.settings.render_git_commit or "0.1.0",
            "method": method,
            "route": route,
            "status_code": status,
            "duration_ms": round(duration * 1000, 2),
            "request_id": request_id,
        }
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            fields["trace_id"] = format(context.trace_id, "032x")
        if error_type:
            fields["error_type"] = error_type
        self.logger.info(
            json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), **fields})
        )
        if self.cloud_logger:
            self.cloud_logger.emit(
                body="http.request",
                attributes=fields,
                severity_number=SeverityNumber.ERROR
                if status >= 500
                else SeverityNumber.INFO,
            )


class RequestTelemetryMiddleware:
    def __init__(self, app, telemetry: Telemetry):
        self.app = app
        self.telemetry = telemetry

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        if path in EXCLUDED or path.startswith("/assets/"):
            return await self.app(scope, receive, send)
        route = path if path in ROUTES else "unmatched"
        method = scope["method"] if scope["method"] in METHODS else "OTHER"
        request_id = uuid4().hex
        status = 500
        error_type = None
        start = time.perf_counter()
        # Only trace context is propagated; never collect request headers or baggage.
        carrier = {}
        for key, value in scope.get("headers", []):
            if key == b"traceparent" and re.fullmatch(
                rb"00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}", value
            ):
                carrier["traceparent"] = value.decode("ascii")
        context = TraceContextTextMapPropagator().extract(carrier)
        with self.telemetry.tracer.start_as_current_span(
            f"{method} {route}",
            context=context,
            kind=trace.SpanKind.SERVER,
            attributes={"http.request.method": method, "http.route": route},
            record_exception=False,
            set_status_on_exception=False,
        ) as span:

            async def capture(message):
                nonlocal status
                if message["type"] == "http.response.start":
                    status = message["status"]
                    message = {
                        **message,
                        "headers": [
                            *message.get("headers", []),
                            (b"x-request-id", request_id.encode()),
                        ],
                    }
                await send(message)

            try:
                await self.app(scope, receive, capture)
            except Exception as error:
                status = 500
                error_type = type(error).__name__
                raise
            finally:
                span.set_attribute("http.response.status_code", status)
                if status >= 500:
                    span.set_status(trace.StatusCode.ERROR)
                self.telemetry.record(
                    method,
                    route,
                    status,
                    time.perf_counter() - start,
                    request_id,
                    error_type,
                )
