"""
Admin API endpoints for management operations.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
import jwt  # pyjwt

from app.database import get_session
from app.models import User, Channel, Post, Interaction, UserChannel, UserRole
from app.config import get_settings

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()
settings = get_settings()


# ============== JWT Functions ==============

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency to get current admin from JWT token."""
    token = credentials.credentials
    payload = verify_token(token, "access")
    return payload


# ============== Request Models ==============

class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserUpdate(BaseModel):
    language: Optional[str] = None
    bonus_channels_count: Optional[int] = None
    user_role: Optional[UserRole] = None


class ChannelUpdate(BaseModel):
    is_default: Optional[bool] = None
    title: Optional[str] = None


# ============== Authentication ==============

@router.post("/auth/login")
async def login(login_data: LoginRequest):
    """Login endpoint for admin dashboard.
    
    Returns access token and refresh token.
    """
    # Verify credentials
    if login_data.username != settings.admin_username or login_data.password != settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Create tokens
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": login_data.username, "username": login_data.username},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": login_data.username, "username": login_data.username}
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/auth/refresh")
async def refresh_token(refresh_data: RefreshTokenRequest):
    """Refresh access token using refresh token."""
    # Verify refresh token
    payload = verify_token(refresh_data.refresh_token, "refresh")
    username = payload.get("username")
    
    # Create new access token
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": username, "username": username},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# ============== Users ==============

@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    trained_only: bool = False,  # Deprecated: use user_role instead
    q: Optional[str] = None,
    user_role: Optional[UserRole] = None,
    db: AsyncSession = Depends(get_session),
    current_admin: dict = Depends(get_current_admin),
):
    """List all users with pagination."""
    from sqlalchemy import select, func, or_
    
    base_query = select(User).where(User.is_deleted == False)
    if trained_only:
        # Deprecated: use user_role instead. For backward compatibility, filter by MEMBER or ADMIN
        base_query = base_query.where(User.user_role.in_([UserRole.MEMBER, UserRole.ADMIN]))
    if user_role:
        base_query = base_query.where(User.user_role == user_role)
    if q:
        q_like = f"%{q}%"
        filters = [
            User.username.ilike(q_like),
            User.first_name.ilike(q_like),
            User.last_name.ilike(q_like),
        ]
        if q.isdigit():
            try:
                tg_id = int(q)
                filters.append(User.telegram_id == tg_id)
            except ValueError:
                pass
        base_query = base_query.where(or_(*filters))
    
    total_query = select(func.count(User.id)).select_from(base_query.subquery())
    total = await db.scalar(total_query)
    
    query = base_query.offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "total": total or 0,
        "skip": skip,
        "limit": limit,
        "users": [
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "username": u.username,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "status": u.status.value,
                "user_role": u.user_role.value,
                "language": u.language,
                "bonus_channels_count": u.bonus_channels_count,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_activity_at": u.last_activity_at.isoformat() if u.last_activity_at else None,
            }
            for u in users
        ],
    }


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    db: AsyncSession = Depends(get_session),
    current_admin: dict = Depends(get_current_admin),
):
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
        "status": user.status.value,
        "user_role": user.user_role.value,
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
    current_admin: dict = Depends(get_current_admin),
):
    """Update user settings."""
    from app.repositories.user_repository import UserRepository
    from app.schemas import UserUpdate as UserUpdateSchema
    
    user = await UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create UserUpdate schema from admin update - only include fields that are actually set
    update_dict = {}
    if update.bonus_channels_count is not None:
        update_dict["bonus_channels_count"] = update.bonus_channels_count
    if update.user_role is not None:
        update_dict["user_role"] = update.user_role
        # When removing admin role, determine role based on previous role
        if user.user_role == UserRole.ADMIN and update.user_role != UserRole.ADMIN:
            # User was admin, now removing admin role
            # If was MEMBER before becoming admin, restore to MEMBER, otherwise GUEST
            # For simplicity, set to MEMBER if they had training (we can't track previous role easily)
            # Actually, just use the provided role
            pass  # Use the provided role
    if update.language is not None:
        update_dict["language"] = update.language
    
    if update_dict:
        user_update = UserUpdateSchema(**update_dict)
        updated_user = await UserRepository.update(db, user.telegram_id, user_update)
    
    await db.commit()
    return {"status": "updated", "user_id": user_id}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_session),
    hard: bool = False,
    current_admin: dict = Depends(get_current_admin),
):
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
    current_admin: dict = Depends(get_current_admin),
):
    """List all channels with stats."""
    from app.repositories.channel_repository import ChannelRepository
    from app.repositories.post_repository import PostRepository
    from app.config import get_settings
    from sqlalchemy import select, func
    from datetime import datetime, timezone, timedelta
    
    settings = get_settings()
    ttl_hours = settings.training_metadata_ttl_hours
    
    # Get all channels with soft delete filter
    all_channels = await ChannelRepository.get_all(db)
    channels = all_channels[skip:skip + limit]
    
    total = len(all_channels)
    
    # Get post counts and TTL info for each channel
    channels_with_stats = []
    now = datetime.now(timezone.utc)
    
    for channel in channels:
        posts = await PostRepository.get_all_by_channel(db, channel.id)
        
        # Calculate remaining TTL for posts
        # Find the oldest post's created_at time (this determines when TTL expires)
        posts_ttl_remaining_seconds = None
        if posts:
            # Filter posts with created_at and find the oldest one
            posts_with_created = [p for p in posts if p.created_at]
            if posts_with_created:
                oldest_post_created = min(p.created_at for p in posts_with_created)
                # Calculate when TTL expires (created_at + TTL hours)
                ttl_expires_at = oldest_post_created.replace(tzinfo=timezone.utc) + timedelta(hours=ttl_hours)
                # Calculate remaining time
                remaining = (ttl_expires_at - now).total_seconds()
                posts_ttl_remaining_seconds = max(0, int(remaining)) if remaining > 0 else 0
        
        channels_with_stats.append({
            "id": channel.id,
            "telegram_id": channel.telegram_id,
            "username": channel.username,
            "title": channel.title,
            "is_default": channel.is_default,
            "posts_count": len(posts),
            "posts_ttl_remaining_seconds": posts_ttl_remaining_seconds,
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
    current_admin: dict = Depends(get_current_admin),
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
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_session),
    hard: bool = False,
    current_admin: dict = Depends(get_current_admin),
):
    """Delete a channel and its posts."""
    from app.repositories.channel_repository import ChannelRepository
    
    channel = await ChannelRepository.delete(db, channel_id, hard=hard)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    await db.commit()
    return {"status": "deleted", "channel_id": channel_id}


