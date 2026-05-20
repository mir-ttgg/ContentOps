from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.runtime import (
    get_ai_provider,
    get_channel_manager,
    get_moderation_service,
    get_scheduler,
    set_runtime,
)
from config import settings
from models import (
    Channel,
    MediaType,
    ModerationAction,
    ModerationLog,
    Post,
    PostSource,
    PostStatus,
    ScheduleSlot,
)
from models.db import SessionLocal
from services.ai import build_provider
from services.channel.manager import ChannelManager
from services.moderation import ModerationDecision, ModerationService
from services.scheduler.scheduler import PostScheduler
from webapp.auth import require_admin
from webapp.schemas import (
    AIGenerateIn,
    AIGenerateOut,
    ChannelOut,
    ChannelSettingsIn,
    DashboardOut,
    ModerationLogOut,
    PostIn,
    PostOut,
    ScheduleSlotIn,
    ScheduleSlotOut,
)


STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        ai = build_provider()
    except Exception as e:
        logger.warning("WebApp: AI provider disabled: {}", e)
        ai = None

    channel_mgr = ChannelManager(bot)
    moderation = ModerationService(ai)
    scheduler = PostScheduler()
    set_runtime(
        bot=bot,
        channel_manager=channel_mgr,
        moderation=moderation,
        scheduler=scheduler,
        ai=ai,
    )
    scheduler.start()
    await scheduler.sync_all()
    try:
        yield
    finally:
        await scheduler.shutdown()
        await bot.session.close()


