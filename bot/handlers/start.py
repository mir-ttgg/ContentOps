from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import main_menu_kb
from config import settings
from models import Admin
from models.admin import AdminRole

router = Router(name="start")


WELCOME_ADMIN = (
    "✨ <b>ContentOps</b> — ваш редакционный пульт\n"
    "<i>Планирование, модерация и AI-публикации в один клик.</i>\n\n"
    "🚀 <b>С чего начать</b>\n"
    "1️⃣ Добавьте канал: <code>/addchannel -100…</code>\n"
    "2️⃣ Откройте панель администратора (кнопка ниже)\n"
    "3️⃣ Настройте расписание и доверьте публикации боту\n\n"
    "ℹ️ Полный список команд — <code>/help</code>"
)

WELCOME_GUEST = (
    "👋 <b>Добро пожаловать в ContentOps!</b>\n\n"
    "Это закрытый бот для управления контентом каналов.\n"
    "Чтобы получить доступ, введите промо-код:\n\n"
    "<code>/promo ваш_код</code>"
)

HELP_TEXT = (
    "📖 <b>Команды ContentOps</b>\n\n"
    "<b>Основное</b>\n"
    "• /start — главное меню\n"
    "• /help — этот список\n"
    "• /promo <code>&lt;код&gt;</code> — активировать доступ\n\n"
    "<b>Каналы</b>\n"
    "• /addchannel <code>&lt;chat_id&gt;</code> — зарегистрировать канал "
    "(бот должен быть его администратором)\n"
    "• /channels — список зарегистрированных каналов\n"
    "• /removechannel <code>&lt;id&gt;</code> — снять регистрацию\n\n"
    "<b>Подсказка</b>\n"
    "Управление публикациями, расписанием и модерацией доступно "
    "через панель администратора — кнопка под сообщением /start."
)


async def _grant_access(session: AsyncSession, message: Message) -> Admin:
    user = message.from_user
    assert user is not None
    admin = Admin(
        tg_user_id=user.id,
        username=user.username,
        role=AdminRole.EDITOR,
    )
    session.add(admin)
    await session.flush()
    return admin


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession, is_admin: bool = False):
    code = (command.args or "").strip()
    if code and not is_admin:
        await _try_redeem(message, session, code)
        return

    if is_admin:
        await message.answer(WELCOME_ADMIN, parse_mode="HTML", reply_markup=main_menu_kb())
    else:
        await message.answer(WELCOME_GUEST, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message, is_admin: bool = False):
    if is_admin:
        await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=main_menu_kb())
    else:
        await message.answer(WELCOME_GUEST, parse_mode="HTML")


@router.message(Command("promo"))
async def cmd_promo(message: Message, command: CommandObject, session: AsyncSession, is_admin: bool = False):
    if is_admin:
        await message.answer("✅ У вас уже есть доступ.", parse_mode="HTML")
        return
    code = (command.args or "").strip()
    if not code:
        await message.answer(
            "Использование: <code>/promo &lt;код&gt;</code>",
            parse_mode="HTML",
        )
        return
    await _try_redeem(message, session, code)


async def _try_redeem(message: Message, session: AsyncSession, code: str) -> None:
    user = message.from_user
    if user is None:
        return
    if code != settings.promo_code:
        await message.answer("❌ Неверный промо-код. Попробуйте ещё раз.")
        return

    existing = await session.execute(select(Admin).where(Admin.tg_user_id == user.id))
    if existing.scalar_one_or_none() is None:
        await _grant_access(session, message)

    await message.answer(
        "🎉 <b>Доступ открыт!</b>\n\n" + WELCOME_ADMIN,
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
