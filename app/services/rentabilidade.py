from app.core.database import get_connection


def rentabilidade_por_instituicao():
    """Retorno entre os dois snapshots mais recentes, por instituição."""
    conn = get_connection()
    rows = conn.execute("""
        WITH datas AS (
            SELECT DISTINCT snapshot_date FROM snapshots
            ORDER BY snapshot_date DESC LIMIT 2
        )
        SELECT
            d1.snapshot_date                    AS data_atual,
            d2.snapshot_date                    AS data_anterior,
            i.institution,
            COALESCE(v1.total, 0)               AS valor_anterior,
            COALESCE(v2.total, 0)               AS valor_atual,
            COALESCE(v2.total, 0) - COALESCE(v1.total, 0) AS variacao_abs,
            CASE
                WHEN COALESCE(v1.total, 0) > 0 THEN
                    ROUND((COALESCE(v2.total, 0) - COALESCE(v1.total, 0))
                          / v1.total * 100, 2)
                ELSE NULL
            END AS variacao_pct
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


def rentabilidade_total():
    """Patrimônio total nos dois últimos snapshots."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT snapshot_date, SUM(amount) AS total
        FROM snapshots
        WHERE snapshot_date IN (
            SELECT DISTINCT snapshot_date FROM snapshots
            ORDER BY snapshot_date DESC LIMIT 2
        )
        GROUP BY snapshot_date
        ORDER BY snapshot_date
    """).fetchall()

    if len(rows) < 2:
        return {"msg": "Dados insuficientes — precisa de 2 snapshots"}

    anterior, atual = rows[0], rows[1]
    var_abs = atual["total"] - anterior["total"]
    var_pct = round(var_abs / anterior["total"] * 100, 2) if anterior["total"] else None
    return {
        "data_anterior": anterior["snapshot_date"],
        "data_atual": atual["snapshot_date"],
        "valor_anterior": anterior["total"],
        "valor_atual": atual["total"],
        "variacao_abs": round(var_abs, 2),
        "variacao_pct": var_pct,
    }
