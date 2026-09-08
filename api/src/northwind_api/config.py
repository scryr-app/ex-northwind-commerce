from functools import lru_cache
from urllib.parse import unquote, urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "postgresql://northwind:northwind@localhost:5432/northwind"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173"
    stripe_secret_key: str = "sk_test_stub"
    static_dir: str | None = None
    metrics_token: SecretStr = SecretStr("")
    render_git_commit: str = ""
    render_instance_id: str = ""
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: SecretStr = SecretStr("")
    otel_trace_sample_ratio: float = Field(default=0.1, ge=0, le=1)
    request_log_sample_ratio: float = Field(default=0.1, ge=0, le=1)
    otel_metric_export_interval: int = Field(default=60, ge=60)

    @field_validator("otel_exporter_otlp_endpoint")
    @classmethod
    def validate_endpoint(cls, value):
        if not value:
            return None
        url = urlsplit(value)
        local = url.scheme == "http" and url.hostname in (
            "localhost",
            "127.0.0.1",
            "::1",
        )
        if (
            not url.hostname
            or (url.scheme != "https" and not local)
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "OTLP endpoint must use HTTPS (HTTP allowed only on loopback), without credentials or query parameters"
            )
        return value.rstrip("/")

    @property
    def otlp_headers(self) -> dict[str, str]:
        headers = {}
        for item in self.otel_exporter_otlp_headers.get_secret_value().split(","):
            if not item.strip():
                continue
            key, separator, value = item.partition("=")
            key, value = key.strip(), unquote(value.strip())
            if not separator or not key or any(c in key + value for c in "\r\n"):
                raise ValueError("OTLP headers must be comma-separated key=value pairs")
            headers[key] = value
        return headers

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
