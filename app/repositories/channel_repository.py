"""Channel repository."""
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.channel import Channel
from app.schemas import ChannelCreate


class ChannelRepository:
    """Repository for channel operations."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, channel_id: int) -> Optional[Channel]:
        """Get channel by ID."""
        result = await db.execute(
            select(Channel).where(
                Channel.id == channel_id,
                Channel.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_telegram_id(db: AsyncSession, telegram_id: int) -> Optional[Channel]:
        """Get channel by Telegram ID."""
        result = await db.execute(
            select(Channel).where(
                Channel.telegram_id == telegram_id,
                Channel.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[Channel]:
        """Get channel by username."""
        # Normalize username
        username = username.lstrip("@").lower()
        result = await db.execute(
            select(Channel).where(
                Channel.username.ilike(username),
                Channel.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all(db: AsyncSession) -> List[Channel]:
        """Get all channels."""
        result = await db.execute(
            select(Channel).where(
                Channel.is_deleted == False
            ).order_by(Channel.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_default_channels(db: AsyncSession) -> List[Channel]:
        """Get all default training channels."""
        result = await db.execute(
            select(Channel).where(
                Channel.is_default == True,
                Channel.is_active == True,
                Channel.is_deleted == False
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def create(db: AsyncSession, channel_data: ChannelCreate) -> Channel:
        """Create a new channel (without commit)."""
        channel = Channel(
            telegram_id=channel_data.telegram_id,
            username=channel_data.username,
            title=channel_data.title,
            is_default=channel_data.is_default,
        )
        db.add(channel)
        await db.flush()
        return channel
    
    @staticmethod
    async def get_or_create(db: AsyncSession, channel_data: ChannelCreate) -> tuple[Channel, bool]:
        """Get existing channel or create new one. Returns (channel, is_new)."""
        channel = await ChannelRepository.get_by_telegram_id(db, channel_data.telegram_id)
        if channel:
            return channel, False
        
        # Check if soft-deleted channel exists
        result = await db.execute(
            select(Channel).where(
                Channel.telegram_id == channel_data.telegram_id,
                Channel.is_deleted == True
            )
        )
        deleted_channel = result.scalar_one_or_none()
        
        if deleted_channel:
            # Restore soft-deleted channel
            deleted_channel.is_deleted = False
            deleted_channel.deleted_at = None
            deleted_channel.username = channel_data.username
            deleted_channel.title = channel_data.title
            deleted_channel.is_default = channel_data.is_default
            await db.flush()
            return deleted_channel, True
        
        channel = await ChannelRepository.create(db, channel_data)
        return channel, True
    
    @staticmethod
    async def update(db: AsyncSession, channel_id: int, **kwargs) -> Optional[Channel]:
        """Update channel fields (without commit)."""
        channel = await ChannelRepository.get_by_id(db, channel_id)
        if not channel:
            return None
        
        updated = False
        for field, value in kwargs.items():
            if hasattr(channel, field) and getattr(channel, field) != value:
                setattr(channel, field, value)
                updated = True
        
        if updated:
            await db.flush()
            return channel
        return None
    
    @staticmethod
    async def soft_delete(db: AsyncSession, channel_id: int) -> Optional[Channel]:
        """Soft delete a channel (without commit)."""
        channel = await ChannelRepository.get_by_id(db, channel_id)
        if not channel or channel.is_deleted:
            return None
        
        channel.is_deleted = True
        from datetime import datetime
        channel.deleted_at = datetime.utcnow()
        await db.flush()
        return channel
    
    @staticmethod
    async def delete(db: AsyncSession, channel_id: int, hard: bool = False) -> Optional[Channel]:
        """Delete a channel (without commit)."""
        if not hard:
            return await ChannelRepository.soft_delete(db, channel_id)
        
        channel = await ChannelRepository.get_by_id(db, channel_id)
        if not channel:
            return None
        
        await db.delete(channel)
        await db.flush()
        return channel

