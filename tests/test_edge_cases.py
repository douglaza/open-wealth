# tests/test_edge_cases.py
import pytest

from dashboard.data import EXCLUDED_CATEGORIES, prepare_snapshot_data


def _rows(*entries):
    return [
        {"snapshot_date": d, "institution": "XP", "category": "Ações", "amount": a}
        for d, a in entries
    ]


def test_ytd_is_none_when_history_starts_midyear():
    rows = _rows(
        ("2025-03-01", 100.0),
        ("2025-06-01", 110.0),
    )
    summary = prepare_snapshot_data(rows)
    assert summary.returns["return_ytd"] is None


def test_ytd_exists_with_previous_year_snapshot():
    rows = _rows(
        ("2024-12-15", 100.0),
        ("2025-01-10", 105.0),
        ("2025-06-01", 120.0),
    )
    summary = prepare_snapshot_data(rows)
    # baseline = último snapshot anterior a 2025-01-01 (100) → 120/100 - 1
    assert summary.returns["return_ytd"] == pytest.approx(0.20)


def test_snapshot_data_includes_all_categories_by_default():
    rows = [
        *_rows(("2025-06-01", 100.0)),
        {
            "snapshot_date": "2025-06-01",
            "institution": "Nubank",
            "category": "banco",
            "amount": 5000.0,
        },
        {
            "snapshot_date": "2025-06-01",
            "institution": "Nubank",
            "category": "cartao",
            "amount": 300.0,
        },
    ]
    summary = prepare_snapshot_data(rows)
    assert summary.total == pytest.approx(5400.0)
    assert list(summary.allocation["category"]) == ["banco", "cartao", "Ações"]
    assert set(summary.institutions["institution"]) == {"XP", "Nubank"}


def test_category_exclusion_is_explicit_and_case_insensitive():
    rows = [
        *_rows(("2025-06-01", 100.0)),
        {
            "snapshot_date": "2025-06-01",
            "institution": "Nubank",
            "category": "BANCO",
            "amount": 5000.0,
        },
        {
            "snapshot_date": "2025-06-01",
            "institution": "Nubank",
            "category": "cartao",
            "amount": 300.0,
        },
        {"snapshot_date": "2025-06-01", "institution": "Outra", "category": None, "amount": 200.0},
    ]
    summary = prepare_snapshot_data(rows, exclude_categories=EXCLUDED_CATEGORIES)
    assert summary.total == pytest.approx(300.0)
    assert list(summary.allocation["category"]) == ["Não classificado", "Ações"]
    assert list(summary.institutions["institution"]) == ["Outra", "XP"]


def test_category_exclusion_applies_to_history_and_returns():
    rows = [
        *_rows(("2024-12-15", 100.0), ("2025-06-01", 120.0)),
        {
            "snapshot_date": "2024-12-15",
            "institution": "Nubank",
            "category": "banco",
            "amount": 900.0,
        },
        {
            "snapshot_date": "2025-06-01",
            "institution": "Nubank",
            "category": "banco",
            "amount": 1200.0,
        },
    ]
    summary = prepare_snapshot_data(rows, exclude_categories=EXCLUDED_CATEGORIES)
    assert summary.returns["return_ytd"] == pytest.approx(0.20)
    assert list(summary.evolution["amount"]) == pytest.approx([100.0, 120.0])
