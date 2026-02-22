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


def test_settings_rejects_invalid_app_mode():
    with pytest.raises(ValidationError, match="APP_MODE must be one of"):
        config_module.Settings(APP_MODE="invalid-mode")


def test_settings_normalizes_app_mode_value():
    settings = config_module.Settings(APP_MODE="  PRODUCTION  ")

    assert settings.app_mode == "production"


def test_runtime_security_rejects_non_db_mode_in_production_app_mode():
    original_testing = config_module.settings.testing
    original_jwt = config_module.settings.jwt_secret
    original_pod = config_module.settings.pod_otp_hmac_secret
    original_mode = config_module.settings.ui_service_mode
    original_db = config_module.settings.database_url
    original_app_mode = config_module.settings.app_mode
    config_module.settings.testing = True
    config_module.settings.jwt_secret = config_module.DEFAULT_JWT_SECRET
    config_module.settings.pod_otp_hmac_secret = config_module.DEFAULT_POD_OTP_HMAC_SECRET
    config_module.settings.ui_service_mode = "hybrid"
    config_module.settings.database_url = "sqlite+pysqlite:///./test.db"
    config_module.settings.app_mode = "production"
    try:
        with pytest.raises(RuntimeError, match="APP_MODE=production"):
            config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.jwt_secret = original_jwt
        config_module.settings.pod_otp_hmac_secret = original_pod
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.database_url = original_db
        config_module.settings.app_mode = original_app_mode


def test_settings_reads_redis_url_from_env_alias():
    settings = config_module.Settings(REDIS_URL="redis://localhost:6379/0")

    assert settings.redis_url == "redis://localhost:6379/0"


def test_settings_rejects_invalid_redis_url_scheme():
    with pytest.raises(ValidationError, match="REDIS_URL must use redis:// scheme"):
        config_module.Settings(REDIS_URL="rediss://localhost:6379/0")


def test_settings_normalizes_redis_url_whitespace():
    settings = config_module.Settings(REDIS_URL="  redis://localhost:6379/0  ")

    assert settings.redis_url == "redis://localhost:6379/0"


def test_settings_rejects_non_positive_redis_readiness_timeout():
    with pytest.raises(ValidationError, match="redis_readiness_timeout_s must be greater than 0"):
        config_module.Settings(REDIS_READINESS_TIMEOUT_S="0")


def test_settings_accepts_positive_redis_readiness_timeout():
    settings = config_module.Settings(REDIS_READINESS_TIMEOUT_S="2.0")

    assert settings.redis_readiness_timeout_s == 2.0


def test_settings_reads_redis_readiness_timeout_from_env_alias():
    settings = config_module.Settings(REDIS_READINESS_TIMEOUT_S="2.25")

    assert settings.redis_readiness_timeout_s == 2.25


def test_settings_rejects_non_positive_fleet_timeout():
    with pytest.raises(
        ValidationError, match="fleet_api timeout/cache settings must be greater than 0"
    ):
        config_module.Settings(fleet_api_timeout_s=0)


def test_settings_rejects_non_positive_fleet_cache_ttl():
    with pytest.raises(
        ValidationError, match="fleet_api timeout/cache settings must be greater than 0"
    ):
        config_module.Settings(fleet_api_cache_ttl_s=0)
