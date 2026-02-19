from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

is_sqlite = settings.database_url.startswith("sqlite")
is_sqlite_memory = is_sqlite and ":memory:" in settings.database_url
engine_kwargs = {"pool_pre_ping": True}
if is_sqlite_memory:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # If it's in-memory SQLite, force a single shared connection
    if ":memory:" in database_url or database_url.endswith("sqlite+pysqlite://"):
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)
