from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    public_tracking_rate_limit_requests: int = 10
    public_tracking_rate_limit_window_s: int = 60

    order_create_rate_limit_requests: int = 5
    order_create_rate_limit_window_s: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


def allowed_origins() -> list[str]:
    return [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]


def allowed_roles_list() -> list[str]:
    return [value.strip() for value in settings.allowed_roles.split(",") if value.strip()]
