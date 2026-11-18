import os
import sqlite3
from pathlib import Path

from app.core.config import DATABASE_URL


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", DATABASE_URL)


def _sqlite_path() -> str:
    configured_path = os.environ.get("OW_DB_PATH")
    if configured_path:
        return configured_path

    url = _database_url()
    if url.startswith("sqlite:///"):
        return url.removeprefix("sqlite:///")
    return "data/database.db"


def init_db():
    if _is_postgres():
        with get_connection() as conn:
            conn.executescript(SCHEMA_PG)
        print("✅ Banco PostgreSQL pronto")
        return

    path = _sqlite_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
    print(f"✅ Banco pronto em: {path}")


def _is_postgres() -> bool:
    return _database_url().startswith(("postgres://", "postgresql://"))


class _SQLiteConn:
    def __init__(self):
        self._conn = sqlite3.connect(_sqlite_path())
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql, params=()):
        return self._conn.execute(sql, params)

    def executemany(self, sql, seq):
        return self._conn.executemany(sql, seq)

    def executescript(self, script):
        self._conn.executescript(script)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        return False


class _PostgresConn:
    def __init__(self):
        import psycopg
        from psycopg.rows import dict_row

        self._conn = psycopg.connect(_database_url(), row_factory=dict_row)

    def execute(self, sql, params=()):
        return self._conn.execute(sql.replace("?", "%s"), params)

    def executemany(self, sql, seq):
        cur = self._conn.cursor()
        try:
            cur.executemany(sql.replace("?", "%s"), seq)
        finally:
            cur.close()

    def executescript(self, script):
        for stmt in [s.strip() for s in script.split(";") if s.strip()]:
            self._conn.execute(stmt)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        return False


def get_connection():
    cls = _PostgresConn if _is_postgres() else _SQLiteConn
    return cls()


SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id              TEXT PRIMARY KEY,
    institution     TEXT NOT NULL,
    connector_id    INTEGER,
    status          TEXT DEFAULT 'ACTIVE',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS accounts (
    id              TEXT PRIMARY KEY,
    item_id         TEXT NOT NULL REFERENCES items(id),
    name            TEXT NOT NULL,
    type            TEXT,
    balance         REAL DEFAULT 0,
    currency        TEXT DEFAULT 'BRL',
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS investments (
    id              TEXT PRIMARY KEY,
    item_id         TEXT NOT NULL REFERENCES items(id),
    name            TEXT NOT NULL,
    type            TEXT,
    quantity        REAL DEFAULT 0,
    price           REAL DEFAULT 0,
    value           REAL DEFAULT 0,
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL REFERENCES accounts(id),
    description     TEXT,
    amount          REAL NOT NULL,
    date            TEXT NOT NULL,
    category        TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date   DATE NOT NULL,
    institution     TEXT NOT NULL,
    account_type    TEXT NOT NULL,
    asset_name      TEXT NOT NULL,
    category        TEXT NOT NULL,
    amount          REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS manual_positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,
    institution     TEXT NOT NULL,
    category        TEXT NOT NULL,
    amount          REAL NOT NULL,
    updated_at      TEXT DEFAULT (datetime('now'))
);


CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snapshots_inst  ON snapshots(institution);

CREATE VIEW IF NOT EXISTS v_alocacao_instituicao AS
SELECT snapshot_date, institution, SUM(amount) AS total
FROM snapshots GROUP BY snapshot_date, institution;

CREATE VIEW IF NOT EXISTS v_alocacao_classe AS
SELECT snapshot_date, category, SUM(amount) AS total
FROM snapshots GROUP BY snapshot_date, category;
"""


SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS items (
    id              TEXT PRIMARY KEY,
    institution     TEXT NOT NULL,
    connector_id    INTEGER,
    status          TEXT DEFAULT 'ACTIVE',
    created_at      TEXT DEFAULT (now())::text,
    updated_at      TEXT DEFAULT (now())::text
);

CREATE TABLE IF NOT EXISTS accounts (
    id              TEXT PRIMARY KEY,
    item_id         TEXT NOT NULL REFERENCES items(id),
    name            TEXT NOT NULL,
    type            TEXT,
    balance         NUMERIC(20,4) DEFAULT 0,
    currency        TEXT DEFAULT 'BRL',
    updated_at      TEXT DEFAULT (now())::text
);

CREATE TABLE IF NOT EXISTS investments (
    id              TEXT PRIMARY KEY,
    item_id         TEXT NOT NULL REFERENCES items(id),
    name            TEXT NOT NULL,
    type            TEXT,
    quantity        NUMERIC(20,4) DEFAULT 0,
    price           NUMERIC(20,4) DEFAULT 0,
    value           NUMERIC(20,4) DEFAULT 0,
    updated_at      TEXT DEFAULT (now())::text
);

CREATE TABLE IF NOT EXISTS transactions (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL REFERENCES accounts(id),
    description     TEXT,
    amount          NUMERIC(20,4) NOT NULL,
    date            TEXT NOT NULL,
    category        TEXT,
    created_at      TEXT DEFAULT (now())::text
);

CREATE TABLE IF NOT EXISTS snapshots (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_date   TEXT NOT NULL,
    institution     TEXT NOT NULL,
    account_type    TEXT NOT NULL,
    asset_name      TEXT NOT NULL,
    category        TEXT NOT NULL,
    amount          NUMERIC(20,4) NOT NULL
);

CREATE TABLE IF NOT EXISTS manual_positions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,
    institution     TEXT NOT NULL,
    category        TEXT NOT NULL,
    amount          NUMERIC(20,4) NOT NULL,
    updated_at      TEXT DEFAULT (now())::text
);


CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snapshots_inst  ON snapshots(institution);

CREATE OR REPLACE VIEW v_alocacao_instituicao AS
SELECT snapshot_date, institution, SUM(amount) AS total
FROM snapshots GROUP BY snapshot_date, institution;

CREATE OR REPLACE VIEW v_alocacao_classe AS
SELECT snapshot_date, category, SUM(amount) AS total
FROM snapshots GROUP BY snapshot_date, category;
"""
