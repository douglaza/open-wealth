# tests/test_scheduler.py
from app.core import scheduler as sched


def test_sync_weekly_runs():
    sched.start_scheduler()
    try:
        job = sched.scheduler.get_job("sync_weekly")
        assert job is not None
    finally:
        sched.stop_scheduler()
