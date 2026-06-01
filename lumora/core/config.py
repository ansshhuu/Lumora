from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lumora"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://lumora:lumora@postgres:5432/lumora"
    redis_url: str = "redis://redis:6379/0"
    qdrant_url: str = "http://qdrant:6333"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()