from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from config import settings
from models import Admin


PUBLIC_COMMANDS = ("/start", "/help", "/promo")


def _is_public_command(text: str | None) -> bool:
    if not text:
        return False
    head = text.split(maxsplit=1)[0].split("@", 1)[0].lower()
    return head in PUBLIC_COMMANDS


class AdminOnlyMiddleware(BaseMiddleware):
    """Drops events from non-admins. Superadmin IDs from .env are always allowed.

    Public commands (/start, /help, /promo) are passed through so that new
    users can redeem a promo code and gain access.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        text: str | None = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            text = event.text or event.caption
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
        if admin is not None:
            data["is_admin"] = True
            data["admin"] = admin
            return await handler(event, data)

        if isinstance(event, Message) and _is_public_command(text):
            data["is_admin"] = False
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(
                "🔒 Доступ ограничен.\n\n"
                "Введите промо-код командой <code>/promo &lt;код&gt;</code>, "
                "чтобы получить доступ.",
                parse_mode="HTML",
            )
        elif isinstance(event, CallbackQuery):
            await event.answer("Доступ запрещён.", show_alert=True)
        return
