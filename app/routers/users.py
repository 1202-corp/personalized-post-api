from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserActivityUpdate,
    LogCreate,
    LogResponse,
    UserFeedTargetResponse,
    LanguageUpdate,
    LanguageResponse,
)
from app.services import user_service
from app.models import UserStatus

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_or_get_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new user or return existing one."""
    user, is_new = await user_service.get_or_create_user(session, user_data)
    return user


@router.post("/activity", status_code=status.HTTP_204_NO_CONTENT)
async def update_activity(
    activity_data: UserActivityUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update user's last activity timestamp."""
    success = await user_service.update_user_activity(session, activity_data.telegram_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )


@router.post("/logs", response_model=LogResponse, status_code=status.HTTP_201_CREATED)
async def create_log(
    log_data: LogCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a user activity log entry."""
    try:
        log = await user_service.create_log(session, log_data)
        return log
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/feed-targets", response_model=List[UserFeedTargetResponse])
async def get_feed_targets(
    session: AsyncSession = Depends(get_session)
):
    """Get users eligible for feed auto-delivery (trained or active)."""
    users = await user_service.get_users_by_statuses(
        session,
        [UserStatus.TRAINED, UserStatus.ACTIVE],
    )
    return users


@router.get("/inactive", response_model=List[UserResponse])
async def get_inactive_users(
    silence_threshold: int = 600,
    session: AsyncSession = Depends(get_session)
):
    """Get users who have been inactive for longer than silence_threshold seconds."""
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(seconds=silence_threshold)
    users = await user_service.get_inactive_users(
        session,
        since,
        [UserStatus.TRAINED, UserStatus.ACTIVE]
    )
    return users


@router.get("/{telegram_id}", response_model=UserResponse)
async def get_user(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get user by Telegram ID."""
    user = await user_service.get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.patch("/{telegram_id}", response_model=UserResponse)
async def update_user(
    telegram_id: int,
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update user fields."""
    user = await user_service.update_user(session, telegram_id, user_update)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.get("/{telegram_id}/language", response_model=LanguageResponse)
async def get_user_language(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get user's preferred language."""
    user = await user_service.get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return LanguageResponse(language=user.language or "en")


@router.put("/{telegram_id}/language", status_code=status.HTTP_204_NO_CONTENT)
async def set_user_language(
    telegram_id: int,
    language_data: LanguageUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Set user's preferred language."""
    user = await user_service.get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    user.language = language_data.language
    await session.flush()


@router.post("/{telegram_id}/nudge-sent", status_code=status.HTTP_204_NO_CONTENT)
async def mark_nudge_sent(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Mark that a nudge was sent to user."""
    from datetime import datetime
    user = await user_service.get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    user.last_nudge_at = datetime.utcnow()
    await session.flush()


@router.post("/{telegram_id}/training-complete", status_code=status.HTTP_200_OK)
async def mark_training_complete(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Mark user training as complete (called from MiniApp).
    
    Always publishes event to Redis so main-bot can send completion message.
    """
    import json
    import logging
    import redis.asyncio as aioredis
    
    user = await user_service.get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update status to TRAINED if currently in TRAINING
    if user.status == UserStatus.TRAINING:
        user.status = UserStatus.TRAINED
        user.is_trained = True
        await session.commit()
    
    # Always notify main-bot via Redis pub/sub (even if already trained)
    notified = False
    try:
        redis_client = aioredis.from_url("redis://redis:6379/0")
        result = await redis_client.publish(
            "ppb:training_complete",
            json.dumps({"telegram_id": telegram_id, "chat_id": telegram_id})
        )
        await redis_client.close()
        notified = result > 0
        logging.info(f"Published training_complete for {telegram_id}, subscribers: {result}")
    except Exception as e:
        logging.error(f"Failed to notify bot via Redis: {e}")
    
    return {"status": "ok", "user_status": user.status.value, "notified": notified}
