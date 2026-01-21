"""UserLog repository."""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_log import UserLog
from app.models.user import User
from app.schemas import LogCreate


class UserLogRepository:
    """Repository for user log operations."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, log_id: int) -> Optional[UserLog]:
        """Get log entry by ID."""
        result = await db.execute(
            select(UserLog).where(UserLog.id == log_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: int) -> List[UserLog]:
        """Get all log entries for a user."""
        result = await db.execute(
            select(UserLog)
            .join(User)
            .where(
                User.id == user_id,
                User.is_deleted == False
            )
            .order_by(UserLog.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_by_user_telegram_id(
        db: AsyncSession,
        telegram_id: int
    ) -> List[UserLog]:
        """Get all log entries for a user by Telegram ID."""
        result = await db.execute(
            select(UserLog)
            .join(User)
            .where(
                User.telegram_id == telegram_id,
                User.is_deleted == False
            )
            .order_by(UserLog.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def create(db: AsyncSession, log_data: LogCreate, user_id: int) -> UserLog:
        """Create a new log entry (without commit)."""
        log = UserLog(
            user_id=user_id,
            action=log_data.action,
            details=log_data.details,
        )
        db.add(log)
        await db.flush()
        return log
    
    @staticmethod
    async def delete(db: AsyncSession, log_id: int) -> bool:
        """Delete a log entry (without commit)."""
        log = await UserLogRepository.get_by_id(db, log_id)
        if not log:
            return False
        
        await db.delete(log)
        await db.flush()
        return True

