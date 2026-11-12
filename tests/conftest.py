# tests/conftest.py
import pytest
from app.core.database import get_connection


@pytest.fixture(autouse=True)
def banco_limpo():
    conn = get_connection()
    conn.execute("DELETE FROM snapshots")
    conn.execute("DELETE FROM accounts")
    conn.execute("DELETE FROM investments")
    conn.commit()
    yield
    conn.execute("DELETE FROM snapshots")
    conn.execute("DELETE FROM accounts")
    conn.execute("DELETE FROM investments")
    conn.commit()
