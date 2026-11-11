# tests/test_rentabilidade.py
def test_rentabilidade_total():
    from app.core.database import get_connection
    conn = get_connection()
    conn.executemany(
        "INSERT INTO snapshots (snapshot_date, institution, account_type, asset_name, category, amount) VALUES (?,?,?,?,?,?)",
        [
            ("2025-01-01", "Banco A", "bank", "Conta", "banco", 10000),
            ("2025-02-01", "Banco A", "bank", "Conta", "banco", 10500),
        ],
    )
    conn.commit()
    from app.services.rentabilidade import rentabilidade_total
    result = rentabilidade_total()
    assert result["variacao_pct"] == 5.0
