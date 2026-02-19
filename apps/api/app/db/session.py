from __future__ import annotations

from app.config import settings

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


is_sqlite = settings.database_url.startswith("sqlite")
is_sqlite_memory = is_sqlite and ":memory:" in settings.database_url
engine_kwargs = {"pool_pre_ping": True}
if is_sqlite_memory:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
