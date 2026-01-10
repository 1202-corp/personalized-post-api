from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, UserLog, UserStatus
from app.schemas import UserCreate, UserUpdate, LogCreate


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Get user by Telegram ID."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, user_data: UserCreate) -> User:
    """Create a new user."""
    user = User(
        telegram_id=user_data.telegram_id,
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        status=UserStatus.NEW,
    )
    session.add(user)
    await session.flush()
    return user


async def get_or_create_user(session: AsyncSession, user_data: UserCreate) -> tuple[User, bool]:
    """Get existing user or create new one. Returns (user, is_new)."""
    user = await get_user_by_telegram_id(session, user_data.telegram_id)
    if user:
        return user, False
    user = await create_user(session, user_data)
    return user, True


async def update_user(session: AsyncSession, telegram_id: int, user_update: UserUpdate) -> Optional[User]:
    """Update user fields."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None
    
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await session.flush()
    return user


async def update_user_activity(session: AsyncSession, telegram_id: int) -> bool:
    """Update user's last activity timestamp."""
    result = await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(last_activity_at=datetime.utcnow())
    )
    return result.rowcount > 0


async def get_inactive_users(
    session: AsyncSession,
    since: datetime,
    statuses: List[UserStatus] = None
) -> List[User]:
    """Get users who have been inactive since given time."""
    query = select(User).where(User.last_activity_at < since)
    if statuses:
        query = query.where(User.status.in_(statuses))
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_log(session: AsyncSession, log_data: LogCreate) -> UserLog:
    """Create a user activity log entry."""
    user = await get_user_by_telegram_id(session, log_data.user_telegram_id)
    if not user:
        raise ValueError(f"User with telegram_id {log_data.user_telegram_id} not found")
    
    log = UserLog(
        user_id=user.id,
        action=log_data.action,
        details=log_data.details,
    )
    session.add(log)
    await session.flush()
    return log


async def get_users_by_statuses(
    session: AsyncSession,
    statuses: List[UserStatus]
) -> List[User]:
    """Get users whose status is in the provided list."""
    query = select(User).where(User.status.in_(statuses))
    result = await session.execute(query)
    return list(result.scalars().all())
