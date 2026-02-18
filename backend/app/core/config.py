from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    PROJECT_NAME: str = "workflow-builder-backend"
    API_V1_STR: str = "/api"

    DATABASE_URL: str = "sqlite:///./data/app.db"

    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60

    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: str | None = None
    TEST_USERS: str | None = None

    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_API_MODE: str = "responses"  # responses | chat

    CORS_ORIGINS: str = ""


settings = Settings()
