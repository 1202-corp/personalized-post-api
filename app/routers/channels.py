from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.schemas import ChannelCreate, ChannelResponse, UserChannelAdd
from app.services import channel_service

router = APIRouter(prefix="/channels", tags=["channels"])


@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_or_get_channel(
    channel_data: ChannelCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new channel or return existing one."""
    channel, is_new = await channel_service.get_or_create_channel(session, channel_data)
    return channel


@router.get("/defaults", response_model=List[ChannelResponse])
async def get_default_channels(
    session: AsyncSession = Depends(get_session)
):
    """Get all default training channels."""
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
    user_channel = await channel_service.add_user_channel(session, user_channel_data)
    if not user_channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add channel (user/channel not found or already exists)"
        )
    return {"message": "Channel added successfully"}


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
