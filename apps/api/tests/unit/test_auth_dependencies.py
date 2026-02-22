import pytest
from fastapi import HTTPException

from app.auth.dependencies import get_auth_context
from app.config import settings


def test_get_auth_context_requires_bearer_when_bypass_disabled():
    original = settings.enable_test_auth_bypass
    settings.enable_test_auth_bypass = False
    try:
        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(None, None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Missing bearer token"
    finally:
        settings.enable_test_auth_bypass = original


def test_get_auth_context_allows_bypass_when_explicitly_enabled():
    original = settings.enable_test_auth_bypass
    settings.enable_test_auth_bypass = True
    try:
        auth = get_auth_context(None, None)
        assert auth.user_id == "test-ops"
        assert auth.role == "OPS"
        assert auth.source == "test"
    finally:
        settings.enable_test_auth_bypass = original
