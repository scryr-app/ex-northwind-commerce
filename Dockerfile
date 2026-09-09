FROM node:22-alpine AS web
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ENV VITE_API_URL=""
# Public browser ingestion configuration only; never pass personal API keys here.
ARG VITE_POSTHOG_PROJECT_TOKEN=""
ARG VITE_POSTHOG_HOST="https://us.i.posthog.com"
ARG VITE_POSTHOG_ENVIRONMENT="local"
RUN npm run build

FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /usr/local/bin/uv
WORKDIR /app/api
COPY api/pyproject.toml api/uv.lock ./
COPY api/src ./src
RUN uv sync --locked --no-dev --no-editable --no-cache
COPY --from=web /build/web/dist /app/web/dist
ENV PATH="/app/api/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STATIC_DIR=/app/web/dist \
    PORT=10000
RUN useradd --create-home --uid 10001 northwind
USER northwind
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn northwind_api.main:app --no-access-log --host 0.0.0.0 --port ${PORT:-10000}"]
