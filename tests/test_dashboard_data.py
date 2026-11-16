from datetime import date
from decimal import Decimal

from dashboard.data import prepare_snapshot_data


def test_prepare_snapshot_data_uses_typed_values_and_latest_snapshot():
    rows = [
        {
            "snapshot_date": date(2025, 1, 1),
            "institution": "XP",
            "amount": Decimal("100.00"),
        },
        {
            "snapshot_date": date(2025, 1, 1),
            "institution": "Banco X",
            "amount": Decimal("200.00"),
        },
        {
            "snapshot_date": date(2025, 2, 1),
            "institution": "XP",
            "amount": Decimal("400.00"),
        },
        {
            "snapshot_date": date(2025, 2, 1),
            "institution": "Banco X",
            "amount": Decimal("300.00"),
        },
    ]

    # snapshots, total, evolution, institutions = prepare_snapshot_data(rows)
    summary = prepare_snapshot_data(rows)

    assert summary.snapshots["snapshot_date"].dtype.kind == "M"
    assert summary.snapshots["amount"].dtype.kind == "f"
    assert summary.total == 700.0
    assert summary.evolution["amount"].tolist() == [300.0, 700.0]
    assert summary.institutions.to_dict("records") == [
        {"institution": "XP", "amount": 400.0},
        {"institution": "Banco X", "amount": 300.0},
    ]
