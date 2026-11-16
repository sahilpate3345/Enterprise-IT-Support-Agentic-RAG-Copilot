
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):

    # Application
    app_name: str = "Enterprise IT Support Agentic RAG Copilot"
    app_env: str = "development"

    # API Keys
    jina_api_key: str = ""
    groq_api_key: str = ""
    tavily_api_key: str = ""
    qdrant_api_key: str = ""

    # Models
    model_name: str = "jina-embeddings-v2-base-en"

    # Qdrant
    qdrant_url: str = ""
    qdrant_collection_name: str = "IT_SUPPORT"

    # LangSmith
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # RAG Configuration
    top_k: int = 4
    max_retries: int = 1

    # Security
    admin_api_key: str = "change-me"

    # Directories
    audit_db_path: str = str(BASE_DIR / "data" / "audit.db")
    upload_dir: str = str(BASE_DIR / "uploads")
    sample_kb_dir: str = str(BASE_DIR / "data" / "sample_kb")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
