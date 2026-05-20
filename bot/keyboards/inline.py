from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import settings


def main_menu_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if settings.webapp_url:
        rows.append([
            InlineKeyboardButton(text="Панель администратора", web_app=WebAppInfo(url=settings.webapp_url))
        ])
    rows.append([
        InlineKeyboardButton(text="Каналы", callback_data="channels:list"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def moderation_kb(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Опубликовать", callback_data=f"mod:approve:{post_id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"mod:reject:{post_id}"),
        ],
    ])
