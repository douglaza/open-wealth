from datetime import date, timedelta

import pytest

from app.core.database import init_db
# from app.models.snapshot import Position, Snapshot
from app.domain.models import Position, Snapshot
from app.repositories.snapshot_repository import SnapshotRepository


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("OW_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    yield


@pytest.fixture()
def repo() -> SnapshotRepository:
    return SnapshotRepository()


def _snapshot(d: date, amounts: list[float]) -> Snapshot:
    return Snapshot(snapshot_date=d, positions=[
        Position(institution="Banco X", account_type="conta",
                 asset_name=f"Ativo {i}", category="Conta", amount=a)
        for i, a in enumerate(amounts)
    ])


def test_save_and_get_latest(tmp_db, repo):
    snap = _snapshot(date.today(), [1000.0, 500.0])
    repo.save(snap)

    loaded = repo.get_latest()
    assert loaded.snapshot_date == snap.snapshot_date
    assert loaded.total == 1500.0
    assert len(loaded.positions) == 2


def test_save_same_day_twice_does_not_duplicate(tmp_db, repo):
    d = date.today()
    repo.save(_snapshot(d, [100.0]))
    repo.save(_snapshot(d, [200.0, 300.0]))  # upsert

    loaded = repo.get_latest()
    assert loaded.total == 500.0          # não 100+200+300
    assert len(loaded.positions) == 2


def test_get_between_filters_by_period(tmp_db, repo):
    d1 = date.today() - timedelta(days=10)
    d2 = date.today()
    repo.save(_snapshot(d1, [100.0]))
    repo.save(_snapshot(d2, [200.0]))

    result = repo.get_between(d1, d2)
    assert len(result) == 2
    assert result[0].snapshot_date == d1  # ordenado

    only_recent = repo.get_between(d2, d2)
    assert len(only_recent) == 1 and only_recent[0].total == 200.0
