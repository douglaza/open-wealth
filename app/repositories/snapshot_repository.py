"""Persistência de snapshots e posições. Fala negócio, não SQL espalhado."""
from datetime import date

from app.core.database import get_connection
from app.domain.models import Position, Snapshot


class SnapshotRepository:
    """Único lugar que sabe que snapshots/accounts/investments vivem em SQLite."""

    def __init__(self, conn=None):
        self._conn = conn or get_connection()
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Snapshots (posições agregadas)
    # ------------------------------------------------------------------

    def save(self, snapshot: Snapshot) -> None:
        """Upsert do dia: apaga posições existentes e reinsere."""
        self.save_all([snapshot])

    def save_all(self, snapshots: list[Snapshot]) -> None:
        """Upsert por data: apaga posições existentes e reinsere."""
        try:
            for s in snapshots:
                self._conn.execute(
                    "DELETE FROM snapshots WHERE snapshot_date = ?",
                    (s.snapshot_date.isoformat(),),
                )
            self._conn.executemany(
                """INSERT INTO snapshots
                   (snapshot_date, institution, account_type, asset_name, category, amount)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        s.snapshot_date.isoformat(),
                        p.institution, p.account_type,
                        p.asset_name, p.category, p.amount,
                    )
                    for s in snapshots for p in s.positions
                ],
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def add_all(self, snapshots) -> None:
        """Insert puro, sem apagar nada (útil em testes/seeds)."""
        self._conn.executemany(
            """INSERT INTO snapshots
               (snapshot_date, institution, account_type, asset_name, category, amount)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (s.snapshot_date.isoformat(), p.institution, p.account_type,
                 p.asset_name, p.category, p.amount)
                for s in snapshots for p in s.positions
            ],
        )
        self._conn.commit()

    def snapshot_exists(self, snapshot_date: str, institution: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM snapshots WHERE snapshot_date = ? AND institution = ?",
            (snapshot_date, institution),
        ).fetchone() is not None

    def save_snapshot_row(self, snapshot_date, institution, account_type,
                          asset_name, category, amount) -> None:
        self._conn.execute(
            "INSERT INTO snapshots (snapshot_date, institution, account_type, asset_name, category, amount) "
            "VALUES (?,?,?,?,?,?)",
            (snapshot_date, institution, account_type, asset_name, category, amount),
        )

    def get_latest(self) -> Snapshot | None:
        rows = self._conn.execute(
            "SELECT * FROM snapshots WHERE snapshot_date = "
            "(SELECT MAX(snapshot_date) FROM snapshots)"
        ).fetchall()
        if not rows:
            return None
        return self._rows_to_snapshots(rows)[0]

    def get_all(self) -> list[Snapshot]:
        rows = self._conn.execute(
            "SELECT * FROM snapshots ORDER BY snapshot_date"
        ).fetchall()
        return self._rows_to_snapshots(rows)

    def get_between(self, inicio: str | date | None, fim: str | date | None) -> list[Snapshot]:
        query = "SELECT * FROM snapshots WHERE 1=1"
        params: list = []
        if inicio:
            query += " AND snapshot_date >= ?"
            params.append(inicio if isinstance(inicio, str) else inicio.isoformat())
        if fim:
            query += " AND snapshot_date <= ?"
            params.append(fim if isinstance(fim, str) else fim.isoformat())
        query += " ORDER BY snapshot_date"
        rows = self._conn.execute(query, params).fetchall()
        return self._rows_to_snapshots(rows)


    # def get_between(self, inicio: str | None, fim: str | None) -> list[Snapshot]:
    #     query = "SELECT * FROM snapshots WHERE 1=1"
    #     params: list = []
    #     if inicio:
    #         query += " AND snapshot_date >= ?"
    #         params.append(inicio)
    #     if fim:
    #         query += " AND snapshot_date <= ?"
    #         params.append(fim)
    #     query += " ORDER BY snapshot_date"
    #     rows = self._conn.execute(query, params).fetchall()
    #     return self._rows_to_snapshots(rows)

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

    # ------------------------------------------------------------------
    # Items / accounts / investments (dados crus do conector)
    # ------------------------------------------------------------------

    def upsert_snapshot(self, items: list[dict], snapshot_date: date) -> None:
        try:
            for item in items:
                self.upsert_item(item, snapshot_date)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def upsert_item(self, item: dict, snapshot_date: str | date) -> None:
        if isinstance(snapshot_date, date):
            snapshot_date = snapshot_date.isoformat()
        self._conn.execute(
            """INSERT INTO items (id, institution, updated_at) VALUES (?,?,?)
            ON CONFLICT(id) DO UPDATE SET institution=excluded.institution, updated_at=excluded.updated_at""",
            (item["id"], item.get("connector", {}).get("name", ""), snapshot_date),
        )

    def upsert_account(self, acc: dict, item_id: str, snapshot_date: str | date) -> None:
        if isinstance(snapshot_date, date):
            snapshot_date = snapshot_date.isoformat()
        self._conn.execute(
            """INSERT INTO accounts (id, item_id, name, type, balance, currency, updated_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 balance=excluded.balance, updated_at=excluded.updated_at""",
            (acc["id"], item_id, acc.get("name", ""), acc.get("type"),
             acc.get("balance", 0), acc.get("currency", "BRL"), snapshot_date),
        )

    def upsert_investment(self, inv: dict, item_id: str, snapshot_date: str | date) -> None:
        if isinstance(snapshot_date, date):
            snapshot_date = snapshot_date.isoformat()
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

    def commit(self) -> None:
        self._conn.commit()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                institution TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_date TEXT NOT NULL,
                institution TEXT NOT NULL,
                account_type TEXT NOT NULL,
                asset_name TEXT NOT NULL,
                category TEXT,
                amount REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                name TEXT,
                type TEXT,
                balance REAL,
                currency TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS investments (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                name TEXT,
                type TEXT,
                quantity REAL,
                price REAL,
                value REAL,
                updated_at TEXT
            );
        """)
        self._conn.commit()
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        """Migrações incrementais e idempotentes para bancos existentes."""
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(items)")}
        if "updated_at" not in cols:
            self._conn.execute("ALTER TABLE items ADD COLUMN updated_at TEXT")
        self._conn.commit()