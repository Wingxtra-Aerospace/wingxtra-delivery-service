import pytest

from app import config as config_module


def test_runtime_security_allows_testing_with_default_pod_secret():
    original_testing = config_module.settings.testing
    original_secret = config_module.settings.pod_otp_hmac_secret
    config_module.settings.testing = True
    config_module.settings.pod_otp_hmac_secret = config_module.DEFAULT_POD_OTP_HMAC_SECRET
    try:
        config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.pod_otp_hmac_secret = original_secret


def test_runtime_security_rejects_default_pod_secret_when_not_testing():
    original_testing = config_module.settings.testing
    original_secret = config_module.settings.pod_otp_hmac_secret
    config_module.settings.testing = False
    config_module.settings.pod_otp_hmac_secret = config_module.DEFAULT_POD_OTP_HMAC_SECRET
    try:
        with pytest.raises(RuntimeError, match="POD_OTP_HMAC_SECRET"):
            config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.pod_otp_hmac_secret = original_secret


def test_runtime_security_rejects_non_db_ui_mode_when_not_testing():
    original_testing = config_module.settings.testing
    original_mode = config_module.settings.ui_service_mode
    original_secret = config_module.settings.pod_otp_hmac_secret
    config_module.settings.testing = False
    config_module.settings.ui_service_mode = "hybrid"
    config_module.settings.pod_otp_hmac_secret = "strong-secret"
    try:
        with pytest.raises(RuntimeError, match="WINGXTRA_UI_SERVICE_MODE"):
            config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.pod_otp_hmac_secret = original_secret


def test_runtime_security_allows_db_ui_mode_when_not_testing():
    original_testing = config_module.settings.testing
    original_mode = config_module.settings.ui_service_mode
    original_secret = config_module.settings.pod_otp_hmac_secret
    config_module.settings.testing = False
    config_module.settings.ui_service_mode = "db"
    config_module.settings.pod_otp_hmac_secret = "strong-secret"
    try:
        config_module.ensure_secure_runtime_settings()
    finally:
        config_module.settings.testing = original_testing
        config_module.settings.ui_service_mode = original_mode
        config_module.settings.pod_otp_hmac_secret = original_secret
