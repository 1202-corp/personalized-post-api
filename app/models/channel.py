"""Channel ORM model."""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, BigInteger, Boolean, DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.channel_avatar import ChannelAvatar


class Channel(Base):
    """Telegram channel model."""
    __tablename__ = "channels"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # is_default = channel is in DEFAULT_TRAINING_CHANNELS (onboarding).
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Channel description (bio/about) from Telethon, set by user-bot on sync
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Soft delete fields
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    avatar: Mapped[Optional["ChannelAvatar"]] = relationship(
        back_populates="channel", uselist=False, cascade="all, delete-orphan"
    )
    posts: Mapped[List["Post"]] = relationship(back_populates="channel", cascade="all, delete-orphan")
    user_channels: Mapped[List["UserChannel"]] = relationship(back_populates="channel", cascade="all, delete-orphan")

    @property
    def avatar_telegram_file_id(self) -> Optional[str]:
        """From channel_avatars table; None if no avatar row."""
        return self.avatar.avatar_telegram_file_id if self.avatar else None

    @property
    def avatar_photo_bytes(self) -> Optional[bytes]:
        """From channel_avatars table; None if no avatar row."""
        return self.avatar.avatar_photo_bytes if self.avatar else None

