"""Post repository."""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.post import Post
from app.models.channel import Channel
from app.schemas import PostCreate


class PostRepository:
    """Repository for post operations."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, post_id: int) -> Optional[Post]:
        """Get post by ID."""
        result = await db.execute(
            select(Post).where(
                Post.id == post_id,
                Post.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_channel_and_message(
        db: AsyncSession,
        channel_id: int,
        telegram_message_id: int
    ) -> Optional[Post]:
        """Get post by channel ID and Telegram message ID."""
        result = await db.execute(
            select(Post).where(
                Post.channel_id == channel_id,
                Post.telegram_message_id == telegram_message_id,
                Post.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_channel_telegram_id_and_message(
        db: AsyncSession,
        channel_telegram_id: int,
        telegram_message_id: int
    ) -> Optional[Post]:
        """Get post by channel Telegram ID and Telegram message ID."""
        result = await db.execute(
            select(Post)
            .join(Channel)
            .where(
                Channel.telegram_id == channel_telegram_id,
                Post.telegram_message_id == telegram_message_id,
                Post.is_deleted == False,
                Channel.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_by_channel(db: AsyncSession, channel_id: int) -> List[Post]:
        """Get all posts for a channel."""
        result = await db.execute(
            select(Post).where(
                Post.channel_id == channel_id,
                Post.is_deleted == False
            ).order_by(Post.posted_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def create(db: AsyncSession, post_data: PostCreate, channel_id: int) -> Optional[Post]:
        """Create a new post (without commit)."""
        post = Post(
            channel_id=channel_id,
            telegram_message_id=post_data.telegram_message_id,
            text=post_data.text,
            media_type=post_data.media_type,
            media_file_id=post_data.media_file_id,
            posted_at=post_data.posted_at,
        )
        db.add(post)
        await db.flush()
        return post
    
    @staticmethod
    async def bulk_create(db: AsyncSession, posts_data: List[Post], channel_id: int) -> List[Post]:
        """Create multiple posts (without commit)."""
        db.add_all(posts_data)
        await db.flush()
        return posts_data
    
    @staticmethod
    async def update(db: AsyncSession, post_id: int, **kwargs) -> Optional[Post]:
        """Update post fields (without commit)."""
        post = await PostRepository.get_by_id(db, post_id)
        if not post:
            return None
        
        updated = False
        for field, value in kwargs.items():
            if hasattr(post, field) and getattr(post, field) != value:
                setattr(post, field, value)
                updated = True
        
        if updated:
            await db.flush()
            return post
        return None
    
    @staticmethod
    async def soft_delete(db: AsyncSession, post_id: int) -> Optional[Post]:
        """Soft delete a post (without commit)."""
        post = await PostRepository.get_by_id(db, post_id)
        if not post or post.is_deleted:
            return None
        
        post.is_deleted = True
        post.deleted_at = datetime.utcnow()
        await db.flush()
        return post
    
    @staticmethod
    async def delete(db: AsyncSession, post_id: int, hard: bool = False) -> Optional[Post]:
        """Delete a post (without commit)."""
        if not hard:
            return await PostRepository.soft_delete(db, post_id)
        
        post = await PostRepository.get_by_id(db, post_id)
        if not post:
            return None
        
        await db.delete(post)
        await db.flush()
        return post

