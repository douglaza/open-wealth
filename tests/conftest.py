import os
from datetime import date

import pytest

from app.core.database import get_connection, init_db
from app.domain.models import Position, Snapshot
from app.repositories.snapshot_repository import SnapshotRepository


@pytest.fixture(autouse=True)
def banco_limpo(tmp_path, monkeypatch):
    is_pg = os.getenv("TEST_DB", "sqlite").lower() == "postgres"

    if is_pg:
        test_database_url = os.getenv("TEST_DATABASE_URL")
        if not test_database_url:
            pytest.fail("Defina TEST_DATABASE_URL para executar testes no PostgreSQL.")
        monkeypatch.setenv("DATABASE_URL", test_database_url)
        init_db()
        with get_connection() as conn:
            conn.execute(
                """TRUNCATE TABLE transactions, accounts, investments,
                    snapshots, items RESTART IDENTITY CASCADE"""
            )
    else:
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("OW_DB_PATH", str(db_path))
        init_db()
        # SQLite: limpeza com DELETE
        with get_connection() as conn:
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM accounts")
            conn.execute("DELETE FROM investments")
            conn.execute("DELETE FROM snapshots")
            conn.execute("DELETE FROM items")


@pytest.fixture
def db_conn(banco_limpo):
    """Conexão de teste usando o dialeto selecionado pelo ambiente."""
    conn = get_connection()
    yield conn
    conn.close()


@pytest.fixture
def db_integrity_error():
    if os.getenv("TEST_DB", "sqlite").lower() == "postgres":
        import psycopg

        return psycopg.IntegrityError

    import sqlite3

    return sqlite3.IntegrityError


@pytest.fixture
def db_is_postgres():
    return os.getenv("TEST_DB", "sqlite").lower() == "postgres"


@pytest.fixture
def repo(db_conn):
    return SnapshotRepository(db_conn)


@pytest.fixture
def repo_com_dados(repo):
    repo.save_all(
        [
            Snapshot(
                snapshot_date=date(2025, 1, 1),
                positions=[
                    Position(
                        institution="XP",
                        account_type="broker",
                        asset_name="ITSA4",
                        category="Ações",
                        amount=1000.0,
                    ),
                ],
            ),
            Snapshot(
                snapshot_date=date(2025, 2, 1),
                positions=[
                    Position(
                        institution="XP",
                        account_type="broker",
                        asset_name="ITSA4",
                        category="Ações",
                        amount=1100.0,
                    ),
                ],
            ),
            Snapshot(
                snapshot_date=date(2025, 3, 1),
                positions=[
                    Position(
                        institution="XP",
                        account_type="broker",
                        asset_name="ITSA4",
                        category="Ações",
                        amount=1200.0,
                    ),
                ],
            ),
        ]
    )
    return repo
