from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, BigInteger, Text, Boolean, ForeignKey, DateTime, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class UserStatus(str, enum.Enum):
    """User funnel status."""
    NEW = "new"
    ONBOARDING = "onboarding"
    TRAINING = "training"
    TRAINED = "trained"
    ACTIVE = "active"
    CHURNED = "churned"


class InteractionType(str, enum.Enum):
    """Type of user interaction with post."""
    LIKE = "like"
    DISLIKE = "dislike"
    SKIP = "skip"


class User(Base):
    """Telegram user model."""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), 
        default=UserStatus.NEW,
        nullable=False
    )
    is_trained: Mapped[bool] = mapped_column(Boolean, default=False)
    bonus_channels_count: Mapped[int] = mapped_column(default=0)
    initial_best_post_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    last_nudge_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    channels: Mapped[List["UserChannel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    interactions: Mapped[List["Interaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    logs: Mapped[List["UserLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_user_status", "status"),
        Index("idx_user_last_activity", "last_activity_at"),
    )


class Channel(Base):
    """Telegram channel model."""
    __tablename__ = "channels"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    posts: Mapped[List["Post"]] = relationship(back_populates="channel", cascade="all, delete-orphan")
    user_channels: Mapped[List["UserChannel"]] = relationship(back_populates="channel", cascade="all, delete-orphan")


class UserChannel(Base):
    """User-Channel association (subscription)."""
    __tablename__ = "user_channels"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    
    is_for_training: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bonus: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="channels")
    channel: Mapped["Channel"] = relationship(back_populates="user_channels")
    
    __table_args__ = (
        Index("idx_user_channel", "user_id", "channel_id", unique=True),
    )


class Post(Base):
    """Channel post model."""
    __tablename__ = "posts"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    media_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Mock ML score (0.0 - 1.0)
    relevance_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    channel: Mapped["Channel"] = relationship(back_populates="posts")
    interactions: Mapped[List["Interaction"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_post_channel_message", "channel_id", "telegram_message_id", unique=True),
        Index("idx_post_relevance", "relevance_score"),
    )


class Interaction(Base):
    """User interaction with post."""
    __tablename__ = "interactions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    
    interaction_type: Mapped[InteractionType] = mapped_column(
        Enum(InteractionType),
        nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="interactions")
    post: Mapped["Post"] = relationship(back_populates="interactions")
    
    __table_args__ = (
        Index("idx_interaction_user_post", "user_id", "post_id", unique=True),
    )


class UserLog(Base):
    """User activity log for analytics."""
    __tablename__ = "user_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="logs")
    
    __table_args__ = (
        Index("idx_log_user_action", "user_id", "action"),
        Index("idx_log_created", "created_at"),
    )
