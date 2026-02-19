from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config import settings

database_url = settings.database_url

connect_args = {}
engine_kwargs = {"pool_pre_ping": True}

if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # If it's in-memory SQLite, force a single shared connection
    if ":memory:" in database_url or database_url.endswith("sqlite+pysqlite://"):
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)
