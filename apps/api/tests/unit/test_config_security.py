import pytest
from pydantic import ValidationError

from app import config as config_module


def test_runtime_security_allows_testing_with_defaults():
    original_testing = config_module.settings.testing
    original_jwt = config_module.settings.jwt_secret
    original_pod = config_module.settings.pod_otp_hmac_secret
    original_mode = config_module.settings.ui_service_mode
    original_db = config_module.settings.database_url
    config_module.settings.testing = True
    config_module.settings.jwt_secret = config_module.DEFAULT_JWT_SECRET
    config_module.settings.pod_otp_hmac_secret = config_module.DEFAULT_POD_OTP_HMAC_SECRET
    config_module.settings.ui_service_mode = "hybrid"
    config_module.settings.database_url = "sqlite+pysqlite:///./test.db"
    try:
        config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.jwt_secret = original_jwt
        config_module.settings.pod_otp_hmac_secret = original_pod
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.database_url = original_db


def test_runtime_security_rejects_default_pod_secret_when_not_testing():
    original_testing = config_module.settings.testing
    original_jwt = config_module.settings.jwt_secret
    original_pod = config_module.settings.pod_otp_hmac_secret
    original_mode = config_module.settings.ui_service_mode
    original_db = config_module.settings.database_url
    config_module.settings.testing = False
    config_module.settings.jwt_secret = "strong-jwt-secret"
    config_module.settings.pod_otp_hmac_secret = config_module.DEFAULT_POD_OTP_HMAC_SECRET
    config_module.settings.ui_service_mode = "db"
    config_module.settings.database_url = "postgresql+psycopg2://user:pass@localhost:5432/wingxtra"
    try:
        with pytest.raises(RuntimeError, match="POD_OTP_HMAC_SECRET"):
            config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.jwt_secret = original_jwt
        config_module.settings.pod_otp_hmac_secret = original_pod
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.database_url = original_db


def test_runtime_security_rejects_non_db_ui_mode_when_not_testing():
    original_testing = config_module.settings.testing
    original_jwt = config_module.settings.jwt_secret
    original_pod = config_module.settings.pod_otp_hmac_secret
    original_mode = config_module.settings.ui_service_mode
    original_db = config_module.settings.database_url
    config_module.settings.testing = False
    config_module.settings.jwt_secret = "x" * config_module.MIN_SECRET_LENGTH
    config_module.settings.pod_otp_hmac_secret = "y" * config_module.MIN_SECRET_LENGTH
    config_module.settings.ui_service_mode = "hybrid"
    config_module.settings.database_url = "postgresql+psycopg2://user:pass@localhost:5432/wingxtra"
    try:
        with pytest.raises(RuntimeError, match="WINGXTRA_UI_SERVICE_MODE"):
            config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.jwt_secret = original_jwt
        config_module.settings.pod_otp_hmac_secret = original_pod
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.database_url = original_db


def test_runtime_security_rejects_default_jwt_secret_when_not_testing():
    original_testing = config_module.settings.testing
    original_jwt = config_module.settings.jwt_secret
    original_pod = config_module.settings.pod_otp_hmac_secret
    original_mode = config_module.settings.ui_service_mode
    original_db = config_module.settings.database_url
    config_module.settings.testing = False
    config_module.settings.jwt_secret = config_module.DEFAULT_JWT_SECRET
    config_module.settings.pod_otp_hmac_secret = "strong-secret"
    config_module.settings.ui_service_mode = "db"
    config_module.settings.database_url = "postgresql+psycopg2://user:pass@localhost:5432/wingxtra"
    try:
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.jwt_secret = original_jwt
        config_module.settings.pod_otp_hmac_secret = original_pod
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.database_url = original_db


def test_runtime_security_rejects_sqlite_database_when_not_testing():
    original_testing = config_module.settings.testing
    original_jwt = config_module.settings.jwt_secret
    original_pod = config_module.settings.pod_otp_hmac_secret
    original_mode = config_module.settings.ui_service_mode
    original_db = config_module.settings.database_url
    config_module.settings.testing = False
    config_module.settings.jwt_secret = "x" * config_module.MIN_SECRET_LENGTH
    config_module.settings.pod_otp_hmac_secret = "y" * config_module.MIN_SECRET_LENGTH
    config_module.settings.ui_service_mode = "db"
    config_module.settings.database_url = "sqlite+pysqlite:///./test.db"
    try:
        with pytest.raises(RuntimeError, match="WINGXTRA_DATABASE_URL"):
            config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.jwt_secret = original_jwt
        config_module.settings.pod_otp_hmac_secret = original_pod
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.database_url = original_db


