# tests/test_returns.py
import pandas as pd
import pytest

from dashboard.data import calculate_returns, prepare_snapshot_data


def _evolution(dates_amounts):
    return pd.DataFrame(dates_amounts, columns=["snapshot_date", "amount"])


def test_30d_and_ytd_happy_path():
    evo = _evolution(
        [
            ("2024-12-31", 100.0),
            ("2025-01-15", 110.0),
            ("2025-02-01", 115.0),  # ~32 dias antes do latest
            ("2025-03-05", 120.0),
        ]
    )
    r = calculate_returns(evo, 120.0)
    assert r["return_30d"] == pytest.approx(120 / 115 - 1)
    assert r["return_ytd"] == pytest.approx(120 / 100 - 1)


def test_insufficient_history_30d():
    evo = _evolution([("2025-03-01", 100.0), ("2025-03-05", 110.0)])
    r = calculate_returns(evo, 110.0)
    assert r["return_30d"] is None  # sem snapshot >= 30 dias atrás
    assert r["return_ytd"] is None


def test_empty_evolution():
    r = calculate_returns(pd.DataFrame(columns=["snapshot_date", "amount"]), 0.0)
    assert r == {"return_30d": None, "return_ytd": None}


def test_first_year_no_ytd():
    evo = _evolution([("2025-01-10", 100.0), ("2025-03-01", 110.0)])
    r = calculate_returns(evo, 110.0)
    assert r["return_ytd"] is None  # não há 2024


def test_prepare_snapshot_data_integrates_returns():
    rows = [
        {"snapshot_date": "2024-12-31", "institution": "XP", "amount": 100.0},
        {"snapshot_date": "2025-03-05", "institution": "XP", "amount": 110.0},
        {"snapshot_date": "2025-03-05", "institution": "Rico", "amount": 10.0},
    ]
    summary = prepare_snapshot_data(rows)
    assert summary.total == 120.0
    assert summary.returns["return_30d"] == pytest.approx(120 / 100 - 1)
    assert summary.returns["return_ytd"] == pytest.approx(120 / 100 - 1)
