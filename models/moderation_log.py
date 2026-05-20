from __future__ import annotations

import enum

from sqlalchemy import BigInteger, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class ModerationAction(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_DELETED = "auto_deleted"
    FLAGGED = "flagged"
    EDITED = "edited"


class ModerationLog(Base, TimestampMixin):
    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"), index=True)
    action: Mapped[ModerationAction] = mapped_column(
        Enum(ModerationAction, name="moderation_action"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger)
