"""Repositório para ativos e passivos cadastrados manualmente."""

from datetime import datetime
from typing import Any

from app.core.database import get_connection
from app.domain.models import ManualPosition


class ManualPositionRepository:
    """Gerencia a persistência de posições manuais (bens, imóveis, financiamentos)."""

    def __init__(self, conn: Any = None) -> None:
        self._conn = conn or get_connection()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS manual_positions (
                id          INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL,
                institution TEXT NOT NULL,
                category    TEXT NOT NULL,
                amount      REAL NOT NULL,
                updated_at  TEXT
            );
        """)

    def save(self, pos: ManualPosition) -> ManualPosition:
        """Insere ou atualiza uma posição manual."""
        updated_at = pos.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pos_type = pos.type.upper()

        if pos.id is None:
            sql = """
                INSERT INTO manual_positions
                    (name, type, institution, category, amount, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id, updated_at
            """
            cur = self._conn.execute(
                sql,
                (
                    pos.name,
                    pos_type,
                    pos.institution,
                    pos.category,
                    float(pos.amount),
                    updated_at,
                ),
            )
            row = cur.fetchone()
            self._conn.commit()
            return ManualPosition(
                id=int(row["id"]),
                name=pos.name,
                type=pos_type,
                institution=pos.institution,
                category=pos.category,
                amount=float(pos.amount),
                updated_at=str(row["updated_at"]),
            )

        sql = """
            UPDATE manual_positions
            SET name = ?, type = ?, institution = ?, category = ?, amount = ?, updated_at = ?
            WHERE id = ?
        """
        self._conn.execute(
            sql,
            (
                pos.name,
                pos_type,
                pos.institution,
                pos.category,
                float(pos.amount),
                updated_at,
                pos.id,
            ),
        )
        self._conn.commit()
        return ManualPosition(
            id=pos.id,
            name=pos.name,
            type=pos_type,
            institution=pos.institution,
            category=pos.category,
            amount=float(pos.amount),
            updated_at=updated_at,
        )

    def get_by_id(self, position_id: int) -> ManualPosition | None:
        """Busca uma posição manual pelo ID."""
        sql = """
            SELECT id, name, type, institution, category, amount, updated_at
            FROM manual_positions
            WHERE id = ?
        """
        cur = self._conn.execute(sql, (position_id,))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    def list_all(self) -> list[ManualPosition]:
        """Lista todas as posições manuais cadastradas."""
        sql = """
            SELECT id, name, type, institution, category, amount, updated_at
            FROM manual_positions
            ORDER BY id ASC
        """
        cur = self._conn.execute(sql)
        return [self._row_to_model(r) for r in cur.fetchall()]

    def list_by_type(self, pos_type: str) -> list[ManualPosition]:
        """Filtra posições por tipo ('ASSET' ou 'LIABILITY')."""
        sql = """
            SELECT id, name, type, institution, category, amount, updated_at
            FROM manual_positions
            WHERE type = ?
            ORDER BY id ASC
        """
        cur = self._conn.execute(sql, (pos_type.upper(),))
        return [self._row_to_model(r) for r in cur.fetchall()]

    def delete(self, position_id: int) -> bool:
        """Remove uma posição manual pelo ID."""
        cur = self._conn.execute("DELETE FROM manual_positions WHERE id = ?", (position_id,))
        self._conn.commit()
        return bool(cur.rowcount and cur.rowcount > 0)

    def get_totals(self) -> dict[str, float]:
        """Retorna a soma de ativos, passivos e o valor líquido manual."""
        positions = self.list_all()
        assets = sum(p.amount for p in positions if p.type == "ASSET")
        liabilities = sum(p.amount for p in positions if p.type == "LIABILITY")
        return {
            "assets": round(assets, 2),
            "liabilities": round(liabilities, 2),
            "net": round(assets - liabilities, 2),
        }

    def _row_to_model(self, row: Any) -> ManualPosition:
        return ManualPosition(
            id=int(row["id"]),
            name=str(row["name"]),
            type=str(row["type"]),
            institution=str(row["institution"]),
            category=str(row["category"]),
            amount=float(row["amount"]),
            updated_at=str(row["updated_at"]),
        )
