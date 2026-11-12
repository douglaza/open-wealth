"""Persistência de snapshots e posições. Fala negócio, não SQL espalhado."""
from app.core.database import get_connection

from datetime import date
from app.models.snapshot import Position, Snapshot

class SnapshotRepository:
    """Único lugar que sabe que snapshots/accounts/investments vivem em SQLite."""

    def __init__(self, conn=None):
        self._conn = conn or get_connection()

    def snapshot_exists(self, snapshot_date: str, institution: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM snapshots WHERE snapshot_date = ? AND institution = ?",
            (snapshot_date, institution),
        ).fetchone() is not None

    def save_snapshot_row(self, snapshot_date, institution, account_type, asset_name, category, amount):
        self._conn.execute(
            "INSERT INTO snapshots (snapshot_date, institution, account_type, asset_name, category, amount) "
            "VALUES (?,?,?,?,?,?)",
            (snapshot_date, institution, account_type, asset_name, category, amount),
        )

    def upsert_account(self, acc: dict, item_id: str, snapshot_date: str):
        self._conn.execute(
            """INSERT INTO accounts (id, item_id, name, type, balance, currency, updated_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 balance=excluded.balance, updated_at=excluded.updated_at""",
            (acc["id"], item_id, acc.get("name", ""), acc.get("type"),
             acc.get("balance", 0), acc.get("currency", "BRL"), snapshot_date),
        )

    def upsert_investment(self, inv: dict, item_id: str, snapshot_date: str):
        qty = inv.get("quantity") or 0
        price = inv.get("price") or 0
        self._conn.execute(
            """INSERT INTO investments (id, item_id, name, type, quantity, price, value, updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 quantity=excluded.quantity, price=excluded.price,
                 value=excluded.value, updated_at=excluded.updated_at""",
            (inv["id"], item_id, inv.get("name", ""), inv.get("type"),
             qty, price, qty * price, snapshot_date),
        )

    def commit(self):
        self._conn.commit()


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
