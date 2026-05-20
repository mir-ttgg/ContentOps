from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.channel import Channel


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    DELETED = "deleted"


class PostSource(str, enum.Enum):
    MANUAL = "manual"
    AI_AUTO = "ai_auto"
    AI_MANUAL = "ai_manual"


class MediaType(str, enum.Enum):
    NONE = "none"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"


class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    media_url: Mapped[str | None] = mapped_column(String(1024))
    media_file_id: Mapped[str | None] = mapped_column(String(512))
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType, name="media_type"), default=MediaType.NONE, nullable=False
    )
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, name="post_status"), default=PostStatus.DRAFT, nullable=False, index=True
    )
    source: Mapped[PostSource] = mapped_column(
        Enum(PostSource, name="post_source"), default=PostSource.MANUAL, nullable=False
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by: Mapped[int | None] = mapped_column(BigInteger)

    channel: Mapped["Channel"] = relationship(back_populates="posts")
