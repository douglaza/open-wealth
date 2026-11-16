import pandas as pd

import pytest

from dashboard.data import calculate_allocation, prepare_snapshot_data


def test_allocation_sums_by_category():
    latest = pd.DataFrame([
        {"category": "Renda Fixa", "amount": 90.0},
        {"category": "Ações", "amount": 20.0},
        {"category": "Renda Fixa", "amount": 10.0},
    ])
    alloc = calculate_allocation(latest)
    assert list(alloc["category"]) == ["Renda Fixa", "Ações"]
    assert list(alloc["amount"]) == pytest.approx([100.0, 20.0])
    assert alloc["pct"].sum() == pytest.approx(1.0)
    assert list(alloc["pct"]) == pytest.approx([100.0 / 120.0, 20.0 / 120.0])


def test_allocation_empty():
    alloc = calculate_allocation(pd.DataFrame(columns=["category", "amount"]))
    assert alloc.empty


def test_summary_exposes_allocation():
    rows = [
        {"snapshot_date": "2025-03-05", "institution": "XP",
         "category": "Renda Fixa", "amount": 110.0},
        {"snapshot_date": "2025-03-05", "institution": "Rico",
         "category": "Ações", "amount": 10.0},
    ]
    summary = prepare_snapshot_data(rows)
    assert list(summary.allocation["category"]) == ["Renda Fixa", "Ações"]
    assert list(summary.allocation["amount"]) == pytest.approx([110.0, 10.0])
    assert summary.allocation["pct"].sum() == pytest.approx(1.0)


def test_calculate_allocation_groups_categories_and_sorts_by_amount():
    latest_snapshots = pd.DataFrame(
        {
            "category": ["Ações", "Renda fixa", "Ações"],
            "amount": [40.0, 100.0, 30.0],
        }
    )

    allocation = calculate_allocation(latest_snapshots)

    assert allocation.to_dict("records") == [
        {"category": "Renda fixa", "amount": 100.0, "pct": pytest.approx(100.0 / 170.0)},
        {"category": "Ações", "amount": 70.0, "pct": pytest.approx(70.0 / 170.0)},
    ]



def test_calculate_allocation_labels_missing_categories():
    latest_snapshots = pd.DataFrame(
        {"category": [None, "Ações"], "amount": [25.0, 50.0]}
    )

    allocation = calculate_allocation(latest_snapshots)

    assert allocation.to_dict("records") == [
        {"category": "Ações", "amount": 50.0, "pct": pytest.approx(50.0 / 75.0)},
        {"category": "Não classificado", "amount": 25.0, "pct": pytest.approx(25.0 / 75.0)},
    ]



def test_calculate_allocation_empty_dataframe():
    empty = pd.DataFrame(columns=["category", "amount"])
    result = calculate_allocation(empty)
    assert list(result.columns) == ["category", "amount", "pct"]
    assert result.empty
