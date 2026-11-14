from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd


def prepare_snapshot_data(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[pd.DataFrame, float, pd.DataFrame, pd.DataFrame]:
    snapshots = pd.DataFrame([dict(row) for row in rows])
    if snapshots.empty:
        return (
            snapshots,
            0.0,
            pd.DataFrame(columns=["snapshot_date", "amount"]),
            pd.DataFrame(columns=["institution", "amount"]),
        )

    snapshots["snapshot_date"] = pd.to_datetime(
        snapshots["snapshot_date"], errors="raise"
    )
    snapshots["amount"] = pd.to_numeric(
        snapshots["amount"], errors="raise"
    ).astype("float64")

    latest_date = snapshots["snapshot_date"].max()
    latest_snapshots = snapshots[snapshots["snapshot_date"] == latest_date]
    latest_total = float(latest_snapshots["amount"].sum())
    evolution = (
        snapshots.groupby("snapshot_date", as_index=False)["amount"]
        .sum()
        .sort_values("snapshot_date")
    )

    by_type = (
    latest_snapshots.groupby("account_type", as_index=False)["amount"]
    .sum()
    .sort_values("amount", ascending=False)
)

    return snapshots, latest_total, evolution, by_type
