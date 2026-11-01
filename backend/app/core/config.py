from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "app"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/app"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 60 * 12
    cors_origins: str = "http://localhost:5173"
    # OpenAI-compatible endpoint (OpenAI, Azure OpenAI proxy, Ollama, vLLM, LM Studio ...)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 256


@lru_cache
def get_settings() -> Settings:
    return Settings()
