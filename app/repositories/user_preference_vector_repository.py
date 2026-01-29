"""UserPreferenceVector repository."""
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_preference_vector import UserPreferenceVector


class UserPreferenceVectorRepository:
    """Repository for user preference vector cache."""

    @staticmethod
    async def delete_by_user_id(db: AsyncSession, user_id: int) -> bool:
        """Delete preference vector row for user (e.g. on user reset)."""
        result = await db.execute(delete(UserPreferenceVector).where(UserPreferenceVector.user_id == user_id))
        await db.flush()
        return result.rowcount > 0
