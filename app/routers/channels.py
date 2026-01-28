from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.schemas import ChannelCreate, ChannelResponse, ChannelUpdate, UserChannelAdd
from app.services import channel_service
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
            "is_active": true,
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
        "is_active": true,
        "created_at": "2024-01-01T10:00:00"
    }
    ```
    """
    channel, is_new = await channel_service.get_or_create_channel(session, channel_data)
    return channel


# ============== Specific endpoints (before parameterized routes) ==============

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
            "is_active": true,
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


# ============== Parameterized routes ==============

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
