from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_POD_OTP_HMAC_SECRET = "wingxtra-pod-otp-secret"
ALLOWED_RUNTIME_UI_SERVICE_MODES = {"db"}


class Settings(BaseSettings):
    app_name: str = "Wingxtra Delivery Service"

    database_url: str = Field(
        default="sqlite+pysqlite:///./test.db",
        validation_alias="WINGXTRA_DATABASE_URL",
    )
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    jwt_secret: str = "wingxtra-jwt-secret"
    allowed_roles: str = "CUSTOMER,MERCHANT,OPS,ADMIN"
    gcs_auth_source: str = "gcs"
    enable_test_auth_bypass: bool = False
    testing: bool = Field(default=False, validation_alias="WINGXTRA_TESTING")
    ui_service_mode: str = Field(default="hybrid", validation_alias="WINGXTRA_UI_SERVICE_MODE")

    public_tracking_rate_limit_requests: int = 10
    public_tracking_rate_limit_window_s: int = 60

    order_create_rate_limit_requests: int = 1000
    order_create_rate_limit_window_s: int = 60

    idempotency_ttl_s: int = 24 * 60 * 60
    pod_otp_hmac_secret: str = Field(
        default=DEFAULT_POD_OTP_HMAC_SECRET,
        validation_alias="POD_OTP_HMAC_SECRET",
    )

    fleet_api_base_url: str = ""
    fleet_api_timeout_s: float = 2.0
    fleet_api_max_retries: int = 2
    fleet_api_backoff_s: float = 0.2

    gcs_bridge_base_url: str = ""
    gcs_bridge_timeout_s: float = 2.0
    gcs_bridge_max_retries: int = 2
    gcs_bridge_backoff_s: float = 0.2

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


def allowed_origins() -> list[str]:
    return [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]


def allowed_roles_list() -> list[str]:
    return [value.strip() for value in settings.allowed_roles.split(",") if value.strip()]


def ensure_secure_runtime_settings() -> None:
    """Fail fast when production-like runtime uses insecure defaults."""
    if not settings.testing and settings.pod_otp_hmac_secret == DEFAULT_POD_OTP_HMAC_SECRET:
        raise RuntimeError(
            "POD_OTP_HMAC_SECRET must be set to a non-default value when WINGXTRA_TESTING is false"
        )
    if not settings.testing and settings.ui_service_mode not in ALLOWED_RUNTIME_UI_SERVICE_MODES:
        raise RuntimeError("WINGXTRA_UI_SERVICE_MODE must be 'db' when WINGXTRA_TESTING is false")
