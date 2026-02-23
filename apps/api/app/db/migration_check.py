from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.config import is_production_mode, settings
from app.db.base import Base

_ALEMBIC_VERSION_TABLE = "alembic_version"


def _alembic_ini_path() -> Path:
    return Path(__file__).resolve().parents[2] / "alembic.ini"


def get_alembic_head_revision() -> str:
    config = Config(str(_alembic_ini_path()))
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


def get_current_db_revision(engine: Engine) -> Optional[str]:
    inspector = inspect(engine)
    if not inspector.has_table(_ALEMBIC_VERSION_TABLE):
        return None

    with engine.connect() as connection:
        result = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        return result.scalar_one_or_none()


def assert_db_is_up_to_date(engine: Engine) -> None:
    current = get_current_db_revision(engine)
    head = get_alembic_head_revision()
    if current != head:
        raise RuntimeError("Database schema not up to date. Run: alembic upgrade head")


def maybe_create_schema(engine: Engine) -> None:
    if not settings.auto_create_schema:
        return
    if is_production_mode():
        raise RuntimeError("AUTO_CREATE_SCHEMA must be disabled in APP_MODE=production")

    Base.metadata.create_all(bind=engine)
