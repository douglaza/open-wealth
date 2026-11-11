from app.core.database import get_connection
from app.models.snapshot import Snapshot


def save(snapshot: Snapshot):
    with get_connection() as conn:
        for p in snapshot.positions:
            conn.execute(
                """INSERT INTO snapshots
                   (snapshot_date, institution, account_type,
                    asset_name, category, amount)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    snapshot.snapshot_date.isoformat(),
                    p.institution,
                    p.account_type,
                    p.asset_name,
                    p.category,
                    p.amount,
                ),
            )


def get_all() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM snapshots ORDER BY snapshot_date")
        return [dict(r) for r in rows.fetchall()]
