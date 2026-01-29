"""Interaction repository."""
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.interaction import Interaction, InteractionType
from app.models.user import User
from app.models.post import Post


class InteractionRepository:
    """Repository for interaction operations."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, interaction_id: int) -> Optional[Interaction]:
        """Get interaction by ID."""
        result = await db.execute(
            select(Interaction).where(Interaction.id == interaction_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_user_and_post(
        db: AsyncSession,
        user_id: int,
        post_id: int
    ) -> Optional[Interaction]:
        """Get interaction by user ID and post ID."""
        result = await db.execute(
            select(Interaction).where(
                Interaction.user_id == user_id,
                Interaction.post_id == post_id
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: int) -> List[Interaction]:
        """Get all interactions for a user."""
        result = await db.execute(
            select(Interaction)
            .join(User)
            .where(
                User.id == user_id,
                User.is_deleted == False
            )
            .order_by(Interaction.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_by_post_id(db: AsyncSession, post_id: int) -> List[Interaction]:
        """Get all interactions for a post."""
        result = await db.execute(
            select(Interaction)
            .join(Post)
            .where(
                Post.id == post_id,
                Post.is_deleted == False
            )
            .order_by(Interaction.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int,
        post_id: int,
        interaction_type: InteractionType
    ) -> Interaction:
        """Create a new interaction (without commit)."""
        # Check if interaction already exists
        existing = await InteractionRepository.get_by_user_and_post(db, user_id, post_id)
        if existing:
            # Update existing interaction
            existing.interaction_type = interaction_type
            await db.flush()
            return existing
        
        interaction = Interaction(
            user_id=user_id,
            post_id=post_id,
            interaction_type=interaction_type,
        )
        db.add(interaction)
        await db.flush()
        return interaction
    
    @staticmethod
    async def delete(db: AsyncSession, interaction_id: int) -> bool:
        """Delete an interaction (without commit)."""
        interaction = await InteractionRepository.get_by_id(db, interaction_id)
        if not interaction:
            return False
        
        await db.delete(interaction)
        await db.flush()
        return True
    
    @staticmethod
    async def count_by_user_id(db: AsyncSession, user_id: int) -> int:
        """Count interactions for a user."""
        result = await db.execute(
            select(func.count(Interaction.id)).where(Interaction.user_id == user_id)
        )
        return result.scalar() or 0

