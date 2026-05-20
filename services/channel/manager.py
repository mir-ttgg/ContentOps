from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from aiogram import Bot
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.types import FSInputFile, InputFile
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Channel, MediaType, Post, PostStatus


class ChannelError(Exception):
    pass


class ChannelManager:
    """Owns CRUD for channels and post publishing via Telegram Bot API."""

    def __init__(self, bot: Bot):
        self.bot = bot

    # ---------- channels CRUD ----------

    async def list_channels(self, session: AsyncSession) -> Sequence[Channel]:
        result = await session.execute(select(Channel).order_by(Channel.id))
        return result.scalars().all()

    async def get_channel(self, session: AsyncSession, channel_id: int) -> Channel | None:
        return await session.get(Channel, channel_id)

    async def get_by_tg_id(self, session: AsyncSession, tg_channel_id: int) -> Channel | None:
        result = await session.execute(
            select(Channel).where(Channel.tg_channel_id == tg_channel_id)
        )
        return result.scalar_one_or_none()

    async def add_channel(
        self,
        session: AsyncSession,
        tg_channel_id: int,
    ) -> Channel:
        existing = await self.get_by_tg_id(session, tg_channel_id)
        if existing:
            return existing

        try:
            chat = await self.bot.get_chat(tg_channel_id)
        except Exception as e:
            raise ChannelError(f"Не удалось получить доступ к чату {tg_channel_id}: {e}") from e

        # ensure bot is admin with publish rights
        me = await self.bot.get_me()
        try:
            member = await self.bot.get_chat_member(tg_channel_id, me.id)
        except Exception as e:
            raise ChannelError(f"Не удалось проверить статус бота: {e}") from e

        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            raise ChannelError("Бот должен быть добавлен в канал как администратор.")

        channel = Channel(
            tg_channel_id=tg_channel_id,
            name=chat.title or str(tg_channel_id),
            username=chat.username,
            system_prompt="",
            settings_json={
                "approval_required": False,
                "auto_post": False,
                "auto_delete": False,
                "stopwords": [],
            },
        )
        session.add(channel)
        await session.flush()
        logger.info("Added channel {} ({})", channel.name, channel.tg_channel_id)
        return channel

    async def remove_channel(self, session: AsyncSession, channel_id: int) -> bool:
        ch = await self.get_channel(session, channel_id)
        if not ch:
            return False
        await session.delete(ch)
        return True

    # ---------- publishing ----------

    async def publish_post(self, session: AsyncSession, post: Post) -> Post:
        channel = post.channel or await self.get_channel(session, post.channel_id)
        if not channel:
            raise ChannelError("Post has no channel.")

        try:
            message = await self._send(channel.tg_channel_id, post)
        except Exception as e:
            logger.exception("Failed to publish post {}: {}", post.id, e)
            raise

        post.status = PostStatus.PUBLISHED
        post.published_at = datetime.now(timezone.utc)
        post.tg_message_id = message.message_id
        await session.flush()
        logger.info("Published post id={} channel={} msg_id={}", post.id, channel.name, message.message_id)
        return post

    async def delete_published(self, session: AsyncSession, post: Post) -> bool:
        if not post.tg_message_id:
            return False
        channel = post.channel or await self.get_channel(session, post.channel_id)
        if not channel:
            return False
        try:
            await self.bot.delete_message(channel.tg_channel_id, post.tg_message_id)
        except Exception as e:
            logger.warning("Failed to delete tg message: {}", e)
            return False
        post.status = PostStatus.DELETED
        await session.flush()
        return True

    async def edit_published(self, session: AsyncSession, post: Post, new_text: str) -> bool:
        if not post.tg_message_id:
            return False
        channel = post.channel or await self.get_channel(session, post.channel_id)
        if not channel:
            return False
        try:
            if post.media_type == MediaType.NONE:
                await self.bot.edit_message_text(
                    new_text,
                    chat_id=channel.tg_channel_id,
                    message_id=post.tg_message_id,
                    parse_mode=ParseMode.HTML,
                )
            else:
                await self.bot.edit_message_caption(
                    chat_id=channel.tg_channel_id,
                    message_id=post.tg_message_id,
                    caption=new_text,
                    parse_mode=ParseMode.HTML,
                )
        except Exception as e:
            logger.warning("Failed to edit tg message: {}", e)
            return False
        post.text = new_text
        await session.flush()
        return True

    async def _send(self, chat_id: int, post: Post):
        media: str | InputFile | None
        if post.media_file_id:
            media = post.media_file_id
        elif post.media_url:
            media = post.media_url
        else:
            media = None

        if post.media_type == MediaType.NONE or media is None:
            return await self.bot.send_message(
                chat_id, post.text, parse_mode=ParseMode.HTML, disable_web_page_preview=False
            )
        if post.media_type == MediaType.PHOTO:
            return await self.bot.send_photo(
                chat_id, photo=media, caption=post.text or None, parse_mode=ParseMode.HTML
            )
        if post.media_type == MediaType.VIDEO:
            return await self.bot.send_video(
                chat_id, video=media, caption=post.text or None, parse_mode=ParseMode.HTML
            )
        if post.media_type == MediaType.DOCUMENT:
            return await self.bot.send_document(
                chat_id, document=media, caption=post.text or None, parse_mode=ParseMode.HTML
            )
        raise ChannelError(f"Unsupported media type: {post.media_type}")
