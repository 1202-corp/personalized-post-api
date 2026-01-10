"""
Analytics API endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def get_overview(db: AsyncSession = Depends(get_session)):
    """Get overall platform statistics."""
    return await analytics_service.get_overview_stats(db)


@router.get("/daily")
async def get_daily_stats(days: int = 7, db: AsyncSession = Depends(get_session)):
    """Get daily statistics for the last N days."""
    return await analytics_service.get_daily_stats(db, days)


@router.get("/channels")
async def get_channel_stats(limit: int = 10, db: AsyncSession = Depends(get_session)):
    """Get statistics per channel."""
    return await analytics_service.get_channel_stats(db, limit)


@router.get("/retention")
async def get_retention(days: int = 7, db: AsyncSession = Depends(get_session)):
    """Get user retention metrics."""
    return await analytics_service.get_user_retention(db, days)


@router.get("/recommendations")
async def get_recommendation_stats(db: AsyncSession = Depends(get_session)):
    """Get recommendation effectiveness metrics."""
    return await analytics_service.get_recommendation_effectiveness(db)


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_session)):
    """Get all analytics data for dashboard."""
    return {
        "overview": await analytics_service.get_overview_stats(db),
        "daily": await analytics_service.get_daily_stats(db, 7),
        "channels": await analytics_service.get_channel_stats(db, 5),
        "retention": await analytics_service.get_user_retention(db, 7),
        "recommendations": await analytics_service.get_recommendation_effectiveness(db),
    }
