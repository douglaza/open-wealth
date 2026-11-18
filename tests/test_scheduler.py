# tests/test_scheduler.py
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core import scheduler as sched


def test_sync_daily_runs_at_nine():
    sched.start_scheduler()
    try:
        job = sched.scheduler.get_job("sync_daily")
        assert job is not None
        timezone = ZoneInfo("America/Sao_Paulo")
        start = datetime(2026, 11, 17, 8, 59, tzinfo=timezone)
        first_run = job.trigger.get_next_fire_time(None, start)
        second_run = job.trigger.get_next_fire_time(first_run, first_run)

        assert first_run == datetime(2026, 11, 17, 9, 0, tzinfo=timezone)
        assert second_run == datetime(2026, 11, 18, 9, 0, tzinfo=timezone)
    finally:
        sched.stop_scheduler()
