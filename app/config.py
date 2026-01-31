from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql+asyncpg://ppp_user:ppp_secret@localhost:5432/ppp_db"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # User-bot service URL (for fetching training metadata)
    user_bot_url: str = "http://user-bot:8001"
    
    # App settings
    debug: bool = False
    
    # OpenAI-compatible API settings
    openai_api_base: str = "https://bothub.chat/api/v2/openai/v1"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimensions: int = 1536  # text-embedding-ada-002 dimension
    
    # Qdrant vector database settings
    qdrant_host: str = "vector-db-qdrant"  # Docker service name for vector database
    qdrant_port: int = 6333
    qdrant_collection_name: str = "post_embeddings"
    
    # Default training channels
    default_training_channels: str = "@durov,@telegram"
    
    # Training metadata settings (posts downloaded during training: DB metadata + Redis content 6h)
    training_metadata_ttl_hours: int = 6
    training_posts_per_channel_limit: int = 50
    # Realtime posts (new post for publishing): DB + Redis 10 min
    realtime_post_ttl_minutes: int = 10
    # How often to run cleanup of expired realtime posts (seconds); posts are deleted by time, not by event
    realtime_post_cleanup_interval_seconds: int = 60
    
    # Training settings (for miniapp and bot)
    training_recent_posts_per_channel: int = 50
    training_initial_posts_per_channel: int = 8
    training_max_extra_from_dislike: int = 5
    training_max_extra_from_skip: int = 10
    
    # Admin Dashboard JWT Authentication
    admin_username: str = "superadmin"
    admin_password: str = ""
    jwt_secret: str = "change-me-in-production"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
