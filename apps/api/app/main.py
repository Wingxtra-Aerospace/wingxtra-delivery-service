from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import allowed_origins, settings
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
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

app.include_router(health_router)
app.include_router(orders_router)
app.include_router(jobs_router)
app.include_router(tracking_router)


@app.on_event("startup")
def startup_seed() -> None:
    seed_data()
