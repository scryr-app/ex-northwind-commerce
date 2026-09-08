from contextlib import asynccontextmanager
from secrets import compare_digest
from uuid import uuid4

import psycopg
import redis
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from northwind_api.catalog import CATALOG, get_product
from northwind_api.config import get_settings
from northwind_api.observability import RequestTelemetryMiddleware, Telemetry
from northwind_api.risk import score_checkout
from northwind_api.schemas import CheckoutRequest, CheckoutResponse, ProductResponse
from northwind_api.stripe_client import create_payment_intent

settings = get_settings()
telemetry = Telemetry(settings)


@asynccontextmanager
async def lifespan(app):
    telemetry.start()
    try:
        yield
    finally:
        telemetry.close()


app = FastAPI(
    lifespan=lifespan,
    title="Northwind Commerce API",
    version="0.1.0",
    summary="Catalog, checkout, payment-risk, and platform-health flows.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(RequestTelemetryMiddleware, telemetry=telemetry)


@app.get("/metrics", include_in_schema=False)
def metrics(request: Request):
    token = settings.metrics_token.get_secret_value()
    if not token:
        raise HTTPException(status_code=404)
    supplied = request.headers.get("authorization", "")
    if not compare_digest(supplied.encode(), f"Bearer {token}".encode()):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})
    return Response(
        generate_latest(telemetry.registry),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


@app.get("/health/live")
def liveness() -> dict[str, str]:
    # Platform probes must not wake optional databases or consume their quotas.
    return {"api": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    status = {"api": "ok", "postgres": "unavailable", "redis": "unavailable"}

    try:
        with psycopg.connect(settings.database_url, connect_timeout=1) as connection:
            with connection.cursor() as cursor:
                cursor.execute("select 1")
                cursor.fetchone()
                status["postgres"] = "ok"
    except Exception:
        status["postgres"] = "unavailable"

    try:
        client = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        if client.ping():
            status["redis"] = "ok"
    except Exception:
        status["redis"] = "unavailable"

    return status


@app.get("/catalog", response_model=list[ProductResponse], response_model_by_alias=True)
def catalog() -> list[ProductResponse]:
    return [ProductResponse.model_validate(product.__dict__) for product in CATALOG]


@app.post("/checkout", response_model=CheckoutResponse, response_model_by_alias=True)
def checkout(request: CheckoutRequest) -> CheckoutResponse:
    selected_products = []
    order_total_cents = 0
    total_quantity = 0

    for line in request.lines:
        product = get_product(line.product_id)
        if product is None:
            raise HTTPException(
                status_code=404, detail=f"Product {line.product_id} was not found"
            )
        if line.quantity > product.inventory:
            raise HTTPException(
                status_code=409, detail=f"Insufficient inventory for {product.sku}"
            )

        selected_products.append(product)
        total_quantity += line.quantity
        order_total_cents += product.unit_price_cents * line.quantity

    with telemetry.tracer.start_as_current_span(
        "checkout.risk", record_exception=False, set_status_on_exception=False
    ):
        risk_score = score_checkout(
            order_total_cents=order_total_cents,
            total_quantity=total_quantity,
            shipping_speed=request.shipping_speed,
            products=selected_products,
        )

    checkout_id = f"chk_{uuid4().hex[:12]}"
    with telemetry.tracer.start_as_current_span(
        "checkout.payment", record_exception=False, set_status_on_exception=False
    ):
        payment = create_payment_intent(
            stripe_secret_key=settings.stripe_secret_key,
            amount_cents=order_total_cents,
            currency=request.currency,
            metadata={
                "checkout_id": checkout_id,
                "account_id": request.account_id,
                "risk_score": str(risk_score),
            },
        )

    return CheckoutResponse(
        checkout_id=checkout_id,
        payment_intent_id=payment["payment_intent_id"],
        client_secret=payment["client_secret"],
        risk_score=risk_score,
        status=payment["status"],
    )


# Register last so API routes take precedence over the storefront.
# Local Vite development continues to use its separate dev server.
if settings.static_dir:
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="web")