def test_runtime_security_allows_hardened_non_test_runtime():
    original_testing = config_module.settings.testing
    original_jwt = config_module.settings.jwt_secret
    original_pod = config_module.settings.pod_otp_hmac_secret
    original_mode = config_module.settings.ui_service_mode
    original_db = config_module.settings.database_url
    config_module.settings.testing = False
    config_module.settings.jwt_secret = "x" * config_module.MIN_SECRET_LENGTH
    config_module.settings.pod_otp_hmac_secret = "y" * config_module.MIN_SECRET_LENGTH
    config_module.settings.ui_service_mode = "db"
    config_module.settings.database_url = "postgresql+psycopg2://user:pass@localhost:5432/wingxtra"
    try:
        config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.jwt_secret = original_jwt
        config_module.settings.pod_otp_hmac_secret = original_pod
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.database_url = original_db


def test_runtime_security_rejects_short_jwt_secret_when_not_testing():
    original_testing = config_module.settings.testing
    original_jwt = config_module.settings.jwt_secret
    original_pod = config_module.settings.pod_otp_hmac_secret
    original_mode = config_module.settings.ui_service_mode
    original_db = config_module.settings.database_url
    config_module.settings.testing = False
    config_module.settings.jwt_secret = "short-secret"
    config_module.settings.pod_otp_hmac_secret = "x" * config_module.MIN_SECRET_LENGTH
    config_module.settings.ui_service_mode = "db"
    config_module.settings.database_url = "postgresql+psycopg2://user:pass@localhost:5432/wingxtra"
    try:
        with pytest.raises(RuntimeError, match="JWT_SECRET must be at least"):
            config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.jwt_secret = original_jwt
        config_module.settings.pod_otp_hmac_secret = original_pod
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.database_url = original_db


def test_runtime_security_rejects_short_pod_secret_when_not_testing():
    original_testing = config_module.settings.testing
    original_jwt = config_module.settings.jwt_secret
    original_pod = config_module.settings.pod_otp_hmac_secret
    original_mode = config_module.settings.ui_service_mode
    original_db = config_module.settings.database_url
    config_module.settings.testing = False
    config_module.settings.jwt_secret = "x" * config_module.MIN_SECRET_LENGTH
    config_module.settings.pod_otp_hmac_secret = "short-secret"
    config_module.settings.ui_service_mode = "db"
    config_module.settings.database_url = "postgresql+psycopg2://user:pass@localhost:5432/wingxtra"
    try:
        with pytest.raises(RuntimeError, match="POD_OTP_HMAC_SECRET must be at least"):
            config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.jwt_secret = original_jwt
        config_module.settings.pod_otp_hmac_secret = original_pod
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.database_url = original_db


def test_resolved_ui_service_mode_auto_is_hybrid_in_testing():
    original_testing = config_module.settings.testing
    original_mode = config_module.settings.ui_service_mode
    config_module.settings.testing = True
    config_module.settings.ui_service_mode = "auto"
    try:
        assert config_module.resolved_ui_service_mode() == "hybrid"
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.ui_service_mode = original_mode


def test_resolved_ui_service_mode_auto_is_db_in_non_test_runtime():
    original_testing = config_module.settings.testing
    original_mode = config_module.settings.ui_service_mode
    config_module.settings.testing = False
    config_module.settings.ui_service_mode = "auto"
    try:
        assert config_module.resolved_ui_service_mode() == "db"
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.ui_service_mode = original_mode


def test_runtime_security_allows_auto_mode_when_not_testing():
    original_testing = config_module.settings.testing
    original_jwt = config_module.settings.jwt_secret
    original_pod = config_module.settings.pod_otp_hmac_secret
    original_mode = config_module.settings.ui_service_mode
    original_db = config_module.settings.database_url
    config_module.settings.testing = False
    config_module.settings.jwt_secret = "x" * config_module.MIN_SECRET_LENGTH
    config_module.settings.pod_otp_hmac_secret = "y" * config_module.MIN_SECRET_LENGTH
    config_module.settings.ui_service_mode = "auto"
    config_module.settings.database_url = "postgresql+psycopg2://user:pass@localhost:5432/wingxtra"
    try:
        config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.jwt_secret = original_jwt
        config_module.settings.pod_otp_hmac_secret = original_pod
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.database_url = original_db


def test_settings_rejects_invalid_ui_service_mode():
    with pytest.raises(ValidationError, match="WINGXTRA_UI_SERVICE_MODE must be one of"):
        config_module.Settings(WINGXTRA_UI_SERVICE_MODE="invalid-mode")


def test_settings_normalizes_ui_service_mode_value():
    settings = config_module.Settings(WINGXTRA_UI_SERVICE_MODE="  HYBRID  ")

    assert settings.ui_service_mode == "hybrid"
