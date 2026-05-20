from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.post import Post
    from models.schedule_slot import ScheduleSlot


class Channel(Base, TimestampMixin):
    __tablename__ = "channels"
    __table_args__ = (
        UniqueConstraint("owner_tg_id", "tg_channel_id", name="uq_channels_owner_tg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tg_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    system_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    posts: Mapped[list["Post"]] = relationship(back_populates="channel", cascade="all, delete-orphan")
    schedule_slots: Mapped[list["ScheduleSlot"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )

    @property
    def approval_required(self) -> bool:
        return bool(self.settings_json.get("approval_required", False))

    @property
    def auto_post(self) -> bool:
        return bool(self.settings_json.get("auto_post", False))

    @property
    def auto_delete(self) -> bool:
        return bool(self.settings_json.get("auto_delete", False))

    @property
    def stopwords(self) -> list[str]:
        return list(self.settings_json.get("stopwords", []))

    @property
    def ai_model(self) -> str | None:
        return self.settings_json.get("ai_model")
