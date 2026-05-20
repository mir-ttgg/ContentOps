from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.runtime import get_channel_manager
from services.channel.manager import ChannelError

router = Router(name="channels")


@router.message(Command("addchannel"))
async def cmd_addchannel(message: Message, command: CommandObject, session: AsyncSession):
    if message.from_user is None:
        return
    if not command.args:
        await message.answer("Использование: /addchannel [chat_id] (например, -1001234567890)")
        return
    try:
        tg_id = int(command.args.strip())
    except ValueError:
        await message.answer("chat_id должен быть целым числом.")
        return

    try:
        channel = await get_channel_manager().add_channel(
            session, tg_id, owner_tg_id=message.from_user.id
        )
    except ChannelError as e:
        await message.answer(f"Ошибка: {e}")
        return

    await message.answer(
        f"Добавлен: <b>{channel.name}</b> (id={channel.id}, tg_id={channel.tg_channel_id})",
        parse_mode="HTML",
    )


@router.message(Command("channels"))
async def cmd_channels(message: Message, session: AsyncSession):
    if message.from_user is None:
        return
    channels = await get_channel_manager().list_channels(
        session, owner_tg_id=message.from_user.id
    )
    if not channels:
        await message.answer("У вас ещё нет каналов. Добавьте через /addchannel [chat_id].")
        return
    lines = [
        f"#{c.id} — {c.name} (tg_id={c.tg_channel_id})" for c in channels
    ]
    await message.answer("\n".join(lines))


@router.message(Command("removechannel"))
async def cmd_removechannel(message: Message, command: CommandObject, session: AsyncSession):
    if message.from_user is None:
        return
    if not command.args:
        await message.answer("Использование: /removechannel [id]")
        return
    try:
        cid = int(command.args.strip())
    except ValueError:
        await message.answer("id должен быть целым числом.")
        return
    ok = await get_channel_manager().remove_channel(
        session, cid, owner_tg_id=message.from_user.id
    )
    await message.answer("Удалено." if ok else "Канал не найден.")


@router.callback_query(lambda c: c.data == "channels:list")
async def cb_channels(call: CallbackQuery, session: AsyncSession):
    if call.from_user is None:
        await call.answer()
        return
    channels = await get_channel_manager().list_channels(
        session, owner_tg_id=call.from_user.id
    )
    if not channels:
        await call.message.answer("У вас ещё нет каналов.")
    else:
        await call.message.answer("\n".join(f"#{c.id} — {c.name}" for c in channels))
    await call.answer()
