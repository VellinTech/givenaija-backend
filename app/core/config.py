

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
   

  
    PROJECT_NAME: str = "GiveNaija API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/v1"

   
    SECRET_KEY: str = "super_secret_jwt_key_change_in_production_32bytes"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # Default token lifespan: 24 Hours
    WEBHOOK_SECRET: str = "whsec_test_givenaija_secret_key"  # Secret used to verify gateway HMACs

   
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/givenaija_db"
    ALEMBIC_DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@db:5432/givenaija"

    REDIS_URL: str = "redis://localhost:6379/0"

    
    FIRESTORE_PROJECT_ID: Optional[str] = "givenaija-dev"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    
    PAYSTACK_SECRET_KEY: str


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  
    )



settings = Settings()