app = FastAPI(title="ContentOps Admin API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# -------------------- Channels --------------------

async def _owned_channel(
    session: AsyncSession,
    channel_id: int,
    owner_tg_id: int,
    *,
    with_slots: bool = False,
) -> Channel:
    opts = [selectinload(Channel.schedule_slots)] if with_slots else []
    ch = await session.get(Channel, channel_id, options=opts)
    if not ch or ch.owner_tg_id != owner_tg_id:
        raise HTTPException(404, "Channel not found")
    return ch


@app.get("/api/channels", response_model=list[ChannelOut])
async def list_channels(
    owner: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    chs = await get_channel_manager().list_channels(session, owner_tg_id=owner)
    return [ChannelOut.from_orm(c) for c in chs]


@app.get("/api/channels/{channel_id}", response_model=ChannelOut)
async def get_channel(
    channel_id: int,
    owner: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    ch = await _owned_channel(session, channel_id, owner)
    return ChannelOut.from_orm(ch)


@app.patch("/api/channels/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: int,
    payload: ChannelSettingsIn,
    owner: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    ch = await _owned_channel(session, channel_id, owner, with_slots=True)
    if payload.system_prompt is not None:
        ch.system_prompt = payload.system_prompt
    s = dict(ch.settings_json or {})
    for field in ("approval_required", "auto_post", "auto_delete", "ai_model"):
        val = getattr(payload, field)
        if val is not None:
            s[field] = val
    if payload.stopwords is not None:
        s["stopwords"] = payload.stopwords
    ch.settings_json = s
    await session.flush()
    get_scheduler().sync_channel_schedule(ch, ch.schedule_slots)
    return ChannelOut.from_orm(ch)


# -------------------- Posts --------------------

@app.get("/api/posts", response_model=list[PostOut])
async def list_posts(
    channel_id: int | None = None,
    status_filter: PostStatus | None = None,
    limit: int = 50,
    owner: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    q = (
        select(Post)
        .join(Channel, Channel.id == Post.channel_id)
        .where(Channel.owner_tg_id == owner)
        .order_by(Post.created_at.desc())
        .limit(min(limit, 200))
    )
    if channel_id is not None:
        q = q.where(Post.channel_id == channel_id)
    if status_filter is not None:
        q = q.where(Post.status == status_filter)
    result = await session.execute(q)
    return [PostOut.from_orm(p) for p in result.scalars().all()]


async def _owned_post(session: AsyncSession, post_id: int, owner: int) -> Post:
    post = await session.get(Post, post_id, options=[selectinload(Post.channel)])
    if not post or not post.channel or post.channel.owner_tg_id != owner:
        raise HTTPException(404, "Post not found")
    return post


@app.post("/api/posts", response_model=PostOut)
async def create_post(
    payload: PostIn,
    actor: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    channel = await _owned_channel(session, payload.channel_id, actor)

    post = Post(
        channel_id=channel.id,
        text=payload.text or "",
        media_url=payload.media_url,
        media_file_id=payload.media_file_id,
        media_type=payload.media_type,
        scheduled_at=payload.scheduled_at,
        source=payload.source,
        status=PostStatus.DRAFT,
        created_by=actor,
    )
    session.add(post)
    await session.flush()

    moderation = get_moderation_service()
    outcome = await moderation.evaluate(post.text, channel)
    if outcome.decision == ModerationDecision.AUTO_DELETE:
        post.status = PostStatus.REJECTED
        session.add(ModerationLog(
            post_id=post.id, action=ModerationAction.AUTO_DELETED,
            reason=outcome.reason, triggered_by="webapp", actor_id=actor,
        ))
        return PostOut.from_orm(post)
    if outcome.decision == ModerationDecision.NEEDS_APPROVAL:
        post.status = PostStatus.PENDING_APPROVAL
        session.add(ModerationLog(
            post_id=post.id, action=ModerationAction.FLAGGED,
            reason=outcome.reason, triggered_by="webapp", actor_id=actor,
        ))
        await _notify_admins_for_approval(post, channel)
        return PostOut.from_orm(post)

    # PUBLISH
    if payload.publish_now or not payload.scheduled_at:
        # publish immediately
        post.status = PostStatus.APPROVED
        await get_channel_manager().publish_post(session, post)
    else:
        post.status = PostStatus.APPROVED
        get_scheduler().schedule_post(post.id, payload.scheduled_at)
    return PostOut.from_orm(post)


@app.delete("/api/posts/{post_id}")
async def delete_post(
    post_id: int,
    actor: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    post = await _owned_post(session, post_id, actor)

    if post.status == PostStatus.PUBLISHED:
        await get_channel_manager().delete_published(session, post)
    else:
        get_scheduler().cancel_post(post.id)
        post.status = PostStatus.DELETED

    session.add(ModerationLog(
        post_id=post.id, action=ModerationAction.REJECTED,
        reason="manual delete via webapp", triggered_by="webapp", actor_id=actor,
    ))
    return {"ok": True}


@app.post("/api/posts/{post_id}/approve", response_model=PostOut)
async def approve_post(
    post_id: int,
    actor: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    post = await _owned_post(session, post_id, actor)
    if post.status not in (PostStatus.PENDING_APPROVAL, PostStatus.DRAFT):
        raise HTTPException(400, f"Cannot approve from {post.status}")
    await get_channel_manager().publish_post(session, post)
    session.add(ModerationLog(
        post_id=post.id, action=ModerationAction.APPROVED,
        reason="webapp approve", triggered_by="webapp", actor_id=actor,
    ))
    return PostOut.from_orm(post)


@app.post("/api/posts/{post_id}/reject", response_model=PostOut)
async def reject_post(
    post_id: int,
    actor: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    post = await _owned_post(session, post_id, actor)
    post.status = PostStatus.REJECTED
    session.add(ModerationLog(
        post_id=post.id, action=ModerationAction.REJECTED,
        reason="webapp reject", triggered_by="webapp", actor_id=actor,
    ))
    return PostOut.from_orm(post)


# -------------------- AI --------------------

@app.post("/api/ai/generate", response_model=AIGenerateOut)
async def ai_generate(
    payload: AIGenerateIn,
    owner: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    channel = await _owned_channel(session, payload.channel_id, owner)
    try:
        ai = get_ai_provider()
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    if payload.improve_text:
        text = await ai.improve_post(payload.improve_text)
    else:
        text = await ai.generate_post(payload.topic, channel.system_prompt or channel.name)
    return AIGenerateOut(text=text)


# -------------------- Schedule slots --------------------

@app.get("/api/channels/{channel_id}/slots", response_model=list[ScheduleSlotOut])
async def list_slots(
    channel_id: int,
    owner: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _owned_channel(session, channel_id, owner)
    result = await session.execute(
        select(ScheduleSlot).where(ScheduleSlot.channel_id == channel_id).order_by(ScheduleSlot.time_of_day)
    )
    slots = result.scalars().all()
    return [
        ScheduleSlotOut(
            id=s.id, time_of_day=s.time_of_day,
            days_of_week=s.weekday_list, enabled=s.enabled,
        )
        for s in slots
    ]


@app.post("/api/channels/{channel_id}/slots", response_model=ScheduleSlotOut)
async def add_slot(
    channel_id: int,
    payload: ScheduleSlotIn,
    owner: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    channel = await _owned_channel(session, channel_id, owner, with_slots=True)
    slot = ScheduleSlot(
        channel_id=channel.id,
        time_of_day=payload.time_of_day,
        days_of_week=",".join(str(d) for d in payload.days_of_week),
        enabled=payload.enabled,
    )
    session.add(slot)
    await session.flush()
    channel.schedule_slots.append(slot)
    get_scheduler().sync_channel_schedule(channel, channel.schedule_slots)
    return ScheduleSlotOut(
        id=slot.id, time_of_day=slot.time_of_day,
        days_of_week=slot.weekday_list, enabled=slot.enabled,
    )


@app.delete("/api/slots/{slot_id}")
async def delete_slot(
    slot_id: int,
    owner: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    slot = await session.get(ScheduleSlot, slot_id)
    if not slot:
        raise HTTPException(404, "Slot not found")
    channel_id = slot.channel_id
    channel = await _owned_channel(session, channel_id, owner, with_slots=True)
    await session.delete(slot)
    await session.flush()
    await session.refresh(channel, attribute_names=["schedule_slots"])
    get_scheduler().sync_channel_schedule(channel, channel.schedule_slots)
    return {"ok": True}


# -------------------- Moderation log & dashboard --------------------

@app.get("/api/moderation/log", response_model=list[ModerationLogOut])
async def moderation_log(
    limit: int = 100,
    owner: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ModerationLog)
        .join(Post, Post.id == ModerationLog.post_id)
        .join(Channel, Channel.id == Post.channel_id)
        .where(Channel.owner_tg_id == owner)
        .order_by(ModerationLog.created_at.desc())
        .limit(min(limit, 500))
    )
    return [
        ModerationLogOut(
            id=m.id, post_id=m.post_id, action=m.action.value,
            reason=m.reason, triggered_by=m.triggered_by, created_at=m.created_at,
        )
        for m in result.scalars().all()
    ]


@app.get("/api/dashboard", response_model=DashboardOut)
async def dashboard(
    owner: int = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    today = datetime.now(timezone.utc) - timedelta(hours=24)
    owned_posts = (
        select(Post.id)
        .join(Channel, Channel.id == Post.channel_id)
        .where(Channel.owner_tg_id == owner)
        .subquery()
    )
    channels_cnt = (await session.execute(
        select(func.count(Channel.id)).where(Channel.owner_tg_id == owner)
    )).scalar_one()
    posts_today = (await session.execute(
        select(func.count(Post.id))
        .where(Post.id.in_(select(owned_posts.c.id)))
        .where(Post.published_at >= today)
    )).scalar_one()
    queue = (await session.execute(
        select(func.count(Post.id))
        .where(Post.id.in_(select(owned_posts.c.id)))
        .where(Post.scheduled_at.is_not(None), Post.status == PostStatus.APPROVED)
    )).scalar_one()
    pending = (await session.execute(
        select(func.count(Post.id))
        .where(Post.id.in_(select(owned_posts.c.id)))
        .where(Post.status == PostStatus.PENDING_APPROVAL)
    )).scalar_one()
    recent = (await session.execute(
        select(Post)
        .join(Channel, Channel.id == Post.channel_id)
        .where(Channel.owner_tg_id == owner)
        .order_by(Post.created_at.desc())
        .limit(10)
    )).scalars().all()
    return DashboardOut(
        channels=channels_cnt,
        posts_today=posts_today,
        queue=queue,
        pending_approval=pending,
        recent=[PostOut.from_orm(p) for p in recent],
    )


# -------------------- helpers --------------------

async def _notify_admins_for_approval(post: Post, channel: Channel) -> None:
    from bot.keyboards.inline import moderation_kb

    bot = get_channel_manager().bot
    text = (
        f"<b>Требуется одобрение</b>\n"
        f"Канал: {channel.name}\n"
        f"Пост #{post.id}\n\n"
        f"{post.text[:1000]}"
    )
    kb = moderation_kb(post.id)
    try:
        await bot.send_message(channel.owner_tg_id, text, reply_markup=kb)
    except Exception as e:
        logger.warning("Notify owner {} failed: {}", channel.owner_tg_id, e)


# -------------------- static --------------------

if STATIC_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=STATIC_DIR, html=True), name="webapp")


@app.get("/healthz")
async def healthz():
    return {"ok": True}
