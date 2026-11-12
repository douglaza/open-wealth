# tests/test_rentabilidade.py
from app.core.database import get_connection


def _seed(rows):
    conn = get_connection()
    conn.executemany(
        "INSERT INTO snapshots (snapshot_date, institution, account_type, asset_name, category, amount) "
        "VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()


def test_rentabilidade_total():
    _seed([
        ("2025-01-01", "Banco A", "bank", "Conta", "banco", 10000),
        ("2025-02-01", "Banco A", "bank", "Conta", "banco", 10500),
    ])
    from app.services.rentabilidade import rentabilidade_total
    result = rentabilidade_total()
    assert result["variacao_pct"] == 5.0
    assert result["variacao_abs"] == 500.0


def test_rentabilidade_total_dados_insuficientes():
    _seed([("2025-01-01", "Banco A", "bank", "Conta", "banco", 10000)])
    from app.services.rentabilidade import rentabilidade_total
    assert "msg" in rentabilidade_total()


def test_rentabilidade_total_zero_anterior_pct_none():
    _seed([
        ("2025-01-01", "Banco A", "bank", "Conta", "banco", 0),
        ("2025-02-01", "Banco A", "bank", "Conta", "banco", 500),
    ])
    from app.services.rentabilidade import rentabilidade_total
    assert rentabilidade_total()["variacao_pct"] is None


def test_rentabilidade_por_instituicao():
    _seed([
        ("2025-01-01", "Banco A", "bank", "Conta", "banco", 1000),
        ("2025-01-01", "Banco B", "bank", "Conta", "banco", 2000),
        ("2025-02-01", "Banco A", "bank", "Conta", "banco", 1100),
        # Banco B não tem snapshot atual; Banco C só existe no atual
        ("2025-02-01", "Banco C", "bank", "Conta", "banco", 300),
    ])
    from app.services.rentabilidade import rentabilidade_por_instituicao
    result = {r["institution"]: r for r in rentabilidade_por_instituicao()}
    assert result["Banco A"]["variacao_pct"] == 10.0
    assert result["Banco B"]["valor_atual"] == 0        # sum ausente → 0
    assert result["Banco C"]["valor_anterior"] == 0
    assert result["Banco C"]["variacao_pct"] is None    # dividiria por 0
