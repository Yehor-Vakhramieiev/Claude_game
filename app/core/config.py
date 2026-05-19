from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bridge"
    secret_key: str = "change-me-to-a-long-random-secret"
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()
