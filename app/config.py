"""Configurações da aplicação via variáveis de ambiente."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Lê configurações de variáveis de ambiente ou arquivo .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str = "postgresql+asyncpg://obra:obra@localhost:5432/orcamento_obra"
    api_key: str = "dev-api-key"
    basic_auth_user: str = "admin"
    basic_auth_password: str = "admin"
    web_user: str = "admin"
    web_password: str = "admin"
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
