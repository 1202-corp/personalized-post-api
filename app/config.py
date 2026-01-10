from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql+asyncpg://ppb_user:ppb_secret@localhost:5432/ppb_db"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # App settings
    debug: bool = False
    
    # OpenAI-compatible API settings
    openai_api_base: str = "https://bothub.chat/api/v2/openai/v1"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimensions: int = 1536  # text-embedding-ada-002 dimension
    
    # Qdrant settings
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "post_embeddings"
    
    # Default training channels
    default_training_channels: str = "@durov,@telegram"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
