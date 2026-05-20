from aiogram import Router

from bot.handlers import channels, moderation, start


def build_router() -> Router:
    router = Router(name="root")
    router.include_router(start.router)
    router.include_router(channels.router)
    router.include_router(moderation.router)
    return router
