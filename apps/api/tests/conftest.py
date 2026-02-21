import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.auth.dependencies import reset_rate_limits
from app.db.base import Base
from app.db.session import engine as app_engine
from app.db.session import get_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_schema():
    Base.metadata.drop_all(bind=app_engine)
    Base.metadata.create_all(bind=app_engine)
    yield
    Base.metadata.drop_all(bind=app_engine)




@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=app_engine)
    Base.metadata.create_all(bind=app_engine)
    yield


@pytest.fixture(autouse=True)
def reset_rate_limit_buckets():
    reset_rate_limits()
    yield
    reset_rate_limits()

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
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
