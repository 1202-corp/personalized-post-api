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
    from app.repositories.user_repository import UserRepository
    from sqlalchemy import select, func
    
    query = select(User).where(User.is_deleted == False).offset(skip).limit(limit)
    if trained_only:
        query = query.where(User.is_trained == True)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    total_query = select(func.count(User.id)).where(User.is_deleted == False)
    total = await db.scalar(total_query)
    
    return {
        "total": total or 0,
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
    from app.repositories.user_repository import UserRepository
    from app.repositories.user_channel_repository import UserChannelRepository
    from app.repositories.interaction_repository import InteractionRepository
    from app.models.interaction import InteractionType
    
    user = await UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's channels
    user_channels = await UserChannelRepository.get_by_user_id(db, user.id)
    channel_ids = [uc.channel_id for uc in user_channels]
    channels = []
    for channel_id in channel_ids:
        from app.repositories.channel_repository import ChannelRepository
        channel = await ChannelRepository.get_by_id(db, channel_id)
        if channel:
            channels.append(channel)
    
    # Get interaction stats
    interactions = await InteractionRepository.get_by_user_id(db, user.id)
    likes = [i for i in interactions if i.interaction_type == InteractionType.LIKE]
    
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
            "total_interactions": len(interactions),
            "likes": len(likes),
        },
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    update: UserUpdate,
    db: AsyncSession = Depends(get_session),
):
    """Update user settings."""
    from app.repositories.user_repository import UserRepository
    from app.schemas import UserUpdate as UserUpdateSchema
    from app.models.user import UserStatus
    
    user = await UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create UserUpdate schema from admin update
    user_update = UserUpdateSchema(
        is_trained=update.is_trained,
        bonus_channels_count=update.bonus_channels_count
    )
    updated_user = await UserRepository.update(db, user.telegram_id, user_update)
    
    if update.language is not None:
        user.language = update.language
    
    await db.commit()
    return {"status": "updated", "user_id": user_id}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_session), hard: bool = False):
    """Delete a user and their data."""
    from app.repositories.user_repository import UserRepository
    
    user = await UserRepository.delete(db, user_id, hard=hard)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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
    from app.repositories.channel_repository import ChannelRepository
    from app.repositories.post_repository import PostRepository
    from sqlalchemy import select, func
    
    # Get all channels with soft delete filter
    all_channels = await ChannelRepository.get_all(db)
    channels = all_channels[skip:skip + limit]
    
    total = len(all_channels)
    
    # Get post counts for each channel
    channels_with_stats = []
    for channel in channels:
        posts = await PostRepository.get_all_by_channel(db, channel.id)
        channels_with_stats.append({
            "id": channel.id,
            "telegram_id": channel.telegram_id,
            "username": channel.username,
            "title": channel.title,
            "is_default": channel.is_default,
            "posts_count": len(posts),
        })
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "channels": channels_with_stats,
    }


@router.patch("/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    update: ChannelUpdate,
    db: AsyncSession = Depends(get_session),
):
    """Update channel settings."""
    from app.repositories.channel_repository import ChannelRepository
    
    channel = await ChannelRepository.get_by_id(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    updated_channel = await ChannelRepository.update(
        db, 
        channel_id,
        is_default=update.is_default if update.is_default is not None else channel.is_default,
        title=update.title if update.title is not None else channel.title
    )
    
    await db.commit()
    return {"status": "updated", "channel_id": channel_id}


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_session), hard: bool = False):
    """Delete a channel and its posts."""
    from app.repositories.channel_repository import ChannelRepository
    
    channel = await ChannelRepository.delete(db, channel_id, hard=hard)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    await db.commit()
    return {"status": "deleted", "channel_id": channel_id}


# ============== System ==============

@router.post("/reset-training/{user_id}")
async def reset_user_training(user_id: int, db: AsyncSession = Depends(get_session)):
    """Reset training status for a user."""
    from app.repositories.user_repository import UserRepository
    from app.repositories.interaction_repository import InteractionRepository
    from app.schemas import UserUpdate
    
    user = await UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user status
    user.is_trained = False
    user.initial_best_post_sent = False
    
    # Delete their interactions
    interactions = await InteractionRepository.get_by_user_id(db, user.id)
    for interaction in interactions:
        await InteractionRepository.delete(db, interaction.id)
    
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


@router.post("/clusters/recalculate")
async def recalculate_clusters(
    n_clusters: int = 50,
    db: AsyncSession = Depends(get_session)
):
    """Recalculate post clusters for optimized search.
    
    This will group similar posts together based on their embeddings,
    allowing faster search by filtering through clusters first.
    """
    from app.services import cluster_service
    
    try:
        result = await cluster_service.recalculate_clusters(db, n_clusters=n_clusters)
        await db.commit()
        return result
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error recalculating clusters: {str(e)}"
        )


@router.get("/clusters/stats")
async def get_cluster_stats(db: AsyncSession = Depends(get_session)):
    """Get statistics about current post clusters."""
    from sqlalchemy import func, select
    from app.models.post import Post
    
    # Get cluster distribution
    result = await db.execute(
        select(Post.cluster_id, func.count(Post.id).label("count"))
        .where(Post.is_deleted == False, Post.cluster_id.isnot(None))
        .group_by(Post.cluster_id)
    )
    cluster_counts = result.all()
    
    # Get total stats
    total_posts = await db.scalar(
        select(func.count(Post.id)).where(Post.is_deleted == False)
    )
    clustered_posts = await db.scalar(
        select(func.count(Post.id)).where(
            Post.is_deleted == False,
            Post.cluster_id.isnot(None)
        )
    )
    unclustered_posts = (total_posts or 0) - (clustered_posts or 0)
    
    return {
        "total_posts": total_posts or 0,
        "clustered_posts": clustered_posts or 0,
        "unclustered_posts": unclustered_posts,
        "num_clusters": len(cluster_counts),
        "cluster_distribution": [
            {"cluster_id": row[0], "post_count": row[1]} 
            for row in cluster_counts
        ]
    }
