"""Taste cluster ORM model — clusters of users by preference vector per channel (user_channel_tastes)."""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Integer, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TasteCluster(Base):
    """Cluster of users with similar taste for one channel. Used with user_channel_tastes for delivery."""
    __tablename__ = "taste_clusters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    centroid: Mapped[Optional[List[float]]] = mapped_column(JSON, nullable=True)  # average preference vector
    user_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
