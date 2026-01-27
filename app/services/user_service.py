"""User business logic service."""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserStatus
from app.models.user_log import UserLog
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
                f"user_created: user_id={user.id}, telegram_id={user.telegram_id}, username={user.username}"
            )
            return user
        except Exception as e:
            await session.rollback()
            logger.error(f"user_creation_failed: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    async def get_or_create_user(session: AsyncSession, user_data: UserCreate) -> tuple[User, bool]:
        """Get existing user or create new one. Returns (user, is_new)."""
        try:
            user, is_new = await UserRepository.get_or_create(session, user_data)
            await session.commit()
            if is_new:
                await session.refresh(user)
                logger.info(f"user_created: user_id={user.id}, telegram_id={user.telegram_id}")
            return user, is_new
        except Exception as e:
            await session.rollback()
            logger.error(f"get_or_create_user_failed: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    async def update_user(session: AsyncSession, telegram_id: int, user_update: UserUpdate) -> Optional[User]:
        """Update user fields."""
        try:
            user = await UserRepository.update(session, telegram_id, user_update)
            if user:
                await session.commit()
                await session.refresh(user)
                logger.info(f"user_updated: user_id={user.id}, telegram_id={telegram_id}")
            return user
        except Exception as e:
            await session.rollback()
            logger.error(f"user_update_failed: telegram_id={telegram_id}, error={str(e)}", exc_info=True)
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
            logger.error(f"update_activity_failed: telegram_id={telegram_id}, error={str(e)}", exc_info=True)
            raise
    
    @staticmethod
    async def get_users_by_statuses(
        session: AsyncSession,
        statuses: List[UserStatus]
    ) -> List[User]:
        """Get users whose status is in the provided list."""
        return await UserRepository.get_by_statuses(session, statuses)
    
    @staticmethod
    async def create_log(session: AsyncSession, log_data: LogCreate) -> UserLog:
        """Create a user activity log entry."""
        try:
            user = await UserRepository.get_by_telegram_id(session, log_data.user_telegram_id)
            if not user:
                raise NotFoundError(f"User with telegram_id {log_data.user_telegram_id} not found")
            
            log = await UserLogRepository.create(session, log_data, user.id)
            await session.commit()
            await session.refresh(log)
            logger.info(f"log_created: log_id={log.id}, user_id={user.id}, action={log_data.action}")
            return log
        except NotFoundError:
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"log_creation_failed: {str(e)}", exc_info=True)
            raise ValidationError(f"Failed to create log: {str(e)}")
    
    @staticmethod
    async def update_user_language(
        session: AsyncSession,
        telegram_id: int,
        language: str
    ) -> bool:
        """Update user's preferred language."""
        try:
            user = await UserRepository.get_by_telegram_id(session, telegram_id)
            if not user:
                return False
            
            user.language = language
            await session.commit()
            logger.info(f"user_language_updated: user_id={user.id}, language={language}")
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f"user_language_update_failed: telegram_id={telegram_id}, error={str(e)}", exc_info=True)
            raise
    
    @staticmethod
    async def mark_training_complete(
        session: AsyncSession,
        telegram_id: int
    ) -> tuple[UserStatus, bool]:
        """Mark user training as complete and notify via Redis.
        
        Returns (user_status, notified).
        """
        try:
            user = await UserRepository.get_by_telegram_id(session, telegram_id)
            if not user:
                raise NotFoundError(f"User with telegram_id {telegram_id} not found")
            
            # Update status to TRAINED if currently in TRAINING
            if user.status == UserStatus.TRAINING:
                user.status = UserStatus.TRAINED
                user.is_trained = True
                await session.commit()
            
            # Notify main-bot via Redis pub/sub
            notified = await UserService._notify_training_complete(telegram_id)
            
            return user.status, notified
        except NotFoundError:
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"mark_training_complete_failed: telegram_id={telegram_id}, error={str(e)}", exc_info=True)
            raise
    
    @staticmethod
    async def _notify_training_complete(telegram_id: int) -> bool:
        """Notify main-bot via Redis pub/sub about training completion."""
        import json
        import redis.asyncio as aioredis
        from app.config import get_settings
        
        settings = get_settings()
        redis_client = None
        try:
            redis_client = aioredis.from_url(
                settings.redis_url,
                decode_responses=False,  # We send JSON bytes
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            result = await redis_client.publish(
                "ppp:training_complete",
                json.dumps({"telegram_id": telegram_id, "chat_id": telegram_id}).encode('utf-8')
            )
            logger.info(f"training_complete_published: telegram_id={telegram_id}, subscribers={result}")
            return result > 0
        except Exception as e:
            logger.error(f"redis_notification_failed: telegram_id={telegram_id}, error={str(e)}", exc_info=True)
            return False
        finally:
            if redis_client:
                await redis_client.aclose()


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


async def create_log(session: AsyncSession, log_data: LogCreate) -> UserLog:
    """Create a user activity log entry."""
    return await UserService.create_log(session, log_data)


async def get_users_by_statuses(
    session: AsyncSession,
    statuses: List[UserStatus]
) -> List[User]:
    """Get users whose status is in the provided list."""
    return await UserService.get_users_by_statuses(session, statuses)
