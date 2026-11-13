import pytest
from app.core.database import init_db


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("OW_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    yield



@pytest.fixture(autouse=True)
def banco_limpo(tmp_path, monkeypatch):
    """Cada teste roda contra um banco SQLite novo e temporário."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("OW_DB_PATH", str(db_file))
    init_db()
    yield
    # nada a limpar: o arquivo morre com o tmp_path
