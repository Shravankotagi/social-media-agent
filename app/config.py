"""
app/config.py — Centralised settings loaded from environment variables.
Uses pydantic-settings for type-safe config with .env file support.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    groq_api_key: str = ""
    groq_model: str = "llama3-70b-8192"

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "agent_user"
    mysql_password: str = "agent_password"
    mysql_database: str = "social_agent"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8010

    # Twitter / X
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_secret: str = ""
    twitter_bearer_token: str = ""

    # LinkedIn
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_access_token: str = ""

    # Proxycurl
    proxycurl_api_key: str = ""

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change_this"

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+mysqlconnector://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def chroma_url(self) -> str:
        return f"http://{self.chroma_host}:{self.chroma_port}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
