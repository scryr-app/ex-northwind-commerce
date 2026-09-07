#!/usr/bin/env sh
set -eu

API_URL="${API_URL:-http://localhost:8000}"
API_URL="${API_URL%/}"

# Allow time for container startup and Render's free-instance cold start.
curl -fsS --retry 12 --retry-all-errors --retry-delay 5 --max-time 90 \
  "$API_URL/health/live" >/dev/null
curl -fsS --max-time 30 "$API_URL/catalog" >/dev/null
curl -fsS \
  --max-time 30 \
  -H "Content-Type: application/json" \
  -d '{"accountId":"northwind-wholesale","currency":"usd","shippingSpeed":"expedited","lines":[{"productId":"chai-001","quantity":2}]}' \
  "$API_URL/checkout" >/dev/null

echo "Smoke test passed for $API_URL"
