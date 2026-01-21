"""UserLog ORM model."""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UserLog(Base):
    """User activity log for analytics."""
    __tablename__ = "user_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="logs")
    
    __table_args__ = (
        Index("idx_log_user_action", "user_id", "action"),
        Index("idx_log_created", "created_at"),
    )

