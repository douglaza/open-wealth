from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.sync import sync_weekly

TZ_SP = ZoneInfo("America/Sao_Paulo")

scheduler = AsyncIOScheduler(timezone=TZ_SP)


def start_scheduler() -> None:
    trigger = CronTrigger(hour=9, minute=0, timezone=TZ_SP)
    scheduler.add_job(
        sync_weekly,
        trigger=trigger,
        id="sync_daily",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
