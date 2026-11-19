from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.sync import sync_weekly

TZ_SP = ZoneInfo("America/Sao_Paulo")
scheduler = AsyncIOScheduler(timezone=TZ_SP)


def should_trigger_catchup(
    last_sync_date: date | None,
    now: datetime | None = None,
) -> bool:
    """Verifica se um sync de catch-up deve ser executado no startup."""
    current_time = now if now is not None else datetime.now(TZ_SP)
    today = current_time.date()

    if current_time.hour < 9:
        return False

    return last_sync_date != today


def get_last_sync_date(repo: Any = None) -> date | None:
    """Busca a data do snapshot mais recente."""
    target_repo = repo
    if target_repo is None:
        try:
            from app.repositories.snapshot_repository import SnapshotRepository

            target_repo = SnapshotRepository()
        except (ImportError, RuntimeError):
            return None

    try:
        if hasattr(target_repo, "get_latest"):
            latest = target_repo.get_latest()
            if latest and hasattr(latest, "date"):
                d = latest.date
                if isinstance(d, datetime):
                    return d.date()
                if isinstance(d, date):
                    return d
                if isinstance(d, str):
                    return date.fromisoformat(d[:10])
    except (TypeError, ValueError, AttributeError):
        pass
    return None


def run_catchup_if_needed(
    last_sync_date: date | None = None,
    now: datetime | None = None,
    repo: Any = None,
) -> bool:
    """Verifica a necessidade de catch-up e agenda execução imediata."""
    sync_date = last_sync_date if last_sync_date is not None else get_last_sync_date(repo=repo)

    if should_trigger_catchup(last_sync_date=sync_date, now=now):
        scheduler.add_job(
            sync_weekly,
            id="sync_catchup",
            replace_existing=True,
        )
        return True

    return False


def start_scheduler(catchup: bool = True) -> None:
    """Inicia o scheduler com job diário às 09:00 e executa catch-up se necessário."""
    trigger = CronTrigger(hour=9, minute=0, timezone=TZ_SP)
    scheduler.add_job(
        sync_weekly,
        trigger=trigger,
        id="sync_daily",
        replace_existing=True,
    )

    if catchup:
        run_catchup_if_needed()

    if not scheduler.running:
        scheduler.start()


def stop_scheduler() -> None:
    """Encerra o scheduler em execução."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
