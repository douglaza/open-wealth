import pytest
from app.core.database import init_db

@pytest.fixture(autouse=True)
def banco_limpo(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("OW_DB_PATH", str(db_file))
    import app.core.database as db_mod
    monkeypatch.setattr(db_mod, "_conn", None, raising=False)  # reseta cache, se existir
    init_db()
    yield


@pytest.fixture(autouse=True)
def banco_limpo(tmp_path, monkeypatch):
    """Cada teste roda contra um banco SQLite novo e temporário."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("OW_DB_PATH", str(db_file))
    init_db()
    yield


# tmp_db = banco_limpo

