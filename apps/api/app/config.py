from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "wingxtra-jwt-secret"
DEFAULT_POD_OTP_HMAC_SECRET = "wingxtra-pod-otp-secret"
ALLOWED_RUNTIME_UI_SERVICE_MODES = {"db"}
ALLOWED_UI_SERVICE_MODES = {"store", "db", "hybrid", "auto"}
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    app_name: str = "Wingxtra Delivery Service"

    database_url: str = Field(
        default="sqlite+pysqlite:///./test.db",
        validation_alias="WINGXTRA_DATABASE_URL",
    )
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    jwt_secret: str = DEFAULT_JWT_SECRET
    allowed_roles: str = "CUSTOMER,MERCHANT,OPS,ADMIN"
    gcs_auth_source: str = "gcs"
    enable_test_auth_bypass: bool = False
    testing: bool = Field(default=False, validation_alias="WINGXTRA_TESTING")
    ui_service_mode: str = Field(default="auto", validation_alias="WINGXTRA_UI_SERVICE_MODE")

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

    redis_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("ui_service_mode")
    @classmethod
    def validate_ui_service_mode(cls, value: str) -> str:
        mode = value.lower().strip()
        if mode not in ALLOWED_UI_SERVICE_MODES:
            allowed = ", ".join(sorted(ALLOWED_UI_SERVICE_MODES))
            raise ValueError(f"WINGXTRA_UI_SERVICE_MODE must be one of: {allowed}")
        return mode


settings = Settings()


def resolved_ui_service_mode() -> str:
    if settings.ui_service_mode == "auto":
        return "hybrid" if settings.testing else "db"
    return settings.ui_service_mode


def allowed_origins() -> list[str]:
    return [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]


def allowed_roles_list() -> list[str]:
    return [value.strip() for value in settings.allowed_roles.split(",") if value.strip()]


def ensure_secure_runtime_settings() -> None:
    """Fail fast when production-like runtime uses insecure defaults."""
    if not settings.testing and settings.jwt_secret == DEFAULT_JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET must be set to a non-default value when WINGXTRA_TESTING is false"
        )
    if not settings.testing and settings.pod_otp_hmac_secret == DEFAULT_POD_OTP_HMAC_SECRET:
        raise RuntimeError(
            "POD_OTP_HMAC_SECRET must be set to a non-default value when WINGXTRA_TESTING is false"
        )
    if not settings.testing and len(settings.jwt_secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            "JWT_SECRET must be at least "
            f"{MIN_SECRET_LENGTH} characters when WINGXTRA_TESTING is false"
        )
    if not settings.testing and len(settings.pod_otp_hmac_secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            "POD_OTP_HMAC_SECRET must be at least "
            f"{MIN_SECRET_LENGTH} characters when WINGXTRA_TESTING is false"
        )
    if not settings.testing and resolved_ui_service_mode() not in ALLOWED_RUNTIME_UI_SERVICE_MODES:
        raise RuntimeError("WINGXTRA_UI_SERVICE_MODE must be 'db' when WINGXTRA_TESTING is false")
    if not settings.testing and _is_sqlite_url(settings.database_url):
        raise RuntimeError("WINGXTRA_DATABASE_URL must use postgres when WINGXTRA_TESTING is false")


def _is_sqlite_url(database_url: str) -> bool:
    value = database_url.strip().lower()
    return value.startswith("sqlite")
