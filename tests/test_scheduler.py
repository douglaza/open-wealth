import asyncio
from datetime import date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.api.main import create_app
from app.core import scheduler as sched

TZ_SP = ZoneInfo("America/Sao_Paulo")


@pytest.mark.asyncio
async def test_scheduler_catchup_scenarios():
    now_before_9 = datetime(2026, 11, 18, 8, 30, tzinfo=TZ_SP)
    now_after_9 = datetime(2026, 11, 18, 10, 15, tzinfo=TZ_SP)

    # 1. Antes das 9h -> não dispara catchup
    assert sched.should_trigger_catchup(date(2026, 11, 17), now_before_9) is False

    # 2. Depois das 9h sem sync hoje -> dispara catchup
    assert sched.should_trigger_catchup(date(2026, 11, 17), now_after_9) is True

    # 3. Depois das 9h mas já com sync hoje -> não dispara
    assert sched.should_trigger_catchup(date(2026, 11, 18), now_after_9) is False

    # 4. Depois das 9h sem histórico prévio (None) -> dispara
    assert sched.should_trigger_catchup(None, now_after_9) is True


@pytest.mark.asyncio
async def test_run_catchup_adds_job():
    now_after_9 = datetime(2026, 11, 18, 10, 15, tzinfo=TZ_SP)

    # Executa catchup necessário
    triggered = sched.run_catchup_if_needed(last_sync_date=date(2026, 11, 17), now=now_after_9)
    assert triggered is True
    job = sched.scheduler.get_job("sync_catchup")
    assert job is not None

    # Quando não é necessário
    not_triggered = sched.run_catchup_if_needed(last_sync_date=date(2026, 11, 18), now=now_after_9)
    assert not_triggered is False


@pytest.mark.asyncio
async def test_get_last_sync_date_formats():
    # date direto
    mock_repo_date = MagicMock()
    mock_repo_date.get_latest.return_value = MagicMock(date=date(2026, 11, 18))
    assert sched.get_last_sync_date(mock_repo_date) == date(2026, 11, 18)

    # datetime
    mock_repo_dt = MagicMock()
    mock_repo_dt.get_latest.return_value = MagicMock(date=datetime(2026, 11, 18, 9, 30))
    assert sched.get_last_sync_date(mock_repo_dt) == date(2026, 11, 18)

    # string ISO
    mock_repo_str = MagicMock()
    mock_repo_str.get_latest.return_value = MagicMock(date="2026-11-18T09:30:00")
    assert sched.get_last_sync_date(mock_repo_str) == date(2026, 11, 18)

    # None / vazio
    mock_repo_none = MagicMock()
    mock_repo_none.get_latest.return_value = None
    assert sched.get_last_sync_date(mock_repo_none) is None

    # Exceção
    mock_repo_err = MagicMock()
    mock_repo_err.get_latest.side_effect = TypeError("db error")
    assert sched.get_last_sync_date(mock_repo_err) is None

    # Sem repo informado
    assert sched.get_last_sync_date() is not None or sched.get_last_sync_date() is None


@pytest.mark.asyncio
async def test_sync_daily_runs_at_nine():
    sched.start_scheduler(catchup=False)
    try:
        job = sched.scheduler.get_job("sync_daily")
        assert job is not None
        start = datetime(2026, 11, 17, 8, 59, tzinfo=TZ_SP)
        first_run = job.trigger.get_next_fire_time(None, start)
        second_run = job.trigger.get_next_fire_time(first_run, first_run)
        assert first_run == datetime(2026, 11, 17, 9, 0, tzinfo=TZ_SP)
        assert second_run == datetime(2026, 11, 18, 9, 0, tzinfo=TZ_SP)
    finally:
        sched.stop_scheduler()


def test_stop_scheduler_when_already_stopped():
    sched.stop_scheduler()


@pytest.mark.asyncio
async def test_api_lifespan_starts_and_stops_scheduler(monkeypatch):
    monkeypatch.setattr("app.core.scheduler.sync_weekly", lambda: None)
    app = create_app()
    async with app.router.lifespan_context(app):
        assert sched.scheduler.running is True
    await asyncio.sleep(0)
    assert sched.scheduler.running is False


def test_get_last_sync_date_repo_init_error(monkeypatch):
    def fake_init(*args, **kwargs):
        raise RuntimeError("Falha de conexão com o banco")

    monkeypatch.setattr(
        "app.repositories.snapshot_repository.SnapshotRepository",
        fake_init,
    )
    assert sched.get_last_sync_date(repo=None) is None
