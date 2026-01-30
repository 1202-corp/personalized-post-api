from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.schemas import (
    ChannelCreate,
    ChannelResponse,
    ChannelUpdate,
    UserChannelAdd,
    UserChannelResponse,
    MailingRecipientsResponse,
    MailingToggleRequest,
    ChannelDescriptionUpdate,
    ChannelsNeedRefreshRequest,
    ChannelsNeedRefreshResponse,
)
from app.services import channel_service
from app.services import post_service
from app.repositories.channel_repository import ChannelRepository

router = APIRouter(prefix="/channels", tags=["channels"])


# ============== List/Create ==============

@router.get("/", response_model=List[ChannelResponse])
async def list_channels(
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session)
):
    """
    List all channels with pagination.
    
    Returns a paginated list of all channels in the system.
    
    **Parameters:**
    - `skip`: Number of channels to skip (default: 0)
    - `limit`: Maximum number of channels to return (default: 50)
    
    **Example Request:**
    ```
    GET /api/v1/channels/?skip=0&limit=10
    ```
    
    **Example Response:**
    ```json
    [
        {
            "id": 1,
            "telegram_id": -1001234567890,
            "username": "example_channel",
            "title": "Example Channel",
            "is_default": false,
            "created_at": "2024-01-01T10:00:00"
        }
    ]
    ```
    """
    from app.repositories.channel_repository import ChannelRepository
    channels = await ChannelRepository.get_all(session)
    paginated_channels = channels[skip:skip + limit]
    return paginated_channels


