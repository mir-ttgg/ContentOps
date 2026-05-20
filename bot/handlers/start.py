from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from bot.keyboards.inline import main_menu_kb

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Бот ContentOps готов к работе.\n\n"
        "Команды:\n"
        "• /addchannel [chat_id] — зарегистрировать канал (бот должен быть его администратором)\n"
        "• /channels — список зарегистрированных каналов\n"
        "• /removechannel [id] — снять регистрацию\n",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await cmd_start(message)
