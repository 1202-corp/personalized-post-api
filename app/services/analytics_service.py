"""
Analytics service for collecting and aggregating metrics.
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.post import Post
from app.models.interaction import Interaction
from app.models.channel import Channel
from app.models.user_channel import UserChannel
from app.models.user_log import UserLog


async def get_overview_stats(db: AsyncSession) -> dict:
    """Get overall platform statistics."""
    # Total users (excluding deleted)
    total_users = await db.scalar(
        select(func.count(User.id)).where(User.is_deleted == False)
    )
    
    # Trained users (MEMBER or ADMIN role)
    trained_users = await db.scalar(
        select(func.count(User.id)).where(
            User.user_role.in_([UserRole.member, UserRole.admin]),
            User.is_deleted == False
        )
    )
    
    # Total channels (excluding deleted)
    total_channels = await db.scalar(
        select(func.count(Channel.id)).where(Channel.is_deleted == False)
    )
    
    # Total posts (excluding deleted)
    total_posts = await db.scalar(
        select(func.count(Post.id)).where(Post.is_deleted == False)
    )
    
    # Total interactions
    total_interactions = await db.scalar(select(func.count(Interaction.id)))
    
    # Interactions breakdown
    from app.models.interaction import InteractionType
    likes = await db.scalar(
        select(func.count(Interaction.id)).where(Interaction.interaction_type == InteractionType.LIKE)
    )
    dislikes = await db.scalar(
        select(func.count(Interaction.id)).where(Interaction.interaction_type == InteractionType.DISLIKE)
    )
    skips = await db.scalar(
        select(func.count(Interaction.id)).where(Interaction.interaction_type == InteractionType.SKIP)
    )
    
    return {
        "users": {
            "total": total_users or 0,
            "trained": trained_users or 0,
            "training_rate": round((trained_users or 0) / max(total_users or 1, 1) * 100, 1),
        },
        "channels": {
            "total": total_channels or 0,
        },
        "posts": {
            "total": total_posts or 0,
        },
        "interactions": {
            "total": total_interactions or 0,
            "likes": likes or 0,
            "dislikes": dislikes or 0,
            "skips": skips or 0,
            "like_rate": round((likes or 0) / max(total_interactions or 1, 1) * 100, 1),
        },
    }


async def get_daily_stats(db: AsyncSession, days: int = 7) -> list:
    """Get daily statistics for the last N days."""
    results = []
    today = datetime.utcnow().date()
    
    for i in range(days):
        date = today - timedelta(days=i)
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())
        
        # New users (excluding deleted)
        new_users = await db.scalar(
            select(func.count(User.id)).where(
                and_(
                    User.created_at >= start,
                    User.created_at <= end,
                    User.is_deleted == False
                )
            )
        )
        
        # Interactions
        interactions = await db.scalar(
            select(func.count(Interaction.id)).where(
                and_(Interaction.created_at >= start, Interaction.created_at <= end)
            )
        )
        
        results.append({
            "date": date.isoformat(),
            "new_users": new_users or 0,
            "interactions": interactions or 0,
        })
    
    return list(reversed(results))


async def get_channel_stats(db: AsyncSession, limit: int = 10) -> list:
    """Get statistics per channel."""
    query = (
        select(
            Channel.id,
            Channel.username,
            Channel.title,
            func.count(Post.id).label("posts_count"),
        )
        .outerjoin(Post, and_(
            Post.channel_id == Channel.id,
            Post.is_deleted == False
        ))
        .where(Channel.is_deleted == False)
        .group_by(Channel.id)
        .order_by(func.count(Post.id).desc())
        .limit(limit)
    )
    
    result = await db.execute(query)
    channels = result.all()
    
    stats = []
    for ch in channels:
        # Get interaction stats for this channel's posts
        from app.models.interaction import InteractionType
        interactions = await db.scalar(
            select(func.count(Interaction.id))
            .join(Post, Interaction.post_id == Post.id)
            .where(
                Post.channel_id == ch.id,
                Post.is_deleted == False
            )
        )
        
        likes = await db.scalar(
            select(func.count(Interaction.id))
            .join(Post, Interaction.post_id == Post.id)
            .where(and_(
                Post.channel_id == ch.id,
                Post.is_deleted == False,
                Interaction.interaction_type == InteractionType.LIKE
            ))
        )
        
        stats.append({
            "id": ch.id,
            "username": ch.username,
            "title": ch.title,
            "posts_count": ch.posts_count,
            "interactions": interactions or 0,
            "likes": likes or 0,
            "like_rate": round((likes or 0) / max(interactions or 1, 1) * 100, 1),
        })
    
    return stats


async def get_user_retention(db: AsyncSession, days: int = 7) -> dict:
    """Calculate user retention metrics."""
    today = datetime.utcnow().date()
    
    # Users active in the last N days (excluding deleted)
    active_cutoff = datetime.combine(today - timedelta(days=days), datetime.min.time())
    active_users = await db.scalar(
        select(func.count(User.id)).where(
            User.last_activity_at >= active_cutoff,
            User.is_deleted == False
        )
    )
    
    total_users = await db.scalar(
        select(func.count(User.id)).where(User.is_deleted == False)
    )
    
    # Users who completed training (MEMBER or ADMIN role)
    trained_users = await db.scalar(
        select(func.count(User.id)).where(
            User.user_role.in_([UserRole.member, UserRole.admin]),
            User.is_deleted == False
        )
    )
    
    return {
        "period_days": days,
        "total_users": total_users or 0,
        "active_users": active_users or 0,
        "retention_rate": round((active_users or 0) / max(total_users or 1, 1) * 100, 1),
        "trained_users": trained_users or 0,
        "completion_rate": round((trained_users or 0) / max(total_users or 1, 1) * 100, 1),
    }


async def get_recommendation_effectiveness(db: AsyncSession) -> dict:
    """Analyze recommendation effectiveness based on interactions."""
    # Average relevance score of liked posts vs disliked
    from app.models.interaction import InteractionType
    liked_avg = await db.scalar(
        select(func.avg(Post.relevance_score))
        .join(Interaction, Interaction.post_id == Post.id)
        .where(
            Interaction.interaction_type == InteractionType.LIKE,
            Post.is_deleted == False
        )
    )
    
    disliked_avg = await db.scalar(
        select(func.avg(Post.relevance_score))
        .join(Interaction, Interaction.post_id == Post.id)
        .where(
            Interaction.interaction_type == InteractionType.DISLIKE,
            Post.is_deleted == False
        )
    )
    
    # Posts with relevance scores (excluding deleted)
    posts_with_scores = await db.scalar(
        select(func.count(Post.id)).where(
            Post.relevance_score.isnot(None),
            Post.is_deleted == False
        )
    )
    total_posts = await db.scalar(
        select(func.count(Post.id)).where(Post.is_deleted == False)
    )
    
    return {
        "avg_liked_score": round(liked_avg or 0, 4),
        "avg_disliked_score": round(disliked_avg or 0, 4),
        "score_difference": round((liked_avg or 0) - (disliked_avg or 0), 4),
        "posts_with_scores": posts_with_scores or 0,
        "total_posts": total_posts or 0,
        "scoring_coverage": round((posts_with_scores or 0) / max(total_posts or 1, 1) * 100, 1),
    }
