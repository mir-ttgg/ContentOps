"""Process-wide runtime container.

APScheduler jobs and FastAPI handlers need to reach the bot, channel manager,
scheduler, and AI provider without an explicit DI graph. We register them once
at startup and read them via the getters below.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot
    from services.ai.base import AIProvider
    from services.channel.manager import ChannelManager
    from services.moderation.service import ModerationService
    from services.scheduler.scheduler import PostScheduler


_bot: "Bot | None" = None
_channel_manager: "ChannelManager | None" = None
_moderation: "ModerationService | None" = None
_scheduler: "PostScheduler | None" = None
_ai: "AIProvider | None" = None


def set_runtime(
    *,
    bot: "Bot",
    channel_manager: "ChannelManager",
    moderation: "ModerationService",
    scheduler: "PostScheduler",
    ai: "AIProvider | None",
) -> None:
    global _bot, _channel_manager, _moderation, _scheduler, _ai
    _bot = bot
    _channel_manager = channel_manager
    _moderation = moderation
    _scheduler = scheduler
    _ai = ai


def get_bot() -> "Bot":
    assert _bot is not None, "Runtime not initialized"
    return _bot


def get_channel_manager() -> "ChannelManager":
    assert _channel_manager is not None, "Runtime not initialized"
    return _channel_manager


def get_moderation_service() -> "ModerationService":
    assert _moderation is not None, "Runtime not initialized"
    return _moderation


def get_scheduler() -> "PostScheduler":
    assert _scheduler is not None, "Runtime not initialized"
    return _scheduler


def get_ai_provider() -> "AIProvider":
    if _ai is None:
        raise RuntimeError("AI provider is not configured")
    return _ai
