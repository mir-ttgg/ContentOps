from __future__ import annotations

from datetime import datetime, time
from typing import Any

from pydantic import BaseModel, Field

from models import MediaType, PostSource, PostStatus


class ChannelOut(BaseModel):
    id: int
    tg_channel_id: int
    name: str
    username: str | None
    system_prompt: str
    settings: dict[str, Any]

    @classmethod
    def from_orm(cls, ch) -> "ChannelOut":
        return cls(
            id=ch.id,
            tg_channel_id=ch.tg_channel_id,
            name=ch.name,
            username=ch.username,
            system_prompt=ch.system_prompt,
            settings=ch.settings_json or {},
        )


class ChannelSettingsIn(BaseModel):
    system_prompt: str | None = None
    approval_required: bool | None = None
    auto_post: bool | None = None
    auto_delete: bool | None = None
    stopwords: list[str] | None = None
    ai_model: str | None = None


class PostIn(BaseModel):
    channel_id: int
    text: str = ""
    media_url: str | None = None
    media_file_id: str | None = None
    media_type: MediaType = MediaType.NONE
    scheduled_at: datetime | None = None
    publish_now: bool = False
    source: PostSource = PostSource.MANUAL


class PostOut(BaseModel):
    id: int
    channel_id: int
    text: str
    media_url: str | None
    media_type: MediaType
    status: PostStatus
    source: PostSource
    scheduled_at: datetime | None
    published_at: datetime | None
    created_at: datetime

    @classmethod
    def from_orm(cls, p) -> "PostOut":
        return cls(
            id=p.id,
            channel_id=p.channel_id,
            text=p.text,
            media_url=p.media_url,
            media_type=p.media_type,
            status=p.status,
            source=p.source,
            scheduled_at=p.scheduled_at,
            published_at=p.published_at,
            created_at=p.created_at,
        )


class AIGenerateIn(BaseModel):
    channel_id: int
    topic: str
    improve_text: str | None = None


class AIGenerateOut(BaseModel):
    text: str


class ScheduleSlotIn(BaseModel):
    time_of_day: time
    days_of_week: list[int] = Field(default_factory=list)  # 0..6
    enabled: bool = True


class ScheduleSlotOut(BaseModel):
    id: int
    time_of_day: time
    days_of_week: list[int]
    enabled: bool


class ModerationLogOut(BaseModel):
    id: int
    post_id: int | None
    action: str
    reason: str
    triggered_by: str
    created_at: datetime


class DashboardOut(BaseModel):
    channels: int
    posts_today: int
    queue: int
    pending_approval: int
    recent: list[PostOut]
