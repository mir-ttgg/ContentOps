from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config import settings
from models import Channel, MediaType, Post, PostSource, PostStatus, ScheduleSlot
from models.db import session_scope


# Module-level functions to ensure APScheduler can serialize them in the jobstore.

async def _publish_scheduled_post(post_id: int) -> None:
    from bot.runtime import get_channel_manager, get_moderation_service
    from services.moderation import ModerationDecision
    from models import ModerationLog, ModerationAction

    channel_mgr = get_channel_manager()
    moderation = get_moderation_service()
    async with session_scope() as session:
        post = await session.get(Post, post_id, options=[selectinload(Post.channel)])
        if not post or post.status not in (PostStatus.APPROVED, PostStatus.DRAFT, PostStatus.PENDING_APPROVAL):
            logger.info("Scheduled post {} skipped (status={})", post_id, post.status if post else None)
            return
        # apply moderation gate one more time for safety
        outcome = await moderation.evaluate(post.text, post.channel)
        if outcome.decision == ModerationDecision.AUTO_DELETE:
            post.status = PostStatus.REJECTED
            session.add(ModerationLog(
                post_id=post.id, action=ModerationAction.AUTO_DELETED,
                reason=outcome.reason, triggered_by="scheduler",
            ))
            return
        if outcome.decision == ModerationDecision.NEEDS_APPROVAL:
            post.status = PostStatus.PENDING_APPROVAL
            session.add(ModerationLog(
                post_id=post.id, action=ModerationAction.FLAGGED,
                reason=outcome.reason, triggered_by="scheduler",
            ))
            return
        await channel_mgr.publish_post(session, post)


async def _autopost_for_channel(channel_id: int) -> None:
    """Generate a post via AI and run it through the publication pipeline."""
    from bot.runtime import (
        get_ai_provider,
        get_channel_manager,
        get_moderation_service,
    )
    from services.moderation import ModerationDecision
    from models import ModerationLog, ModerationAction

    ai = get_ai_provider()
    channel_mgr = get_channel_manager()
    moderation = get_moderation_service()

    async with session_scope() as session:
        channel = await session.get(Channel, channel_id)
        if not channel or not channel.auto_post:
            return
        try:
            text = await ai.generate_post(
                topic="next scheduled post",
                channel_context=channel.system_prompt or channel.name,
            )
        except Exception as e:
            logger.exception("Autopost AI generation failed for channel {}: {}", channel_id, e)
            return

        post = Post(
            channel_id=channel.id,
            text=text,
            media_type=MediaType.NONE,
            status=PostStatus.DRAFT,
            source=PostSource.AI_AUTO,
        )
        session.add(post)
        await session.flush()

        outcome = await moderation.evaluate(text, channel)
        if outcome.decision == ModerationDecision.AUTO_DELETE:
            post.status = PostStatus.REJECTED
            session.add(ModerationLog(
                post_id=post.id, action=ModerationAction.AUTO_DELETED,
                reason=outcome.reason, triggered_by="autopost",
            ))
            return
        if outcome.decision == ModerationDecision.NEEDS_APPROVAL:
            post.status = PostStatus.PENDING_APPROVAL
            session.add(ModerationLog(
                post_id=post.id, action=ModerationAction.FLAGGED,
                reason=outcome.reason, triggered_by="autopost",
            ))
            return

        await channel_mgr.publish_post(session, post)


class PostScheduler:
    """Wraps APScheduler — schedules one-off post publishes and recurring autoposts."""

    def __init__(self):
        # APScheduler's SQLAlchemyJobStore is sync; use the sync URL form.
        sync_url = settings.database_url.replace("+asyncpg", "")
        jobstores = {"default": SQLAlchemyJobStore(url=sync_url)}
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone=settings.tz,
        )

    def start(self) -> None:
        self.scheduler.start()
        logger.info("Scheduler started (tz={})", settings.tz)

    async def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)

    # ---------- one-off scheduled posts ----------

    def schedule_post(self, post_id: int, run_at: datetime) -> str:
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        job = self.scheduler.add_job(
            _publish_scheduled_post,
            trigger=DateTrigger(run_date=run_at),
            args=[post_id],
            id=f"post:{post_id}",
            replace_existing=True,
            misfire_grace_time=300,
        )
        return job.id

    def cancel_post(self, post_id: int) -> bool:
        job_id = f"post:{post_id}"
        try:
            self.scheduler.remove_job(job_id)
            return True
        except Exception:
            return False

    # ---------- recurring autoposts ----------

    def sync_channel_schedule(self, channel: Channel, slots: Sequence[ScheduleSlot]) -> None:
        """Rebuild cron jobs for a channel from its ScheduleSlot list."""
        # remove existing autopost jobs for this channel
        for job in list(self.scheduler.get_jobs()):
            if job.id.startswith(f"autopost:{channel.id}:"):
                self.scheduler.remove_job(job.id)

        if not channel.auto_post:
            return

        for slot in slots:
            if not slot.enabled:
                continue
            day_of_week = ",".join(str(d) for d in slot.weekday_list) or "*"
            trigger = CronTrigger(
                day_of_week=day_of_week,
                hour=slot.time_of_day.hour,
                minute=slot.time_of_day.minute,
                timezone=settings.tz,
            )
            self.scheduler.add_job(
                _autopost_for_channel,
                trigger=trigger,
                args=[channel.id],
                id=f"autopost:{channel.id}:{slot.id}",
                replace_existing=True,
                misfire_grace_time=600,
            )

    async def sync_all(self) -> None:
        async with session_scope() as session:
            result = await session.execute(
                select(Channel).options(selectinload(Channel.schedule_slots))
            )
            channels = result.scalars().all()
        for ch in channels:
            self.sync_channel_schedule(ch, ch.schedule_slots)
        logger.info("Synced schedules for {} channel(s)", len(channels))
