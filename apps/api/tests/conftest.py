import pytest

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import engine


@pytest.fixture(scope="session", autouse=True)
def _create_test_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
