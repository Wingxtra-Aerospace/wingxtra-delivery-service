from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Wingxtra Delivery Service"
    app_env: str = "dev"
    debug: bool = True

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/wingxtra"
    fleet_api_base_url: str = "http://localhost:9000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
