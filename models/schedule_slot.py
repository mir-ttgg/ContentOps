from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.channel import Channel


class ScheduleSlot(Base, TimestampMixin):
    __tablename__ = "schedule_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False)
    # comma-separated list of weekday numbers 0..6 (Mon..Sun); empty means daily
    days_of_week: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    channel: Mapped["Channel"] = relationship(back_populates="schedule_slots")

    @property
    def weekday_list(self) -> list[int]:
        if not self.days_of_week:
            return list(range(7))
        return [int(x) for x in self.days_of_week.split(",") if x.strip()]
