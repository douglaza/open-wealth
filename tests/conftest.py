# tests/conftest.py
from datetime import date

import pytest

from app.core.database import init_db, get_connection
from app.domain.models import Position, Snapshot
from app.repositories.snapshot_repository import SnapshotRepository


@pytest.fixture(autouse=True)
def banco_limpo(tmp_path, monkeypatch):
    """Cada teste roda contra um banco SQLite novo e temporário."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("OW_DB_PATH", str(db_file))
    import app.core.database as db_mod
    monkeypatch.setattr(db_mod, "_conn", None, raising=False)
    init_db()
    yield


@pytest.fixture
def repo():
    """Repo sobre o banco temporário criado pelo banco_limpo."""
    conn = get_connection()
    yield SnapshotRepository(conn)
    conn.close()


@pytest.fixture
def repo_com_dados(repo):
    repo.save_all([
        Snapshot(snapshot_date=date(2025, 1, 1), positions=[
            Position(institution="XP", account_type="broker",
                     asset_name="ITSA4", category="Ações", amount=1000.0),
        ]),
        Snapshot(snapshot_date=date(2025, 2, 1), positions=[
            Position(institution="XP", account_type="broker",
                     asset_name="ITSA4", category="Ações", amount=1100.0),
        ]),
        Snapshot(snapshot_date=date(2025, 3, 1), positions=[
            Position(institution="XP", account_type="broker",
                     asset_name="ITSA4", category="Ações", amount=1200.0),
        ]),
    ])
    return repo
