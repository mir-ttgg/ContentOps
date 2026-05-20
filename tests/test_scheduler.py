from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from unittest.mock import patch

import pytest

from models import Channel, ScheduleSlot


@pytest.fixture
def fake_settings(monkeypatch, tmp_path):
    # APScheduler needs a usable DB; point it at SQLite in-memory file
    from config import settings

    db_file = tmp_path / "scheduler.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_file}")
    yield settings


def _make_channel(auto_post: bool = True) -> Channel:
    ch = Channel(
        id=1, tg_channel_id=-100, name="t", username=None, system_prompt="",
        settings_json={"auto_post": auto_post, "approval_required": False,
                       "auto_delete": False, "stopwords": []},
    )
    return ch


def test_schedule_post_creates_job(fake_settings):
    from services.scheduler.scheduler import PostScheduler

    sched = PostScheduler()
    run_at = datetime.now(timezone.utc) + timedelta(hours=1)
    job_id = sched.schedule_post(post_id=42, run_at=run_at)
    assert job_id == "post:42"
    job = sched.scheduler.get_job("post:42")
    assert job is not None
    assert job.args == [42]


def test_cancel_post(fake_settings):
    from services.scheduler.scheduler import PostScheduler

    sched = PostScheduler()
    sched.schedule_post(7, datetime.now(timezone.utc) + timedelta(hours=1))
    assert sched.cancel_post(7) is True
    assert sched.cancel_post(7) is False  # already gone


def test_sync_channel_schedule_creates_cron_jobs(fake_settings):
    from services.scheduler.scheduler import PostScheduler

    sched = PostScheduler()
    ch = _make_channel(auto_post=True)
    slots = [
        ScheduleSlot(id=1, channel_id=1, time_of_day=time(9, 0), days_of_week="", enabled=True),
        ScheduleSlot(id=2, channel_id=1, time_of_day=time(19, 30), days_of_week="0,1,2,3,4", enabled=True),
        ScheduleSlot(id=3, channel_id=1, time_of_day=time(12, 0), days_of_week="", enabled=False),
    ]
    sched.sync_channel_schedule(ch, slots)
    job_ids = {j.id for j in sched.scheduler.get_jobs()}
    assert "autopost:1:1" in job_ids
    assert "autopost:1:2" in job_ids
    assert "autopost:1:3" not in job_ids  # disabled


def test_sync_skips_when_auto_post_off(fake_settings):
    from services.scheduler.scheduler import PostScheduler

    sched = PostScheduler()
    ch = _make_channel(auto_post=False)
    slots = [ScheduleSlot(id=1, channel_id=1, time_of_day=time(9, 0), days_of_week="", enabled=True)]
    sched.sync_channel_schedule(ch, slots)
    assert sched.scheduler.get_jobs() == []
