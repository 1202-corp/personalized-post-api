"""Channel avatar ORM model — avatar data in a separate table."""
from typing import Optional
from sqlalchemy import String, ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ChannelAvatar(Base):
    """Channel avatar: file_id and/or photo bytes. One row per channel (1:1)."""
    __tablename__ = "channel_avatars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # file_id from Telegram when main-bot sent photo; bytes = fallback from user-bot upload.
    avatar_telegram_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_photo_bytes: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)

    # Relationship
    channel: Mapped["Channel"] = relationship(back_populates="avatar")
