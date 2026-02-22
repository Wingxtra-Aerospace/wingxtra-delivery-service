import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.auth.dependencies import reset_rate_limits
from app.config import settings
from app.db.base import Base
from app.db.session import engine as app_engine
from app.db.session import get_db
from app.main import app
from app.observability import metrics_store
from app.services.store import reset_store


@pytest.fixture(scope="session", autouse=True)
def setup_test_schema():
    Base.metadata.drop_all(bind=app_engine)
    Base.metadata.create_all(bind=app_engine)
    yield
    Base.metadata.drop_all(bind=app_engine)


@pytest.fixture(autouse=True)
def reset_db():
    reset_rate_limits()
    Base.metadata.drop_all(bind=app_engine)
    Base.metadata.create_all(bind=app_engine)
    yield


@pytest.fixture(autouse=True)
def reset_in_memory_store():
    reset_store()
    yield


@pytest.fixture(autouse=True)
def reset_metrics_store():
    metrics_store.reset()
    yield


@pytest.fixture
def db_session():
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=app_engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=app_engine)
    db_session_lock = threading.Lock()

    def override_get_db():
        if db_session_lock.acquire(blocking=False):
            try:
                yield db_session
            finally:
                db_session_lock.release()
            return

        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session", autouse=True)
def enable_test_auth_bypass():
    original = settings.enable_test_auth_bypass
    settings.enable_test_auth_bypass = True
    yield
    settings.enable_test_auth_bypass = original


@pytest.fixture(scope="session", autouse=True)
def enable_testing_mode():
    original = settings.testing
    settings.testing = True
    yield
    settings.testing = original
