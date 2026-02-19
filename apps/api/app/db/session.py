from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

database_url = settings.database_url

connect_args: dict = {}
engine_kwargs: dict = {"pool_pre_ping": True}

if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # If it's in-memory SQLite, force a single shared connection across sessions/tests
    if ":memory:" in database_url:
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
