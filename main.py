from __future__ import annotations

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from bot.handlers import build_router
from bot.middlewares import AdminOnlyMiddleware, DbSessionMiddleware
from bot.runtime import set_runtime
from config import settings
from services.ai import build_provider
from services.channel.manager import ChannelManager
from services.moderation.service import ModerationService
from services.scheduler.scheduler import PostScheduler


def configure_logging() -> None:
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level, serialize=False, backtrace=False, diagnose=False)


async def main() -> None:
    configure_logging()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    try:
        ai_provider = build_provider()
    except Exception as e:
        logger.warning("AI provider disabled: {}", e)
        ai_provider = None

    channel_manager = ChannelManager(bot)
    moderation = ModerationService(ai_provider)
    scheduler = PostScheduler()

    set_runtime(
        bot=bot,
        channel_manager=channel_manager,
        moderation=moderation,
        scheduler=scheduler,
        ai=ai_provider,
    )

    dp = Dispatcher()
    for observer in (dp.message, dp.callback_query):
        observer.middleware(DbSessionMiddleware())
        observer.middleware(AdminOnlyMiddleware())
    dp.include_router(build_router())

    scheduler.start()
    await scheduler.sync_all()

    logger.info("Bot starting (provider={}, model={})", settings.ai_provider, settings.ai_model)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
