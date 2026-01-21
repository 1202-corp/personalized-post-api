"""UserChannel repository."""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_channel import UserChannel
from app.models.user import User
from app.models.channel import Channel
from app.schemas import UserChannelAdd


class UserChannelRepository:
    """Repository for user-channel association operations."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, user_channel_id: int) -> Optional[UserChannel]:
        """Get user-channel association by ID."""
        result = await db.execute(
            select(UserChannel).where(UserChannel.id == user_channel_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_user_and_channel(
        db: AsyncSession,
        user_id: int,
        channel_id: int
    ) -> Optional[UserChannel]:
        """Get user-channel association by user ID and channel ID."""
        result = await db.execute(
            select(UserChannel).where(
                UserChannel.user_id == user_id,
                UserChannel.channel_id == channel_id
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: int) -> List[UserChannel]:
        """Get all channel associations for a user."""
        result = await db.execute(
            select(UserChannel)
            .join(User)
            .where(
                User.id == user_id,
                User.is_deleted == False
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_by_channel_id(db: AsyncSession, channel_id: int) -> List[UserChannel]:
        """Get all user associations for a channel."""
        result = await db.execute(
            select(UserChannel)
            .join(Channel)
            .where(
                Channel.id == channel_id,
                Channel.is_deleted == False
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_training_channels_by_user(
        db: AsyncSession,
        user_id: int
    ) -> List[Channel]:
        """Get all training channels for a user."""
        result = await db.execute(
            select(Channel)
            .join(UserChannel)
            .join(User)
            .where(
                User.id == user_id,
                UserChannel.is_for_training == True,
                User.is_deleted == False,
                Channel.is_deleted == False
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int,
        channel_id: int,
        is_for_training: bool = False,
        is_bonus: bool = False
    ) -> Optional[UserChannel]:
        """Create a new user-channel association (without commit)."""
        # Check if association already exists
        existing = await UserChannelRepository.get_by_user_and_channel(db, user_id, channel_id)
        if existing:
            return None
        
        user_channel = UserChannel(
            user_id=user_id,
            channel_id=channel_id,
            is_for_training=is_for_training,
            is_bonus=is_bonus,
        )
        db.add(user_channel)
        await db.flush()
        return user_channel
    
    @staticmethod
    async def delete(db: AsyncSession, user_channel_id: int) -> bool:
        """Delete a user-channel association (without commit)."""
        user_channel = await UserChannelRepository.get_by_id(db, user_channel_id)
        if not user_channel:
            return False
        
        await db.delete(user_channel)
        await db.flush()
        return True
    
    @staticmethod
    async def delete_by_user_and_channel(
        db: AsyncSession,
        user_id: int,
        channel_id: int
    ) -> bool:
        """Delete a user-channel association by user and channel IDs (without commit)."""
        user_channel = await UserChannelRepository.get_by_user_and_channel(db, user_id, channel_id)
        if not user_channel:
            return False
        
        await db.delete(user_channel)
        await db.flush()
        return True

