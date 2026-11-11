from datetime import date

from app.core.database import get_connection
from app.models.snapshot import Position, Snapshot


def save(snapshot: Snapshot):
    """Upsert do dia: apaga posições existentes e reinsere."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM snapshots WHERE snapshot_date = ?",
            (snapshot.snapshot_date.isoformat(),),
        )
        conn.executemany(
            """INSERT INTO snapshots
               (snapshot_date, institution, account_type,
                asset_name, category, amount)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (
                    snapshot.snapshot_date.isoformat(),
                    p.institution, p.account_type,
                    p.asset_name, p.category, p.amount,
                )
                for p in snapshot.positions
            ],
        )


def get_latest() -> Snapshot | None:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM snapshots WHERE snapshot_date = "
            "(SELECT MAX(snapshot_date) FROM snapshots)"
        ).fetchall()
    if not rows:
        return None
    return _rows_to_snapshots(rows)[0]


def get_between(start: date, end: date) -> list[Snapshot]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM snapshots "
            "WHERE snapshot_date BETWEEN ? AND ? "
            "ORDER BY snapshot_date",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    return _rows_to_snapshots(rows)


def _rows_to_snapshots(rows) -> list[Snapshot]:
    by_date: dict[date, list[Position]] = {}
    for r in rows:
        d = date.fromisoformat(r["snapshot_date"])
        by_date.setdefault(d, []).append(Position(
            institution=r["institution"],
            account_type=r["account_type"],
            asset_name=r["asset_name"],
            category=r["category"],
            amount=r["amount"],
        ))
    return [Snapshot(snapshot_date=d, positions=ps) for d, ps in by_date.items()]
