"""Seed de dados sintéticos: 180 dias de histórico antes do 1º snapshot real."""

import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_connection

random.seed(42)

DIAS_SINTETICOS = 180
ATIVOS = [
    # (institution, account_type, asset_name, category, peso)
    ("Rico", "bank", "CDB Liquidez Diária", "CDI", 0.30),
    ("Rico", "bank", "Tesouro Selic 2029", "Tesouro Direto", 0.25),
    ("XP", "broker", "PETR4", "Ações", 0.10),
    ("XP", "broker", "VALE3", "Ações", 0.05),
    ("XP", "broker", "MXRF11", "FIIs", 0.08),
    ("NuInvest", "bank", "Caixinha", "banco", 0.07),
    ("NuInvest", "broker", "IVVB11", "ETF", 0.10),
    ("Banco X", "credit", "Cartão Platinum", "cartao", 0.05),
]


def main():
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT MIN(snapshot_date) AS first_snapshot FROM snapshots"
        ).fetchone()
        data_real = row["first_snapshot"] if row else None
        if data_real is None:
            raise RuntimeError("Não há snapshots reais para usar como referência.")
        if isinstance(data_real, str):
            data_real = date.fromisoformat(data_real[:10])

        conn.execute(
            "DELETE FROM snapshots WHERE snapshot_date < ?",
            (data_real.isoformat(),),
        )

        total = 100_000.0
        rows = []
        for i in range(DIAS_SINTETICOS, 0, -1):
            dia = data_real - timedelta(days=i)
            total *= 1 + random.gauss(0.0004, 0.003)
            for inst, account_type, nome, categoria, peso in ATIVOS:
                valor = round(total * peso * (1 + random.gauss(0, 0.02)), 4)
                rows.append(
                    (
                        dia.isoformat(),
                        inst,
                        account_type,
                        nome,
                        categoria,
                        valor,
                    )
                )

        conn.executemany(
            "INSERT INTO snapshots "
            "(snapshot_date, institution, account_type, asset_name, category, amount) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        print(f"Inseridos {len(rows)} snapshots sintéticos até {data_real}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
