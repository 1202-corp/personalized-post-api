"""Channel business logic service."""
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.channel import Channel
from app.models.post import Post
from app.models.interaction import Interaction
from app.models.user import User, UserStatus
from app.models.user_channel import UserChannel
from app.repositories.channel_repository import ChannelRepository
from app.repositories.user_channel_repository import UserChannelRepository
from app.repositories.user_repository import UserRepository
from app.schemas import ChannelCreate, UserChannelAdd, UserChannelResponse
from app.config import get_settings
from app.exceptions import NotFoundError, ValidationError
from app.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ChannelService:
    """Service for channel operations."""
    
    @staticmethod
    def _get_default_usernames() -> List[str]:
        """Get list of default training channel usernames from config."""
        return [
            u.lstrip("@").lower()
            for u in settings.default_training_channels.split(",")
            if u.strip()
        ]
    
    @staticmethod
    def _determine_is_default(channel_data: ChannelCreate) -> bool:
        """Determine if channel should be treated as default training channel."""
        default_usernames = ChannelService._get_default_usernames()
        username_normalized = (channel_data.username or "").lstrip("@").lower()
        return channel_data.is_default or username_normalized in default_usernames
    
    @staticmethod
    async def get_channel_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[Channel]:
        """Get channel by Telegram ID."""
        return await ChannelRepository.get_by_telegram_id(session, telegram_id)
    
    @staticmethod
    async def get_channel_by_username(session: AsyncSession, username: str) -> Optional[Channel]:
        """Get channel by username."""
        return await ChannelRepository.get_by_username(session, username)

    @staticmethod
    async def set_channel_avatar_bytes(
        session: AsyncSession, channel_telegram_id: int, avatar_bytes: bytes
    ) -> bool:
        """Set channel avatar from raw image bytes (by Telegram channel id). Returns True if updated."""
        channel = await ChannelRepository.get_by_telegram_id(session, channel_telegram_id)
        if not channel:
            return False
        avatar = await ChannelRepository.get_or_create_avatar(session, channel.id)
        if not avatar:
            return False
        avatar.avatar_photo_bytes = avatar_bytes
        await session.flush()
        return True

    @staticmethod
    async def set_channel_description(
        session: AsyncSession, channel_telegram_id: int, description: Optional[str]
    ) -> bool:
        """Set channel description (bio/about) by Telegram channel id. Returns True if updated."""
        channel = await ChannelRepository.get_by_telegram_id(session, channel_telegram_id)
        if not channel:
            return False
        channel.description = description
        await session.flush()
        return True

    @staticmethod
    async def get_channel_avatar_bytes(
        session: AsyncSession, channel_id: int
    ) -> Optional[bytes]:
        """Get channel avatar bytes by channel id. Returns None if no avatar."""
        channel = await ChannelRepository.get_by_id(session, channel_id)
        if not channel or not channel.avatar_photo_bytes:
            return None
        return channel.avatar_photo_bytes
    
    @staticmethod
    async def create_channel(session: AsyncSession, channel_data: ChannelCreate) -> Channel:
        """Create a new channel."""
        try:
            # Determine if this channel should be treated as a default training channel
            channel_data.is_default = ChannelService._determine_is_default(channel_data)
            
            channel = await ChannelRepository.create(session, channel_data)
            await session.commit()
            await session.refresh(channel, ["avatar"])
            logger.info(f"channel_created: channel_id={channel.id}, telegram_id={channel.telegram_id}")
            return channel
        except Exception as e:
            await session.rollback()
            logger.error(f"channel_creation_failed: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    async def get_or_create_channel(session: AsyncSession, channel_data: ChannelCreate) -> tuple[Channel, bool]:
        """Get existing channel or create new one. Returns (channel, is_new)."""
        try:
            # Determine if this channel should be treated as a default training channel
            channel_data.is_default = ChannelService._determine_is_default(channel_data)
            
            channel, is_new = await ChannelRepository.get_or_create(session, channel_data)
            await session.commit()
            await session.refresh(channel, ["avatar"])
            if is_new:
                logger.info(f"channel_created: channel_id={channel.id}, telegram_id={channel.telegram_id}")
            return channel, is_new
        except Exception as e:
            await session.rollback()
            logger.error(f"get_or_create_channel_failed: {str(e)}", exc_info=True)
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
        default_usernames = ChannelService._get_default_usernames()
        if not default_usernames:
            return []
        
        # Find existing channels matching configured default usernames
        from sqlalchemy import select, func
        result = await session.execute(
            select(Channel).where(
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
                logger.info(f"channels_marked_as_default: count={len(channels)}")
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
                user_channel_data.is_bonus
            )
            if not user_channel:
                raise ValidationError("User-channel association already exists")
            
            await session.commit()
            await session.refresh(user_channel)
            logger.info(
                f"user_channel_created: user_channel_id={user_channel.id}, user_id={user.id}, channel_id={channel.id}"
            )
            return channel
        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"add_user_channel_failed: {str(e)}", exc_info=True)
            raise ValidationError(f"Failed to add user channel: {str(e)}")
    
    @staticmethod
    async def _get_user_or_none(session: AsyncSession, user_telegram_id: int):
        """Helper to get user by telegram_id or return None."""
        return await UserRepository.get_by_telegram_id(session, user_telegram_id)
    
    @staticmethod
    async def get_user_training_channels(session: AsyncSession, user_telegram_id: int) -> List[Channel]:
        """Get all channels user is using for training."""
        user = await ChannelService._get_user_or_none(session, user_telegram_id)
        if not user:
            return []
        
        return await UserChannelRepository.get_training_channels_by_user(session, user.id)
    
    @staticmethod
    async def get_user_channels(session: AsyncSession, user_telegram_id: int) -> List[Channel]:
        """Get all channels associated with user."""
        user = await ChannelService._get_user_or_none(session, user_telegram_id)
        if not user:
            return []
        
        user_channels = await UserChannelRepository.get_by_user_id(session, user.id)
        if not user_channels:
            return []
        
        channel_ids = [uc.channel_id for uc in user_channels]
        result = await session.execute(
            select(Channel)
            .where(Channel.id.in_(channel_ids))
            .options(selectinload(Channel.avatar))
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_users_by_channel(session: AsyncSession, channel_username: str) -> List[dict]:
        """Get all users subscribed to a channel."""
        channel = await ChannelRepository.get_by_username(session, channel_username.lstrip("@"))
        if not channel:
            return []
        
        user_channels = await UserChannelRepository.get_by_channel_id(session, channel.id)
        users = []
        for uc in user_channels:
            user = await UserRepository.get_by_id(session, uc.user_id)
            if user and not user.is_deleted:
                users.append({
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "is_trained": user.is_trained,
                    "language": user.language or "en_US",
                })
        return users

    @staticmethod
    async def get_user_channels_with_meta(
        session: AsyncSession, user_telegram_id: int
    ) -> List[UserChannelResponse]:
        """Get all user's channels with mailing_enabled and stats."""
        user = await ChannelService._get_user_or_none(session, user_telegram_id)
        if not user:
            return []
        user_channels = await UserChannelRepository.get_by_user_id(session, user.id)
        if not user_channels:
            return []
        channel_ids = [uc.channel_id for uc in user_channels]
        result = await session.execute(
            select(Channel)
            .where(Channel.id.in_(channel_ids))
            .options(selectinload(Channel.avatar))
        )
        channels = {c.id: c for c in result.scalars().all()}
        # Count interactions per channel for this user
        count_result = await session.execute(
            select(Post.channel_id, func.count(Interaction.id).label("cnt"))
            .join(Interaction, Interaction.post_id == Post.id)
            .where(
                Interaction.user_id == user.id,
                Post.channel_id.in_(channel_ids),
                Post.is_deleted == False,
            )
            .group_by(Post.channel_id)
        )
        counts = {row[0]: row[1] for row in count_result.all()}
        out = []
        for uc in user_channels:
            ch = channels.get(uc.channel_id)
            if not ch:
                continue
            out.append(
                UserChannelResponse(
                    id=ch.id,
                    telegram_id=ch.telegram_id,
                    username=ch.username,
                    title=ch.title,
                    is_default=ch.is_default,
                    is_bonus=uc.is_bonus,
                    mailing_enabled=uc.mailing_enabled,
                    posts_received_count=counts.get(ch.id, 0),
                    avatar_telegram_file_id=ch.avatar_telegram_file_id,
                    has_avatar=bool(ch.avatar_telegram_file_id or ch.avatar_photo_bytes),
                    description=ch.description,
                )
            )
        return out

    @staticmethod
    async def get_mailing_recipients(session: AsyncSession, channel_id: int) -> List[int]:
        """Get telegram_id of users who have this channel with mailing_enabled=True and status=active."""
        result = await session.execute(
            select(User.telegram_id)
            .join(UserChannel, UserChannel.user_id == User.id)
            .where(
                UserChannel.channel_id == channel_id,
                UserChannel.mailing_enabled == True,
                User.is_deleted == False,
                User.status == UserStatus.ACTIVE,
            )
        )
        return [row[0] for row in result.all()]

    @staticmethod
    async def set_user_channel_mailing_enabled(
        session: AsyncSession,
        user_telegram_id: int,
        channel_id: int,
        mailing_enabled: bool,
    ) -> Optional[UserChannel]:
        """Set mailing_enabled for a user's channel."""
        user = await ChannelService._get_user_or_none(session, user_telegram_id)
        if not user:
            return None
        return await UserChannelRepository.update_mailing_enabled(
            session, user.id, channel_id, mailing_enabled
        )

    @staticmethod
    async def set_user_all_channels_mailing(
        session: AsyncSession,
        user_telegram_id: int,
        mailing_enabled: bool,
    ) -> int:
        """Set mailing_enabled for all user's channels. Returns count of updated channels."""
        user = await ChannelService._get_user_or_none(session, user_telegram_id)
        if not user:
            return 0
        user_channels = await UserChannelRepository.get_by_user_id(session, user.id)
        for uc in user_channels:
            await UserChannelRepository.update_mailing_enabled(
                session, user.id, uc.channel_id, mailing_enabled
            )
        await session.flush()
        return len(user_channels)

    @staticmethod
    async def remove_user_channel(
        session: AsyncSession,
        user_telegram_id: int,
        channel_id: int,
    ) -> bool:
        """Remove channel from user's subscriptions (unsubscribe). Decrements bonus_channels_count if removed channel was bonus."""
        user = await ChannelService._get_user_or_none(session, user_telegram_id)
        if not user:
            return False
        uc = await UserChannelRepository.get_by_user_and_channel(session, user.id, channel_id)
        if not uc:
            return False
        if uc.is_bonus:
            user.bonus_channels_count = max(0, (user.bonus_channels_count or 0) - 1)
            await session.flush()
        return await UserChannelRepository.delete_by_user_and_channel(
            session, user.id, channel_id
        )

    @staticmethod
    async def get_user_channel_detail(
        session: AsyncSession,
        user_telegram_id: int,
        channel_id: int,
    ) -> Optional[UserChannelResponse]:
        """Get channel detail for user (with mailing_enabled and stats)."""
        user = await ChannelService._get_user_or_none(session, user_telegram_id)
        if not user:
            return None
        uc = await UserChannelRepository.get_by_user_and_channel(session, user.id, channel_id)
        if not uc:
            return None
        channel = await ChannelRepository.get_by_id(session, channel_id)
        if not channel:
            return None
        # Count interactions (posts received / rated) from this channel
        count_result = await session.execute(
            select(func.count(Interaction.id))
            .join(Post, Post.id == Interaction.post_id)
            .where(
                Interaction.user_id == user.id,
                Post.channel_id == channel_id,
                Post.is_deleted == False,
            )
        )
        posts_received_count = count_result.scalar() or 0
        return UserChannelResponse(
            id=channel.id,
            telegram_id=channel.telegram_id,
            username=channel.username,
            title=channel.title,
            is_default=channel.is_default,
            is_bonus=uc.is_bonus,
            mailing_enabled=uc.mailing_enabled,
            posts_received_count=posts_received_count,
            avatar_telegram_file_id=channel.avatar_telegram_file_id,
            has_avatar=bool(channel.avatar_telegram_file_id or channel.avatar_photo_bytes),
            description=channel.description,
        )


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


async def get_users_by_channel(session: AsyncSession, channel_username: str) -> List[dict]:
    """Get all users subscribed to a channel."""
    return await ChannelService.get_users_by_channel(session, channel_username)


async def get_user_channels_with_meta(
    session: AsyncSession, user_telegram_id: int
) -> List[UserChannelResponse]:
    """Get user's channels with mailing_enabled and stats."""
    return await ChannelService.get_user_channels_with_meta(session, user_telegram_id)


async def get_user_channel_detail(
    session: AsyncSession,
    user_telegram_id: int,
    channel_id: int,
) -> Optional[UserChannelResponse]:
    """Get channel detail for user (stats and mailing_enabled)."""
    return await ChannelService.get_user_channel_detail(
        session, user_telegram_id, channel_id
    )


async def set_user_channel_mailing_enabled(
    session: AsyncSession,
    user_telegram_id: int,
    channel_id: int,
    mailing_enabled: bool,
) -> Optional[UserChannel]:
    """Set mailing_enabled for user's channel."""
    return await ChannelService.set_user_channel_mailing_enabled(
        session, user_telegram_id, channel_id, mailing_enabled
    )


async def set_user_all_channels_mailing(
    session: AsyncSession,
    user_telegram_id: int,
    mailing_enabled: bool,
) -> int:
    """Set mailing_enabled for all user's channels. Returns count updated."""
    return await ChannelService.set_user_all_channels_mailing(
        session, user_telegram_id, mailing_enabled
    )


async def remove_user_channel(
    session: AsyncSession,
    user_telegram_id: int,
    channel_id: int,
) -> bool:
    """Remove channel from user's subscriptions."""
    return await ChannelService.remove_user_channel(
        session, user_telegram_id, channel_id
    )


async def get_mailing_recipients(
    session: AsyncSession, channel_id: int
) -> List[int]:
    """Get telegram_ids of users who receive mailing for this channel."""
    return await ChannelService.get_mailing_recipients(session, channel_id)


async def set_channel_avatar_bytes(
    session: AsyncSession, channel_telegram_id: int, avatar_bytes: bytes
) -> bool:
    """Set channel avatar from raw image bytes (by Telegram channel id)."""
    return await ChannelService.set_channel_avatar_bytes(
        session, channel_telegram_id, avatar_bytes
    )


async def set_channel_description(
    session: AsyncSession, channel_telegram_id: int, description: Optional[str]
) -> bool:
    """Set channel description (bio/about) by Telegram channel id."""
    return await ChannelService.set_channel_description(
        session, channel_telegram_id, description
    )


async def get_channel_avatar_bytes(
    session: AsyncSession, channel_id: int
) -> Optional[bytes]:
    """Get channel avatar bytes by channel id."""
    return await ChannelService.get_channel_avatar_bytes(session, channel_id)
