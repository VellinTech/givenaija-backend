from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "GiveNaija API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@db:5432/givenaija"
    )
    REDIS_URL: str = "redis://redis:6379/0"

    SECRET_KEY: str = "super_secret_jwt_key_change_in_prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    WEBHOOK_SECRET: str = "webhook_hmac_secret_key"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()