from datetime import date
from unittest.mock import MagicMock

from app.services.consolidacao import sync_all, get_totals


def _fake_client():
    c = MagicMock()
    c.get_items.return_value = [
        {"id": "i1", "connector": {"name": "Banco X"}},
    ]
    c.get_accounts.return_value = [
        {"name": "CC", "type": "BANK", "balance": 1000.0},
    ]
    c.get_investments.return_value = [
        {"name": "Fundo A", "type": "CDB", "value": 500.0},
    ]
    return c


def test_sync_all_builds_snapshot():
    snap = sync_all(_fake_client())
    assert snap.snapshot_date == date.today()
    assert len(snap.positions) == 2
    assert snap.total == 1500.0


def test_get_totals_aggregates_by_institution():
    snap = sync_all(_fake_client())
    totals = get_totals(snap)
    assert totals["total"] == 1500.0
    assert totals["institutions"] == {"Banco X": 1500.0}
