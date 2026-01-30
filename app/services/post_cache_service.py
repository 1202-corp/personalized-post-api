"""Post content cache service for Redis."""
import json
import base64
import logging
from typing import Optional, Dict, Any, TypeVar, Callable, Awaitable
from datetime import datetime, timedelta
import redis.asyncio as aioredis
from app.config import get_settings

logger = logging.getLogger(__name__)

# TTL for post content cache: 6 hours
CACHE_TTL_SECONDS = 6 * 60 * 60  # 21600 seconds


class PostCacheService:
    """Service for caching post text and media in Redis."""
    
    def __init__(self):
        self.settings = get_settings()
        self._redis_client: Optional[aioredis.Redis] = None
    
    async def _get_redis_client(self) -> aioredis.Redis:
        """Get or create Redis client."""
        if self._redis_client is None:
            self._redis_client = aioredis.from_url(
                self.settings.redis_url,
                decode_responses=False,  # We store binary data
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        return self._redis_client
    
    async def close(self):
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.aclose()
            self._redis_client = None
    
    def _get_cache_key(self, post_id: int) -> str:
        """Get Redis key for post content cache."""
        return f"post:{post_id}:content"
    
    async def get_post_content(
        self, 
        post_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get post content (text and media) from cache.
        
        Args:
            post_id: Post ID
            
        Returns:
            Dict with keys: text, media_type, media_data, telegram_file_id, cached_at
            or None if not found/expired
        """
        try:
            redis_client = await self._get_redis_client()
            cache_key = self._get_cache_key(post_id)
            
            # Get hash data
            data = await redis_client.hgetall(cache_key)
            if not data:
                return None
            
            # Decode hash fields
            result = {}
            for key, value in data.items():
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                if key_str == 'media_data' and value:
                    # media_data is stored as base64 string; return as-is (binary must not be decoded as utf-8)
                    result[key_str] = value.decode('utf-8') if isinstance(value, bytes) else value
                elif key_str == 'cached_at':
                    result[key_str] = value.decode('utf-8') if isinstance(value, bytes) else value
                else:
                    result[key_str] = value.decode('utf-8') if isinstance(value, bytes) else value
            
            return result if result else None
        except Exception as e:
            logger.error(f"Error getting post content from cache (post_id={post_id}): {e}")
            return None
    
    async def set_post_content(
        self,
        post_id: int,
        text: Optional[str] = None,
        media_type: Optional[str] = None,
        media_data: Optional[bytes] = None,
        telegram_file_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Cache post content (text and media) in Redis.
        
        Args:
            post_id: Post ID
            text: HTML text content
            media_type: Type of media (photo, video, etc.)
            media_data: Media data as bytes (will be base64 encoded)
            telegram_file_id: Telegram file_id after bot sent this media (avoids re-download)
            ttl_seconds: Optional TTL in seconds. If None, uses CACHE_TTL_SECONDS (6h).
                         Use 600 for new realtime posts (10 min).
            
        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            cache_key = self._get_cache_key(post_id)
            ttl = ttl_seconds if ttl_seconds is not None else CACHE_TTL_SECONDS
            
            cache_data: dict = {}
            if text is not None or media_type is not None or media_data is not None:
                cache_data['cached_at'] = datetime.utcnow().isoformat()
            if text is not None:
                cache_data['text'] = text
            if media_type is not None:
                cache_data['media_type'] = media_type
            if media_data is not None:
                cache_data['media_data'] = base64.b64encode(media_data).decode('utf-8')
            if telegram_file_id is not None:
                cache_data['telegram_file_id'] = telegram_file_id
            
            if cache_data:
                await redis_client.hset(cache_key, mapping=cache_data)
            await redis_client.expire(cache_key, ttl)
            
            logger.debug(f"Cached post content (post_id={post_id}, has_text={text is not None}, has_media={media_data is not None}, has_file_id={telegram_file_id is not None})")
            return True
        except Exception as e:
            logger.error(f"Error caching post content (post_id={post_id}): {e}")
            return False
    
    async def invalidate_post_cache(self, post_id: int) -> bool:
        """
        Remove post content from cache.
        
        Args:
            post_id: Post ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            cache_key = self._get_cache_key(post_id)
            result = await redis_client.delete(cache_key)
            logger.debug(f"Invalidated post cache (post_id={post_id}, deleted={result > 0})")
            return result > 0
        except Exception as e:
            logger.error(f"Error invalidating post cache (post_id={post_id}): {e}")
            return False
    
    async def get_multiple_posts_content(
        self,
        post_ids: list[int]
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get content for multiple posts at once.
        
        Args:
            post_ids: List of post IDs
            
        Returns:
            Dict mapping post_id to content dict (or None if not cached)
        """
        result = {}
        for post_id in post_ids:
            content = await self.get_post_content(post_id)
            if content:
                result[post_id] = content
        return result


# Singleton instance
_post_cache_service: Optional[PostCacheService] = None


def get_post_cache_service() -> PostCacheService:
    """Get singleton PostCacheService instance."""
    global _post_cache_service
    if _post_cache_service is None:
        _post_cache_service = PostCacheService()
    return _post_cache_service
