import os
import sqlite3
from pathlib import Path

from app.core.config import DATABASE_URL

_DEFAULT_PATH = DATABASE_URL.replace("sqlite:///", "")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id              TEXT PRIMARY KEY,
    institution     TEXT NOT NULL,
    connector_id    INTEGER,
    status          TEXT DEFAULT 'ACTIVE',
    created_at      TEXT DEFAULT (datetime('now'))
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

CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snapshots_inst  ON snapshots(institution);

CREATE VIEW IF NOT EXISTS v_evolucao AS
SELECT snapshot_date, SUM(amount) AS patrimonio_total
FROM snapshots GROUP BY snapshot_date;

CREATE VIEW IF NOT EXISTS v_alocacao_instituicao AS
SELECT snapshot_date, institution, SUM(amount) AS total
FROM snapshots GROUP BY snapshot_date, institution;

CREATE VIEW IF NOT EXISTS v_alocacao_classe AS
SELECT snapshot_date, category, SUM(amount) AS total
FROM snapshots GROUP BY snapshot_date, category;
"""


def _db_path() -> str:
    return os.environ.get("OW_DB_PATH", _DEFAULT_PATH)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    Path(_db_path()).parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
    print(f"✅ Banco pronto em: {_db_path()}")

# SCHEMA permanece exatamente como está — não colado aqui só para economizar espaço.
# Apague os blocos duplicados de imports e o DB_PATH morto.
