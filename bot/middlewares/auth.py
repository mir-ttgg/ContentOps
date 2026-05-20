from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from config import settings
from models import Admin


class AdminOnlyMiddleware(BaseMiddleware):
    """Drops events from non-admins. Superadmin IDs from .env are always allowed."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is None:
            return  # ignore events without identifiable user

        if user_id in settings.superadmin_ids:
            data["is_admin"] = True
            return await handler(event, data)

        session = data.get("session")
        if session is None:
            return

        result = await session.execute(select(Admin).where(Admin.tg_user_id == user_id))
        admin = result.scalar_one_or_none()
        if admin is None:
            if isinstance(event, Message):
                await event.answer("Доступ запрещён.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Доступ запрещён.", show_alert=True)
            return

        data["is_admin"] = True
        data["admin"] = admin
        return await handler(event, data)
