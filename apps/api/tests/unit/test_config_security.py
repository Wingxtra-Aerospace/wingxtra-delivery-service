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
