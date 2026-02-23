from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

import app.main as main_module
from app.config import settings
from app.db.migration_check import (
    assert_db_is_up_to_date,
    get_alembic_head_revision,
    get_current_db_revision,
    maybe_create_schema,
)
from app.main import app


@pytest.fixture
def sqlite_engine(tmp_path: Path):
    db_path = tmp_path / "migration-check.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    try:
        yield engine
    finally:
        engine.dispose()


def test_assert_db_is_up_to_date_fails_when_alembic_version_missing(sqlite_engine):
    with pytest.raises(RuntimeError, match="Database schema not up to date"):
        assert_db_is_up_to_date(sqlite_engine)


def test_assert_db_is_up_to_date_passes_at_head(sqlite_engine):
    head = get_alembic_head_revision()
    with sqlite_engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:rev)"), {"rev": head}
        )

    assert get_current_db_revision(sqlite_engine) == head
    assert_db_is_up_to_date(sqlite_engine)


def test_maybe_create_schema_creates_tables_when_enabled(sqlite_engine):
    original_auto_create = settings.auto_create_schema
    original_app_mode = settings.app_mode
    settings.auto_create_schema = True
    settings.app_mode = "demo"
    try:
        maybe_create_schema(sqlite_engine)
    finally:
        settings.auto_create_schema = original_auto_create
        settings.app_mode = original_app_mode

    with sqlite_engine.begin() as connection:
        exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        ).scalar_one_or_none()
    assert exists == "orders"


def test_app_startup_fails_fast_in_production_when_revision_missing(tmp_path: Path):
    db_path = tmp_path / "startup-fail.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")

    original_engine = main_module.engine
    original_mode = settings.app_mode
    original_testing = settings.testing
    original_ui_mode = settings.ui_service_mode
    original_auto_create = settings.auto_create_schema
    original_require_migrations = settings.require_migrations

    main_module.engine = engine
    settings.app_mode = "production"
    settings.testing = True
    settings.ui_service_mode = "db"
    settings.auto_create_schema = False
    settings.require_migrations = True

    try:
        with pytest.raises(RuntimeError, match="Database schema not up to date"):
            with TestClient(app):
                pass
    finally:
        main_module.engine = original_engine
        settings.app_mode = original_mode
        settings.testing = original_testing
        settings.ui_service_mode = original_ui_mode
        settings.auto_create_schema = original_auto_create
        settings.require_migrations = original_require_migrations
        engine.dispose()


def test_app_startup_allows_demo_auto_create(tmp_path: Path):
    db_path = tmp_path / "startup-demo.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")

    original_engine = main_module.engine
    original_mode = settings.app_mode
    original_testing = settings.testing
    original_ui_mode = settings.ui_service_mode
    original_auto_create = settings.auto_create_schema
    original_require_migrations = settings.require_migrations

    main_module.engine = engine
    settings.app_mode = "demo"
    settings.testing = True
    settings.ui_service_mode = "db"
    settings.auto_create_schema = True
    settings.require_migrations = False

    try:
        with TestClient(app):
            pass
        with engine.begin() as connection:
            exists = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
            ).scalar_one_or_none()
        assert exists == "orders"
    finally:
        main_module.engine = original_engine
        settings.app_mode = original_mode
        settings.testing = original_testing
        settings.ui_service_mode = original_ui_mode
        settings.auto_create_schema = original_auto_create
        settings.require_migrations = original_require_migrations
        engine.dispose()


def test_app_startup_passes_when_db_at_head(tmp_path: Path):
    db_path = tmp_path / "startup-head.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")

    head = get_alembic_head_revision()
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
            {"rev": head},
        )

    original_engine = main_module.engine
    original_mode = settings.app_mode
    original_testing = settings.testing
    original_ui_mode = settings.ui_service_mode
    original_auto_create = settings.auto_create_schema
    original_require_migrations = settings.require_migrations

    main_module.engine = engine
    settings.app_mode = "production"
    settings.testing = True
    settings.ui_service_mode = "db"
    settings.auto_create_schema = False
    settings.require_migrations = True

    try:
        with TestClient(app):
            pass
    finally:
        main_module.engine = original_engine
        settings.app_mode = original_mode
        settings.testing = original_testing
        settings.ui_service_mode = original_ui_mode
        settings.auto_create_schema = original_auto_create
        settings.require_migrations = original_require_migrations
        engine.dispose()
