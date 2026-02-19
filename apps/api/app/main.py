from fastapi import FastAPI

from app.config import settings
from app.logging import configure_logging
from app.routers.health import router as health_router

configure_logging()

app = FastAPI(title=settings.app_name)
app.include_router(health_router)
