from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.runtime import get_channel_manager
from models import ModerationAction, ModerationLog, Post, PostStatus

router = Router(name="moderation")


@router.callback_query(F.data.startswith("mod:approve:"))
async def cb_approve(call: CallbackQuery, session: AsyncSession):
    post_id = int(call.data.split(":")[2])
    post = await session.get(Post, post_id, options=[selectinload(Post.channel)])
    if not post:
        await call.answer("Пост не найден.", show_alert=True)
        return
    if post.status not in (PostStatus.PENDING_APPROVAL, PostStatus.DRAFT):
        await call.answer(f"Уже в статусе {post.status.value}.", show_alert=True)
        return

    try:
        await get_channel_manager().publish_post(session, post)
    except Exception as e:
        logger.exception("Publish failed: {}", e)
        await call.answer(f"Не удалось опубликовать: {e}", show_alert=True)
        return

    session.add(ModerationLog(
        post_id=post.id, action=ModerationAction.APPROVED,
        reason="manual approve", triggered_by="admin",
        actor_id=call.from_user.id,
    ))
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"Пост #{post.id} опубликован.")
    await call.answer()


@router.callback_query(F.data.startswith("mod:reject:"))
async def cb_reject(call: CallbackQuery, session: AsyncSession):
    post_id = int(call.data.split(":")[2])
    post = await session.get(Post, post_id)
    if not post:
        await call.answer("Пост не найден.", show_alert=True)
        return
    post.status = PostStatus.REJECTED
    session.add(ModerationLog(
        post_id=post.id, action=ModerationAction.REJECTED,
        reason="manual reject", triggered_by="admin",
        actor_id=call.from_user.id,
    ))
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"Пост #{post.id} отклонён.")
    await call.answer()
