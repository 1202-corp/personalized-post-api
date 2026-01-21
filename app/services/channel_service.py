"""Channel business logic service."""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.channel import Channel
from app.repositories.channel_repository import ChannelRepository
from app.repositories.user_channel_repository import UserChannelRepository
from app.repositories.user_repository import UserRepository
from app.schemas import ChannelCreate, UserChannelAdd
from app.config import get_settings
from app.exceptions import NotFoundError, ValidationError
from app.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ChannelService:
    """Service for channel operations."""
    
    @staticmethod
    async def get_channel_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[Channel]:
        """Get channel by Telegram ID."""
        return await ChannelRepository.get_by_telegram_id(session, telegram_id)
    
    @staticmethod
    async def get_channel_by_username(session: AsyncSession, username: str) -> Optional[Channel]:
        """Get channel by username."""
        return await ChannelRepository.get_by_username(session, username)
    
    @staticmethod
    async def create_channel(session: AsyncSession, channel_data: ChannelCreate) -> Channel:
        """Create a new channel."""
        try:
            # Determine if this channel should be treated as a default training channel
            default_usernames = [
                u.lstrip("@").lower()
                for u in settings.default_training_channels.split(",")
                if u.strip()
            ]
            username_normalized = (channel_data.username or "").lstrip("@").lower()
            is_default = channel_data.is_default or username_normalized in default_usernames
            
            # Update channel_data with is_default
            channel_data.is_default = is_default
            
            channel = await ChannelRepository.create(session, channel_data)
            await session.commit()
            await session.refresh(channel)
            logger.info("channel_created", channel_id=channel.id, telegram_id=channel.telegram_id)
            return channel
        except Exception as e:
            await session.rollback()
            logger.error("channel_creation_failed", error=str(e), exc_info=True)
            raise
    
    @staticmethod
    async def get_or_create_channel(session: AsyncSession, channel_data: ChannelCreate) -> tuple[Channel, bool]:
        """Get existing channel or create new one. Returns (channel, is_new)."""
        try:
            # Determine if this channel should be treated as a default training channel
            default_usernames = [
                u.lstrip("@").lower()
                for u in settings.default_training_channels.split(",")
                if u.strip()
            ]
            username_normalized = (channel_data.username or "").lstrip("@").lower()
            is_default = channel_data.is_default or username_normalized in default_usernames
            channel_data.is_default = is_default
            
            channel, is_new = await ChannelRepository.get_or_create(session, channel_data)
            await session.commit()
            if is_new:
                await session.refresh(channel)
                logger.info("channel_created", channel_id=channel.id, telegram_id=channel.telegram_id)
            return channel, is_new
        except Exception as e:
            await session.rollback()
            logger.error("get_or_create_channel_failed", error=str(e), exc_info=True)
            raise
    
    @staticmethod
    async def get_default_channels(session: AsyncSession) -> List[Channel]:
        """Get all default training channels.
        
        Primary source is channels explicitly marked as default.
        If none are marked yet, we fall back to channels whose usernames
        are listed in settings.default_training_channels and mark them
        as default for subsequent calls.
        """
        channels = await ChannelRepository.get_default_channels(session)
        if channels:
            return channels
        
        # Fallback: derive defaults from configuration
        default_usernames = [
            u.lstrip("@").lower()
            for u in settings.default_training_channels.split(",")
            if u.strip()
        ]
        if not default_usernames:
            return []
        
        # Find existing channels matching configured default usernames
        from sqlalchemy import select, func
        result = await session.execute(
            select(Channel).where(
                Channel.is_active == True,
                Channel.is_deleted == False,
                func.lower(Channel.username).in_(default_usernames),
            )
        )
        channels = list(result.scalars().all())
        
        # Mark them as default so next call sees them without fallback
        if channels:
            try:
                for ch in channels:
                    ch.is_default = True
                await session.commit()
                logger.info("channels_marked_as_default", count=len(channels))
            except Exception as e:
                await session.rollback()
                logger.error("failed_to_mark_channels_as_default", error=str(e), exc_info=True)
        
        return channels
    
    @staticmethod
    async def add_user_channel(session: AsyncSession, user_channel_data: UserChannelAdd) -> Optional[Channel]:
        """Associate a channel with a user."""
        try:
            user = await UserRepository.get_by_telegram_id(session, user_channel_data.user_telegram_id)
            if not user:
                raise NotFoundError(f"User with telegram_id {user_channel_data.user_telegram_id} not found")
            
            channel = await ChannelRepository.get_by_username(session, user_channel_data.channel_username)
            if not channel:
                raise NotFoundError(f"Channel with username {user_channel_data.channel_username} not found")
            
            user_channel = await UserChannelRepository.create(
                session,
                user.id,
                channel.id,
                user_channel_data.is_for_training,
                user_channel_data.is_bonus
            )
            if not user_channel:
                raise ValidationError("User-channel association already exists")
            
            await session.commit()
            await session.refresh(user_channel)
            logger.info(
                "user_channel_created",
                user_channel_id=user_channel.id,
                user_id=user.id,
                channel_id=channel.id
            )
            return channel
        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            await session.rollback()
            logger.error("add_user_channel_failed", error=str(e), exc_info=True)
            raise ValidationError(f"Failed to add user channel: {str(e)}")
    
    @staticmethod
    async def get_user_training_channels(session: AsyncSession, user_telegram_id: int) -> List[Channel]:
        """Get all channels user is using for training."""
        user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
        if not user:
            return []
        
        return await UserChannelRepository.get_training_channels_by_user(session, user.id)
    
    @staticmethod
    async def get_user_channels(session: AsyncSession, user_telegram_id: int) -> List[Channel]:
        """Get all channels associated with user."""
        user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
        if not user:
            return []
        
        user_channels = await UserChannelRepository.get_by_user_id(session, user.id)
        channel_ids = [uc.channel_id for uc in user_channels]
        if not channel_ids:
            return []
        
        channels = []
        for channel_id in channel_ids:
            channel = await ChannelRepository.get_by_id(session, channel_id)
            if channel:
                channels.append(channel)
        return channels


# Maintain backward compatibility
async def get_channel_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[Channel]:
    """Get channel by Telegram ID."""
    return await ChannelService.get_channel_by_telegram_id(session, telegram_id)


async def get_channel_by_username(session: AsyncSession, username: str) -> Optional[Channel]:
    """Get channel by username."""
    return await ChannelService.get_channel_by_username(session, username)


async def create_channel(session: AsyncSession, channel_data: ChannelCreate) -> Channel:
    """Create a new channel."""
    return await ChannelService.create_channel(session, channel_data)


async def get_or_create_channel(session: AsyncSession, channel_data: ChannelCreate) -> tuple[Channel, bool]:
    """Get existing channel or create new one. Returns (channel, is_new)."""
    return await ChannelService.get_or_create_channel(session, channel_data)


async def get_default_channels(session: AsyncSession) -> List[Channel]:
    """Get all default training channels."""
    return await ChannelService.get_default_channels(session)


async def add_user_channel(session: AsyncSession, user_channel_data: UserChannelAdd) -> Optional[Channel]:
    """Associate a channel with a user."""
    return await ChannelService.add_user_channel(session, user_channel_data)


async def get_user_training_channels(session: AsyncSession, user_telegram_id: int) -> List[Channel]:
    """Get all channels user is using for training."""
    return await ChannelService.get_user_training_channels(session, user_telegram_id)


async def get_user_channels(session: AsyncSession, user_telegram_id: int) -> List[Channel]:
    """Get all channels associated with user."""
    return await ChannelService.get_user_channels(session, user_telegram_id)
