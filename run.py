"""Combined entrypoint: runs bot polling and FastAPI webapp in one event loop.

This avoids two competing scheduler instances over the same jobstore.
"""
from __future__ import annotations

import asyncio
import sys

import uvicorn
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
    logger.add(sys.stderr, level=settings.log_level)


async def main() -> None:
    configure_logging()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        ai = build_provider()
    except Exception as e:
        logger.warning("AI provider disabled: {}", e)
        ai = None

    channel_mgr = ChannelManager(bot)
    moderation = ModerationService(ai)
    scheduler = PostScheduler()
    set_runtime(
        bot=bot, channel_manager=channel_mgr,
        moderation=moderation, scheduler=scheduler, ai=ai,
    )

    dp = Dispatcher()
    for observer in (dp.message, dp.callback_query):
        observer.middleware(DbSessionMiddleware())
        observer.middleware(AdminOnlyMiddleware())
    dp.include_router(build_router())

    scheduler.start()
    await scheduler.sync_all()

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        me = await bot.get_me()
        logger.info("Bot authorized as @{} (id={})", me.username, me.id)
    except Exception as e:
        logger.exception("Bot init failed: {}", e)
        raise

    # Import the FastAPI app AFTER runtime is set; disable its own lifespan
    # (which would build a second bot/scheduler) by using a wrapper.
    from webapp.app import app as fastapi_app
    fastapi_app.router.lifespan_context = _noop_lifespan  # type: ignore[attr-defined]

    config = uvicorn.Config(
        fastapi_app,
        host=settings.webapp_host,
        port=settings.webapp_port,
        log_level=settings.log_level.lower(),
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    bot_task = asyncio.create_task(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
        name="aiogram-polling",
    )
    web_task = asyncio.create_task(server.serve(), name="uvicorn")

    logger.info("ContentOps running (bot + webapp).")
    try:
        done, pending = await asyncio.wait(
            {bot_task, web_task}, return_when=asyncio.FIRST_EXCEPTION
        )
        for t in done:
            exc = t.exception()
            if exc:
                logger.error("Task {} crashed: {!r}", t.get_name(), exc)
        for t in pending:
            t.cancel()
    finally:
        await scheduler.shutdown()
        await bot.session.close()


from contextlib import asynccontextmanager


@asynccontextmanager
async def _noop_lifespan(app):
    yield


if __name__ == "__main__":
    asyncio.run(main())
