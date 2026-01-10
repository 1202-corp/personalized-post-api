from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import Channel, UserChannel, User
from app.schemas import ChannelCreate, UserChannelAdd
from app.config import get_settings

settings = get_settings()


async def get_channel_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[Channel]:
    """Get channel by Telegram ID."""
    result = await session.execute(
        select(Channel).where(Channel.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_channel_by_username(session: AsyncSession, username: str) -> Optional[Channel]:
    """Get channel by username."""
    # Normalize username
    username = username.lstrip("@").lower()
    result = await session.execute(
        select(Channel).where(Channel.username.ilike(username))
    )
    return result.scalar_one_or_none()


async def create_channel(session: AsyncSession, channel_data: ChannelCreate) -> Channel:
    """Create a new channel."""
    # Determine if this channel should be treated as a default training channel
    default_usernames = [
        u.lstrip("@").lower()
        for u in settings.default_training_channels.split(",")
        if u.strip()
    ]
    username_normalized = (channel_data.username or "").lstrip("@").lower()
    is_default = channel_data.is_default or username_normalized in default_usernames

    channel = Channel(
        telegram_id=channel_data.telegram_id,
        username=channel_data.username,
        title=channel_data.title,
        is_default=is_default,
    )
    session.add(channel)
    await session.flush()
    return channel


async def get_or_create_channel(session: AsyncSession, channel_data: ChannelCreate) -> tuple[Channel, bool]:
    """Get existing channel or create new one. Returns (channel, is_new)."""
    channel = await get_channel_by_telegram_id(session, channel_data.telegram_id)
    if channel:
        return channel, False
    channel = await create_channel(session, channel_data)
    return channel, True


async def get_default_channels(session: AsyncSession) -> List[Channel]:
    """Get all default training channels.

    Primary source is channels explicitly marked as default.
    If none are marked yet, we fall back to channels whose usernames
    are listed in settings.default_training_channels and mark them
    as default for subsequent calls.
    """
    result = await session.execute(
        select(Channel).where(Channel.is_default == True, Channel.is_active == True)
    )
    channels = list(result.scalars().all())
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
    result = await session.execute(
        select(Channel).where(
            Channel.is_active == True,
            func.lower(Channel.username).in_(default_usernames),
        )
    )
    channels = list(result.scalars().all())

    # Mark them as default so next call sees them without fallback
    if channels:
        for ch in channels:
            ch.is_default = True
        await session.flush()

    return channels


async def add_user_channel(
    session: AsyncSession, 
    user_channel_data: UserChannelAdd
) -> Optional[UserChannel]:
    """Associate a channel with a user."""
    # Get user
    user_result = await session.execute(
        select(User).where(User.telegram_id == user_channel_data.user_telegram_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return None
    
    # Get channel
    channel = await get_channel_by_username(session, user_channel_data.channel_username)
    if not channel:
        return None
    
    # Check if association exists
    existing = await session.execute(
        select(UserChannel).where(
            UserChannel.user_id == user.id,
            UserChannel.channel_id == channel.id
        )
    )
    if existing.scalar_one_or_none():
        return None
    
    user_channel = UserChannel(
        user_id=user.id,
        channel_id=channel.id,
        is_for_training=user_channel_data.is_for_training,
        is_bonus=user_channel_data.is_bonus,
    )
    session.add(user_channel)
    await session.flush()
    return user_channel


async def get_user_training_channels(session: AsyncSession, user_telegram_id: int) -> List[Channel]:
    """Get all channels user is using for training."""
    result = await session.execute(
        select(Channel)
        .join(UserChannel)
        .join(User)
        .where(
            User.telegram_id == user_telegram_id,
            UserChannel.is_for_training == True
        )
    )
    return list(result.scalars().all())


async def get_user_channels(session: AsyncSession, user_telegram_id: int) -> List[Channel]:
    """Get all channels associated with user."""
    result = await session.execute(
        select(Channel)
        .join(UserChannel)
        .join(User)
        .where(User.telegram_id == user_telegram_id)
    )
    return list(result.scalars().all())
