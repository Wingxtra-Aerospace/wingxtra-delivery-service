import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import Response

from app.config import allowed_origins, ensure_secure_runtime_settings, settings
from app.db.base import Base
from app.db.session import engine
from app.observability import log_event, metrics_store, set_request_id
from app.routers.dispatch import router as dispatch_router
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.metrics import router as metrics_router
from app.routers.orders import router as orders_router
from app.routers.tracking import router as tracking_router
from app.services.store import seed_data


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import app.models  # noqa: F401 (register all SQLAlchemy models)

    ensure_secure_runtime_settings()
    Base.metadata.create_all(bind=engine)
    if settings.app_mode == "demo":
        seed_data()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Wingxtra Delivery API UI integration support endpoints",
    lifespan=lifespan,
)


def custom_openapi():
    """
    Adds HTTP Bearer (JWT) auth to the OpenAPI schema so Swagger UI shows an
    'Authorize' button and automatically sends the Authorization: Bearer <token> header.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    components = openapi_schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }

    # Apply globally (endpoints that don't require auth will still work as coded,
    # but Swagger will send the header once you authorize.)
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    set_request_id(request_id)

    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start

    response.headers["X-Request-ID"] = request_id
    metrics_store.increment("http_requests_total")
    metrics_store.observe("http_request_duration_seconds", elapsed)
    log_event("http_request", order_id=request.path_params.get("order_id"))
    return response


app.include_router(health_router)
app.include_router(orders_router)
app.include_router(dispatch_router)
app.include_router(jobs_router)
app.include_router(tracking_router)
app.include_router(metrics_router)