@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_or_get_channel(
    channel_data: ChannelCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Create a new channel or return existing one.
    
    If a channel with the given `telegram_id` already exists, returns the existing channel.
    Otherwise, creates a new channel. Channels matching `default_training_channels` config
    are automatically marked as default.
    
    **Request Body:**
    ```json
    {
        "telegram_id": -1001234567890,
        "username": "example_channel",
        "title": "Example Channel",
        "is_default": false
    }
    ```
    
    **Example Response:**
    ```json
    {
        "id": 1,
        "telegram_id": -1001234567890,
        "username": "example_channel",
        "title": "Example Channel",
        "is_default": false,
        "created_at": "2024-01-01T10:00:00"
    }
    ```
    """
    channel, is_new = await channel_service.get_or_create_channel(session, channel_data)
    return channel


# ============== Specific endpoints (before parameterized routes) ==============

@router.post("/need-refresh", response_model=ChannelsNeedRefreshResponse)
async def channels_need_refresh(
    body: ChannelsNeedRefreshRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Return which channel usernames need scraping (not in DB or metadata older than TTL).
    Main-bot uses this before "Start training" to skip scrape when posts are already fresh.
    """
    need = await post_service.get_channel_usernames_needing_refresh(session, body.channel_usernames)
    return ChannelsNeedRefreshResponse(channel_usernames=need)


@router.get("/defaults", response_model=List[ChannelResponse])
async def get_default_channels(
    session: AsyncSession = Depends(get_session)
):
    """
    Get all default training channels.
    
    Returns channels marked as default for training. These are used
    when users start training without specifying channels.
    
    **Example Request:**
    ```
    GET /api/v1/channels/defaults
    ```
    
    **Example Response:**
    ```json
    [
        {
            "id": 1,
            "telegram_id": -1001234567890,
            "username": "durov",
            "title": "Durov's Channel",
            "is_default": true,
            "created_at": "2024-01-01T10:00:00"
        }
    ]
    ```
    """
    channels = await channel_service.get_default_channels(session)
    return channels


@router.get("/by-username/{username}", response_model=ChannelResponse)
async def get_channel_by_username(
    username: str,
    session: AsyncSession = Depends(get_session)
):
    """Get channel by username."""
    channel = await channel_service.get_channel_by_username(session, username)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    return channel


@router.post("/user-channel", status_code=status.HTTP_201_CREATED)
async def add_user_channel(
    user_channel_data: UserChannelAdd,
    session: AsyncSession = Depends(get_session)
):
    """Associate a channel with a user."""
    from app.exceptions import NotFoundError, ValidationError
    try:
        channel = await channel_service.add_user_channel(session, user_channel_data)
        return {"message": "Channel added successfully"}
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/user/{telegram_id}/training", response_model=List[ChannelResponse])
async def get_user_training_channels(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get user's training channels."""
    channels = await channel_service.get_user_training_channels(session, telegram_id)
    return channels


@router.get("/user/{telegram_id}", response_model=List[ChannelResponse])
async def get_user_channels(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get all channels associated with a user."""
    channels = await channel_service.get_user_channels(session, telegram_id)
    return channels


@router.get("/{channel_username}/users")
async def get_users_by_channel(
    channel_username: str,
    session: AsyncSession = Depends(get_session)
):
    """Get all users subscribed to a channel."""
    users = await channel_service.get_users_by_channel(session, channel_username)
    return users


@router.get("/user/{telegram_id}/channels/with-meta", response_model=List[UserChannelResponse])
async def get_user_channels_with_meta(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get user's channels with mailing_enabled and stats (posts_received_count)."""
    items = await channel_service.get_user_channels_with_meta(session, telegram_id)
    return items


@router.get("/user/{telegram_id}/channels/{channel_id}/detail", response_model=UserChannelResponse)
async def get_user_channel_detail(
    telegram_id: int,
    channel_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get channel detail for user (stats and mailing_enabled)."""
    detail = await channel_service.get_user_channel_detail(session, telegram_id, channel_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found or user not subscribed"
        )
    return detail


@router.patch("/user/{telegram_id}/channels/mailing-all", response_model=dict)
async def patch_user_all_channels_mailing(
    telegram_id: int,
    body: MailingToggleRequest,
    session: AsyncSession = Depends(get_session)
):
    """Set mailing_enabled for all user's channels at once."""
    count = await channel_service.set_user_all_channels_mailing(
        session, telegram_id, body.mailing_enabled
    )
    await session.commit()
    return {"updated_count": count, "mailing_enabled": body.mailing_enabled}


@router.patch("/user/{telegram_id}/channels/{channel_id}", response_model=dict)
async def patch_user_channel_mailing(
    telegram_id: int,
    channel_id: int,
    body: MailingToggleRequest,
    session: AsyncSession = Depends(get_session)
):
    """Toggle mailing_enabled for user's channel."""
    uc = await channel_service.set_user_channel_mailing_enabled(
        session, telegram_id, channel_id, body.mailing_enabled
    )
    if not uc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User channel not found"
        )
    await session.commit()
    return {"mailing_enabled": uc.mailing_enabled}


@router.delete("/user/{telegram_id}/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_channel(
    telegram_id: int,
    channel_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Remove channel from user's subscriptions (unsubscribe)."""
    removed = await channel_service.remove_user_channel(session, telegram_id, channel_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User channel not found"
        )
    await session.commit()


# ============== Parameterized routes ==============

@router.get("/by-telegram-id/{channel_telegram_id}/mailing-recipients", response_model=MailingRecipientsResponse)
async def get_channel_mailing_recipients_by_telegram_id(
    channel_telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get telegram_ids of users who receive mailing for this channel (by Telegram channel id)."""
    channel = await channel_service.get_channel_by_telegram_id(session, channel_telegram_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    telegram_ids = await channel_service.get_mailing_recipients(session, channel.id)
    return MailingRecipientsResponse(telegram_ids=telegram_ids)


@router.post("/by-telegram-id/{channel_telegram_id}/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def set_channel_avatar_by_telegram_id(
    channel_telegram_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """Set channel avatar from raw image bytes (by Telegram channel id). Body = image bytes."""
    body = await request.body()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty body")
    updated = await channel_service.set_channel_avatar_bytes(session, channel_telegram_id, body)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    await session.commit()


@router.patch("/by-telegram-id/{channel_telegram_id}/description", status_code=status.HTTP_204_NO_CONTENT)
async def set_channel_description_by_telegram_id(
    channel_telegram_id: int,
    body: ChannelDescriptionUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Set channel description (bio/about) by Telegram channel id. Body = { \"description\": \"...\" }."""
    updated = await channel_service.set_channel_description(
        session, channel_telegram_id, body.description
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    await session.commit()


@router.get("/{channel_id}/mailing-recipients", response_model=MailingRecipientsResponse)
async def get_channel_mailing_recipients(
    channel_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get telegram_ids of users who receive mailing for this channel."""
    telegram_ids = await channel_service.get_mailing_recipients(session, channel_id)
    return MailingRecipientsResponse(telegram_ids=telegram_ids)


@router.get("/{channel_id}/avatar")
async def get_channel_avatar(
    channel_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get channel avatar image bytes. Returns 404 if no avatar."""
    avatar_bytes = await channel_service.get_channel_avatar_bytes(session, channel_id)
    if not avatar_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")
    return Response(content=avatar_bytes, media_type="image/jpeg")


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get channel by ID."""
    from app.repositories.channel_repository import ChannelRepository
    channel = await ChannelRepository.get_by_id(session, channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    return channel


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: int,
    channel_update: ChannelUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update channel fields."""
    update_data = channel_update.model_dump(exclude_unset=True)
    channel = await ChannelRepository.update(session, channel_id, **update_data)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    await session.commit()
    await session.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: int,
    hard: bool = False,
    session: AsyncSession = Depends(get_session)
):
    """Delete a channel (soft delete by default, hard delete if hard=true)."""
    channel = await ChannelRepository.delete(session, channel_id, hard=hard)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    await session.commit()
