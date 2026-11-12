"""Persistência de snapshots e posições. Fala negócio, não SQL espalhado."""
from app.core.database import get_connection

from datetime import date
# from app.models.snapshot import Position, Snapshot
from app.domain.models import Position, Snapshot


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

    def save(self, snapshot: Snapshot):
        """Upsert do dia: apaga posições existentes e reinsere."""
        self._conn.execute(
            "DELETE FROM snapshots WHERE snapshot_date = ?",
            (snapshot.snapshot_date.isoformat(),),
        )
        self._conn.executemany(
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
        self._conn.commit()

    def get_latest(self) -> Snapshot | None:
        rows = self._conn.execute(
            "SELECT * FROM snapshots WHERE snapshot_date = "
            "(SELECT MAX(snapshot_date) FROM snapshots)"
        ).fetchall()
        if not rows:
            return None
        return self._rows_to_snapshots(rows)[0]

    def get_between(self, start: date, end: date) -> list[Snapshot]:
        rows = self._conn.execute(
            "SELECT * FROM snapshots "
            "WHERE snapshot_date BETWEEN ? AND ? "
            "ORDER BY snapshot_date",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return self._rows_to_snapshots(rows)

    def _rows_to_snapshots(self, rows) -> list[Snapshot]:
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

    def ultimos_totais_por_data(self, n: int = 2) -> list[dict]:
        rows = self._conn.execute(
            """SELECT snapshot_date, SUM(amount) AS total
               FROM snapshots
               WHERE snapshot_date IN (
                   SELECT DISTINCT snapshot_date FROM snapshots
                   ORDER BY snapshot_date DESC LIMIT ?
               )
               GROUP BY snapshot_date
               ORDER BY snapshot_date""",
            (n,),
        ).fetchall()
        return [dict(r) for r in rows]

    def totais_por_instituicao_ultimas_datas(self) -> list[dict]:
        rows = self._conn.execute("""
            WITH datas AS (
                SELECT DISTINCT snapshot_date FROM snapshots
                ORDER BY snapshot_date DESC LIMIT 2
            )
            SELECT
                (SELECT MAX(snapshot_date) FROM datas) AS data_atual,
                (SELECT MIN(snapshot_date) FROM datas) AS data_anterior,
                i.institution,
                COALESCE(v1.total, 0)               AS valor_anterior,
                COALESCE(v2.total, 0)               AS valor_atual
            FROM (SELECT institution FROM snapshots GROUP BY institution) i
            LEFT JOIN (SELECT institution, SUM(amount) total
                       FROM snapshots
                       WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM datas)
                       GROUP BY institution) v2 ON i.institution = v2.institution
            LEFT JOIN (SELECT institution, SUM(amount) total
                       FROM snapshots
                       WHERE snapshot_date = (SELECT MIN(snapshot_date) FROM datas)
                       GROUP BY institution) v1 ON i.institution = v1.institution
        """).fetchall()
        return [dict(r) for r in rows]
