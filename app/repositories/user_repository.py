"""User repository."""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserStatus
from app.schemas import UserCreate, UserUpdate


class UserRepository:
    """Repository for user operations."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_telegram_id(db: AsyncSession, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await db.execute(
            select(User).where(
                User.telegram_id == telegram_id,
                User.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all(db: AsyncSession) -> List[User]:
        """Get all users."""
        result = await db.execute(
            select(User).where(
                User.is_deleted == False
            ).order_by(User.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_by_statuses(
        db: AsyncSession,
        statuses: List[UserStatus]
    ) -> List[User]:
        """Get users whose status is in the provided list."""
        result = await db.execute(
            select(User).where(
                User.status.in_(statuses),
                User.is_deleted == False
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def create(db: AsyncSession, user_data: UserCreate) -> User:
        """Create a new user (without commit)."""
        user = User(
            telegram_id=user_data.telegram_id,
            username=user_data.username,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            status=UserStatus.NEW,
            language=user_data.language or "en_US",  # Use provided language or default
        )
        db.add(user)
        await db.flush()
        return user
    
    @staticmethod
    async def get_or_create(db: AsyncSession, user_data: UserCreate) -> tuple[User, bool]:
        """Get existing user or create new one. Returns (user, is_new)."""
        user = await UserRepository.get_by_telegram_id(db, user_data.telegram_id)
        if user:
            return user, False
        
        # Check if soft-deleted user exists
        result = await db.execute(
            select(User).where(
                User.telegram_id == user_data.telegram_id,
                User.is_deleted == True
            )
        )
        deleted_user = result.scalar_one_or_none()
        
        if deleted_user:
            # Restore soft-deleted user and set to TRAINING status
            from app.models import UserStatus
            deleted_user.is_deleted = False
            deleted_user.deleted_at = None
            deleted_user.status = UserStatus.TRAINING
            deleted_user.username = user_data.username
            deleted_user.first_name = user_data.first_name
            deleted_user.last_name = user_data.last_name
            # Update language if provided (for new users restoring)
            if user_data.language:
                deleted_user.language = user_data.language
            deleted_user.updated_at = datetime.utcnow()
            await db.flush()
            return deleted_user, True
        
        user = await UserRepository.create(db, user_data)
        return user, True
    
    @staticmethod
    async def update(db: AsyncSession, telegram_id: int, user_update: UserUpdate) -> Optional[User]:
        """Update user fields (without commit)."""
        user = await UserRepository.get_by_telegram_id(db, telegram_id)
        if not user:
            return None
        
        update_data = user_update.model_dump(exclude_unset=True)
        updated = False
        for field, value in update_data.items():
            if hasattr(user, field) and getattr(user, field) != value:
                setattr(user, field, value)
                updated = True
        
        if updated:
            await db.flush()
            return user
        return None
    
    @staticmethod
    async def update_activity(db: AsyncSession, telegram_id: int) -> bool:
        """Update user's last activity timestamp (without commit)."""
        result = await db.execute(
            update(User)
            .where(
                User.telegram_id == telegram_id,
                User.is_deleted == False
            )
            .values(last_activity_at=datetime.utcnow())
        )
        if result.rowcount > 0:
            await db.flush()
            return True
        return False
    
    @staticmethod
    async def soft_delete(db: AsyncSession, user_id: int) -> Optional[User]:
        """Soft delete a user (without commit)."""
        user = await UserRepository.get_by_id(db, user_id)
        if not user or user.is_deleted:
            return None
        
        user.is_deleted = True
        user.deleted_at = datetime.utcnow()
        await db.flush()
        return user
    
    @staticmethod
    async def delete(db: AsyncSession, user_id: int, hard: bool = False) -> Optional[User]:
        """Delete a user (without commit)."""
        if not hard:
            return await UserRepository.soft_delete(db, user_id)
        
        # Hard delete (only in exceptional cases)
        user = await UserRepository.get_by_id(db, user_id)
        if not user:
            return None
        
        await db.delete(user)
        await db.flush()
        return user

