import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.config import allowed_origins, settings
from app.observability import configure_logging, log_event, metrics_store, set_request_id
from app.routers.dispatch import router as dispatch_router
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.metrics import router as metrics_router
from app.routers.orders import router as orders_router
from app.routers.tracking import router as tracking_router
from app.services.store import seed_data

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Wingxtra Delivery API UI integration support endpoints",
)

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


@app.on_event("startup")
def startup_seed() -> None:
    configure_logging()
    if not settings.testing:
        seed_data()