# ============== System ==============

@router.post("/reset-training/{user_id}")
async def reset_user_training(
    user_id: int,
    db: AsyncSession = Depends(get_session),
    current_admin: dict = Depends(get_current_admin),
):
    """Reset training status for a user."""
    from app.repositories.user_repository import UserRepository
    from app.repositories.interaction_repository import InteractionRepository
    from app.schemas import UserUpdate
    
    user = await UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user status - reset to GUEST role
    user.user_role = UserRole.GUEST
    user.initial_best_post_sent = False
    
    # Delete their interactions
    interactions = await InteractionRepository.get_by_user_id(db, user.id)
    for interaction in interactions:
        await InteractionRepository.delete(db, interaction.id)
    
    await db.commit()
    return {"status": "training_reset", "user_id": user_id}


@router.post("/clear-all-data")
async def clear_all_data(
    confirm: bool = False,
    db: AsyncSession = Depends(get_session),
    current_admin: dict = Depends(get_current_admin),
):
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
    db: AsyncSession = Depends(get_session),
    current_admin: dict = Depends(get_current_admin),
):
    """Recalculate post clusters for optimized search.
    
    This will group similar posts together based on their embeddings,
    allowing faster search by filtering through clusters first.
    
    Forwards request to ML Service.
    """
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                "http://ml-service:8002/api/v1/clusters/recalculate",
                json={"n_clusters": n_clusters}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error recalculating clusters: {str(e)}"
        )


@router.get("/clusters/stats")
async def get_cluster_stats(
    db: AsyncSession = Depends(get_session),
    current_admin: dict = Depends(get_current_admin),
):
    """Get statistics about current post clusters.
    
    Forwards request to ML Service.
    """
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://ml-service:8002/api/v1/clusters/stats")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cluster stats: {str(e)}"
        )
