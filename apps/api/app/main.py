from fastapi import FastAPI

from app.config import settings
from app.logging import configure_logging
from app.routers.dispatch import router as dispatch_router
from app.routers.health import router as health_router
from app.routers.orders import router as orders_router
from app.routers.tracking import router as tracking_router

configure_logging()

app = FastAPI(title=settings.app_name)
app.include_router(health_router)
app.include_router(orders_router)
app.include_router(dispatch_router)
app.include_router(tracking_router)
