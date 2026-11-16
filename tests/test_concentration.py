# tests/test_concentration.py
import pandas as pd
import pytest

from dashboard.data import calculate_concentration, prepare_snapshot_data


def _institutions(institution, amount):
    return pd.DataFrame({"institution": institution, "amount": amount})


def test_concentration_two_institutions():
    inst = _institutions(["XP", "Rico"], [90.0, 30.0])
    pct, hhi = calculate_concentration(inst, 120.0)
    assert list(pct["pct"]) == pytest.approx([0.75, 0.25])
    assert hhi == pytest.approx(0.75**2 + 0.25**2)


def test_concentration_single_institution():
    inst = _institutions(["XP"], [100.0])
    pct, hhi = calculate_concentration(inst, 100.0)
    assert list(pct["pct"]) == pytest.approx([1.0])
    assert hhi == pytest.approx(1.0)


def test_concentration_empty():
    inst = pd.DataFrame(columns=["institution", "amount"])
    pct, hhi = calculate_concentration(inst, 0.0)
    assert pct.empty
    assert hhi is None


def test_summary_exposes_concentration():
    rows = [
        {"snapshot_date": "2025-03-05", "institution": "XP", "amount": 110.0},
        {"snapshot_date": "2025-03-05", "institution": "Rico", "amount": 10.0},
    ]
    summary = prepare_snapshot_data(rows)
    assert summary.total == 120.0
    assert list(summary.institutions_pct["institution"]) == ["XP", "Rico"]
    assert list(summary.institutions_pct["pct"]) == pytest.approx([110 / 120, 10 / 120])
    assert summary.hhi == pytest.approx((110 / 120) ** 2 + (10 / 120) ** 2)
