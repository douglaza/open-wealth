import sqlite3
import sys
from types import ModuleType

import pytest

from app.core import database

# ---- _sqlite_path ----


def test_sqlite_path_do_ambiente(monkeypatch):
    monkeypatch.setenv("OW_DB_PATH", "/tmp/outro.db")
    assert database._sqlite_path() == "/tmp/outro.db"


def test_sqlite_path_da_url(monkeypatch):
    monkeypatch.delenv("OW_DB_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/meu.db")
    assert database._sqlite_path() == "data/meu.db"


def test_sqlite_path_default(monkeypatch):
    monkeypatch.delenv("OW_DB_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    assert database._sqlite_path() == "data/database.db"


# ---- _is_postgres ----


def test_is_postgres_variants(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host/db")
    assert database._is_postgres() is True
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    assert database._is_postgres() is True
    monkeypatch.setenv("DATABASE_URL", "sqlite:///x.db")
    assert database._is_postgres() is False


# ---- init_db (sqlite) ----


def test_init_db_cria_tabelas_sqlite(tmp_path, monkeypatch):
    db = tmp_path / "sub" / "test.db"
    monkeypatch.setenv("OW_DB_PATH", str(db))
    database.init_db()
    with sqlite3.connect(db) as conn:
        tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"items", "accounts", "investments", "transactions", "snapshots"} <= tabelas


def test_init_db_postgres_chama_executescript(monkeypatch):
    chamadas = {}

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def executescript(self, script):
            chamadas["script"] = script

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    monkeypatch.setattr(database, "get_connection", lambda: FakeConn())
    database.init_db()
    assert "snapshots" in chamadas["script"]


# ---- _SQLiteConn: rollback no contexto com exceção ----


def test_sqlite_conn_rollback_em_erro(tmp_path, monkeypatch):
    monkeypatch.setenv("OW_DB_PATH", str(tmp_path / "t.db"))
    database.init_db()

    with pytest.raises(ValueError):
        with database.get_connection() as conn:
            conn.execute(
                "INSERT INTO items (id, institution) VALUES (?, ?)",
                ("i1", "Banco Teste"),
            )
            raise ValueError("boom")

    with sqlite3.connect(tmp_path / "t.db") as conn:
        n = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    assert n == 0  # rollback não gravou nada


def test_sqlite_conn_commit_sucesso(tmp_path, monkeypatch):
    monkeypatch.setenv("OW_DB_PATH", str(tmp_path / "t.db"))
    database.init_db()
    with database.get_connection() as conn:
        conn.execute("INSERT INTO items (id, institution) VALUES (?, ?)", ("i1", "Banco"))
    with sqlite3.connect(tmp_path / "t.db") as c:
        assert c.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1


def test_postgres_connection_wrapper(monkeypatch):
    calls = []

    class FakeCursor:
        def executemany(self, sql, rows):
            calls.append(("executemany", sql, list(rows)))

        def close(self):
            calls.append(("cursor_close",))

    class FakeConnection:
        def execute(self, sql, params=()):
            calls.append(("execute", sql, params))
            return "cursor"

        def cursor(self):
            return FakeCursor()

        def commit(self):
            calls.append(("commit",))

        def rollback(self):
            calls.append(("rollback",))

        def close(self):
            calls.append(("close",))

    fake_connection = FakeConnection()
    psycopg = ModuleType("psycopg")
    psycopg.connect = lambda url, row_factory: (
        calls.append(("connect", url, row_factory)) or fake_connection
    )
    psycopg_rows = ModuleType("psycopg.rows")
    psycopg_rows.dict_row = object()
    monkeypatch.setitem(sys.modules, "psycopg", psycopg)
    monkeypatch.setitem(sys.modules, "psycopg.rows", psycopg_rows)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test/db")

    conn = database.get_connection()
    assert conn.execute("SELECT ?", (1,)) == "cursor"
    conn.executemany("INSERT INTO t VALUES (?)", [(1,), (2,)])
    conn.executescript(" SELECT 1; ; SELECT 2; ")
    conn.commit()
    conn.rollback()
    conn.close()
    with database.get_connection():
        pass
    with pytest.raises(RuntimeError, match="rollback"):
        with database.get_connection():
            raise RuntimeError("rollback")

    assert ("execute", "SELECT %s", (1,)) in calls
    assert ("executemany", "INSERT INTO t VALUES (%s)", [(1,), (2,)]) in calls
    assert ("execute", "SELECT 1", ()) in calls
    assert ("execute", "SELECT 2", ()) in calls
    assert calls.count(("cursor_close",)) == 1
    assert calls.count(("commit",)) == 2
    assert calls.count(("rollback",)) == 2
    assert calls.count(("close",)) == 3
