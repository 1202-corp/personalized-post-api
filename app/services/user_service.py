"""User business logic service."""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserStatus
from app.repositories.user_repository import UserRepository
from app.repositories.user_log_repository import UserLogRepository
from app.schemas import UserCreate, UserUpdate, LogCreate
from app.exceptions import NotFoundError, ValidationError
from app.logging_config import get_logger

logger = get_logger(__name__)


class UserService:
    """Service for user operations."""
    
    @staticmethod
    async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        return await UserRepository.get_by_telegram_id(session, telegram_id)
    
    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return await UserRepository.get_by_id(session, user_id)
    
    @staticmethod
    async def create_user(session: AsyncSession, user_data: UserCreate) -> User:
        """Create a new user."""
        try:
            user = await UserRepository.create(session, user_data)
            await session.commit()
            await session.refresh(user)
            logger.info(
                "user_created",
                user_id=user.id,
                telegram_id=user.telegram_id,
                username=user.username
            )
            return user
        except Exception as e:
            await session.rollback()
            logger.error("user_creation_failed", error=str(e), exc_info=True)
            raise
    
    @staticmethod
    async def get_or_create_user(session: AsyncSession, user_data: UserCreate) -> tuple[User, bool]:
        """Get existing user or create new one. Returns (user, is_new)."""
        try:
            user, is_new = await UserRepository.get_or_create(session, user_data)
            await session.commit()
            if is_new:
                await session.refresh(user)
                logger.info("user_created", user_id=user.id, telegram_id=user.telegram_id)
            return user, is_new
        except Exception as e:
            await session.rollback()
            logger.error("get_or_create_user_failed", error=str(e), exc_info=True)
            raise
    
    @staticmethod
    async def update_user(session: AsyncSession, telegram_id: int, user_update: UserUpdate) -> Optional[User]:
        """Update user fields."""
        try:
            user = await UserRepository.update(session, telegram_id, user_update)
            if user:
                await session.commit()
                await session.refresh(user)
                logger.info("user_updated", user_id=user.id, telegram_id=telegram_id)
            return user
        except Exception as e:
            await session.rollback()
            logger.error("user_update_failed", error=str(e), telegram_id=telegram_id, exc_info=True)
            raise
    
    @staticmethod
    async def update_user_activity(session: AsyncSession, telegram_id: int) -> bool:
        """Update user's last activity timestamp."""
        try:
            result = await UserRepository.update_activity(session, telegram_id)
            if result:
                await session.commit()
            return result
        except Exception as e:
            await session.rollback()
            logger.error("update_activity_failed", error=str(e), telegram_id=telegram_id, exc_info=True)
            raise
    
    @staticmethod
    async def get_inactive_users(
        session: AsyncSession,
        since: datetime,
        statuses: Optional[List[UserStatus]] = None
    ) -> List[User]:
        """Get users who have been inactive since given time."""
        return await UserRepository.get_inactive_users(session, since, statuses)
    
    @staticmethod
    async def get_users_by_statuses(
        session: AsyncSession,
        statuses: List[UserStatus]
    ) -> List[User]:
        """Get users whose status is in the provided list."""
        return await UserRepository.get_by_statuses(session, statuses)
    
    @staticmethod
    async def create_log(session: AsyncSession, log_data: LogCreate) -> User:
        """Create a user activity log entry."""
        try:
            user = await UserRepository.get_by_telegram_id(session, log_data.user_telegram_id)
            if not user:
                raise NotFoundError(f"User with telegram_id {log_data.user_telegram_id} not found")
            
            log = await UserLogRepository.create(session, log_data, user.id)
            await session.commit()
            await session.refresh(log)
            logger.info("log_created", log_id=log.id, user_id=user.id, action=log_data.action)
            return log
        except NotFoundError:
            raise
        except Exception as e:
            await session.rollback()
            logger.error("log_creation_failed", error=str(e), exc_info=True)
            raise ValidationError(f"Failed to create log: {str(e)}")


# Maintain backward compatibility - export functions directly
async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Get user by Telegram ID."""
    return await UserService.get_user_by_telegram_id(session, telegram_id)


async def create_user(session: AsyncSession, user_data: UserCreate) -> User:
    """Create a new user."""
    return await UserService.create_user(session, user_data)


async def get_or_create_user(session: AsyncSession, user_data: UserCreate) -> tuple[User, bool]:
    """Get existing user or create new one. Returns (user, is_new)."""
    return await UserService.get_or_create_user(session, user_data)


async def update_user(session: AsyncSession, telegram_id: int, user_update: UserUpdate) -> Optional[User]:
    """Update user fields."""
    return await UserService.update_user(session, telegram_id, user_update)


async def update_user_activity(session: AsyncSession, telegram_id: int) -> bool:
    """Update user's last activity timestamp."""
    return await UserService.update_user_activity(session, telegram_id)


async def get_inactive_users(
    session: AsyncSession,
    since: datetime,
    statuses: List[UserStatus] = None
) -> List[User]:
    """Get users who have been inactive since given time."""
    return await UserService.get_inactive_users(session, since, statuses)


async def create_log(session: AsyncSession, log_data: LogCreate) -> User:
    """Create a user activity log entry."""
    return await UserService.create_log(session, log_data)


async def get_users_by_statuses(
    session: AsyncSession,
    statuses: List[UserStatus]
) -> List[User]:
    """Get users whose status is in the provided list."""
    return await UserService.get_users_by_statuses(session, statuses)
