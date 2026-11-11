import os
from datetime import date, timedelta

import pytest

from app.core.database import init_db
from app.models.snapshot import Position, Snapshot
from app.repositories import snapshot_repository


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("OW_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    yield


def _snapshot(d: date, amounts: list[float]) -> Snapshot:
    return Snapshot(snapshot_date=d, positions=[
        Position(institution="Banco X", account_type="conta",
                 asset_name=f"Ativo {i}", category="Conta", amount=a)
        for i, a in enumerate(amounts)
    ])


def test_save_and_get_latest(tmp_db):
    snap = _snapshot(date.today(), [1000.0, 500.0])
    snapshot_repository.save(snap)

    loaded = snapshot_repository.get_latest()
    assert loaded.snapshot_date == snap.snapshot_date
    assert loaded.total == 1500.0
    assert len(loaded.positions) == 2


def test_save_same_day_twice_does_not_duplicate(tmp_db):
    d = date.today()
    snapshot_repository.save(_snapshot(d, [100.0]))
    snapshot_repository.save(_snapshot(d, [200.0, 300.0]))  # upsert

    loaded = snapshot_repository.get_latest()
    assert loaded.total == 500.0          # não 100+200+300
    assert len(loaded.positions) == 2


def test_get_between_filters_by_period(tmp_db):
    d1 = date.today() - timedelta(days=10)
    d2 = date.today()
    snapshot_repository.save(_snapshot(d1, [100.0]))
    snapshot_repository.save(_snapshot(d2, [200.0]))

    result = snapshot_repository.get_between(d1, d2)
    assert len(result) == 2
    assert result[0].snapshot_date == d1  # ordenado

    only_recent = snapshot_repository.get_between(d2, d2)
    assert len(only_recent) == 1 and only_recent[0].total == 200.0
