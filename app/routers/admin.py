"""
Admin API endpoints for management operations.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import User, Channel, Post, Interaction, UserChannel

router = APIRouter(prefix="/admin", tags=["admin"])


# ============== Request Models ==============

class UserUpdate(BaseModel):
    is_trained: Optional[bool] = None
    language: Optional[str] = None
    bonus_channels_count: Optional[int] = None


class ChannelUpdate(BaseModel):
    is_default: Optional[bool] = None
    title: Optional[str] = None


# ============== Users ==============

@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    trained_only: bool = False,
    db: AsyncSession = Depends(get_session),
):
    """List all users with pagination."""
    query = select(User).offset(skip).limit(limit)
    if trained_only:
        query = query.where(User.is_trained == True)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    total = await db.scalar(select(func.count(User.id)))
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "users": [
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "username": u.username,
                "is_trained": u.is_trained,
                "language": u.language,
                "bonus_channels_count": u.bonus_channels_count,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_activity_at": u.last_activity_at.isoformat() if u.last_activity_at else None,
            }
            for u in users
        ],
    }


@router.get("/users/{user_id}")
async def get_user_details(user_id: int, db: AsyncSession = Depends(get_session)):
    """Get detailed user information."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's channels
    channels_query = (
        select(Channel)
        .join(UserChannel, UserChannel.channel_id == Channel.id)
        .where(UserChannel.user_id == user.id)
    )
    result = await db.execute(channels_query)
    channels = result.scalars().all()
    
    # Get interaction stats
    interactions = await db.scalar(
        select(func.count(Interaction.id)).where(Interaction.user_id == user.id)
    )
    likes = await db.scalar(
        select(func.count(Interaction.id)).where(
            Interaction.user_id == user.id,
            Interaction.interaction_type == "LIKE"
        )
    )
    
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "is_trained": user.is_trained,
        "language": user.language,
        "bonus_channels_count": user.bonus_channels_count,
        "initial_best_post_sent": user.initial_best_post_sent,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_activity_at": user.last_activity_at.isoformat() if user.last_activity_at else None,
        "channels": [{"id": c.id, "username": c.username, "title": c.title} for c in channels],
        "stats": {
            "total_interactions": interactions or 0,
            "likes": likes or 0,
        },
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    update: UserUpdate,
    db: AsyncSession = Depends(get_session),
):
    """Update user settings."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if update.is_trained is not None:
        user.is_trained = update.is_trained
    if update.language is not None:
        user.language = update.language
    if update.bonus_channels_count is not None:
        user.bonus_channels_count = update.bonus_channels_count
    
    await db.commit()
    return {"status": "updated", "user_id": user_id}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_session)):
    """Delete a user and their data."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete related data
    await db.execute(delete(Interaction).where(Interaction.user_id == user.id))
    await db.execute(delete(UserChannel).where(UserChannel.user_id == user.id))
    await db.delete(user)
    await db.commit()
    
    return {"status": "deleted", "user_id": user_id}


# ============== Channels ==============

@router.get("/channels")
async def list_channels(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_session),
):
    """List all channels with stats."""
    query = (
        select(
            Channel,
            func.count(Post.id).label("posts_count"),
        )
        .outerjoin(Post, Post.channel_id == Channel.id)
        .group_by(Channel.id)
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(query)
    channels = result.all()
    
    total = await db.scalar(select(func.count(Channel.id)))
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "channels": [
            {
                "id": c.Channel.id,
                "telegram_id": c.Channel.telegram_id,
                "username": c.Channel.username,
                "title": c.Channel.title,
                "is_default": c.Channel.is_default,
                "posts_count": c.posts_count,
            }
            for c in channels
        ],
    }


@router.patch("/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    update: ChannelUpdate,
    db: AsyncSession = Depends(get_session),
):
    """Update channel settings."""
    channel = await db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if update.is_default is not None:
        channel.is_default = update.is_default
    if update.title is not None:
        channel.title = update.title
    
    await db.commit()
    return {"status": "updated", "channel_id": channel_id}


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_session)):
    """Delete a channel and its posts."""
    channel = await db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Delete posts first
    await db.execute(delete(Post).where(Post.channel_id == channel.id))
    await db.execute(delete(UserChannel).where(UserChannel.channel_id == channel.id))
    await db.delete(channel)
    await db.commit()
    
    return {"status": "deleted", "channel_id": channel_id}


# ============== System ==============

@router.post("/reset-training/{user_id}")
async def reset_user_training(user_id: int, db: AsyncSession = Depends(get_session)):
    """Reset training status for a user."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_trained = False
    user.initial_best_post_sent = False
    
    # Delete their interactions
    await db.execute(delete(Interaction).where(Interaction.user_id == user.id))
    await db.commit()
    
    return {"status": "training_reset", "user_id": user_id}


@router.post("/clear-all-data")
async def clear_all_data(confirm: bool = False, db: AsyncSession = Depends(get_session)):
    """Clear all data from the database. Requires confirm=true."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Set confirm=true to clear all data"
        )
    
    await db.execute(delete(Interaction))
    await db.execute(delete(UserChannel))
    await db.execute(delete(Post))
    await db.execute(delete(Channel))
    await db.execute(delete(User))
    await db.commit()
    
    return {"status": "all_data_cleared"}
