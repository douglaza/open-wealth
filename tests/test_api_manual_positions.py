from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes import get_manual_repo
from app.core.metrics import (
    MANUAL_ASSETS_BRL,
    MANUAL_LIABILITIES_BRL,
    NET_WORTH_TOTAL_BRL,
    refresh_financial_metrics,
)
from app.repositories.manual_position_repository import (
    ManualPositionRepository,
)

client = TestClient(app)


def test_metrics_updated_on_create_and_delete(db_conn) -> None:
    payload = {
        "name": "Apartamento Teste",
        "type": "ASSET",
        "institution": "Imóvel",
        "category": "REAL_ESTATE",
        "amount": 500000.0,
    }
    res = client.post("/api/v1/manual-positions", json=payload)
    pos_id = res.json()["id"]

    assert MANUAL_ASSETS_BRL._value.get() >= 500000.0

    client.delete(f"/api/v1/manual-positions/{pos_id}")
    # Após deletar, o valor de ativos manuais diminui
    assert MANUAL_ASSETS_BRL._value.get() < 500000.0


def test_refresh_financial_metrics_fallbacks_and_exceptions() -> None:
    mock_m_repo = MagicMock()
    mock_m_repo.get_totals.return_value = {
        "assets": 50000.0,
        "liabilities": 20000.0,
    }

    # 1. Com ultimos_totais_por_data
    mock_s_repo_totals = MagicMock()
    mock_s_repo_totals.ultimos_totais_por_data.return_value = [{"total": 80000.0}]
    refresh_financial_metrics(snapshot_repo=mock_s_repo_totals, manual_repo=mock_m_repo)
    assert MANUAL_ASSETS_BRL._value.get() == 50000.0
    assert MANUAL_LIABILITIES_BRL._value.get() == 20000.0
    assert NET_WORTH_TOTAL_BRL._value.get() == 110000.0  # 80k + 50k - 20k

    # 2. Com fallback para get_latest
    mock_s_repo = MagicMock()
    mock_s_repo.ultimos_totais_por_data.return_value = []
    mock_snap = MagicMock()
    mock_snap.total = 100000.0
    mock_s_repo.get_latest.return_value = mock_snap

    refresh_financial_metrics(snapshot_repo=mock_s_repo, manual_repo=mock_m_repo)
    assert NET_WORTH_TOTAL_BRL._value.get() == 130000.0  # 100k + 50k - 20k

    # 3. Com fallback get_latest retornando None
    mock_s_repo_none = MagicMock()
    mock_s_repo_none.ultimos_totais_por_data.return_value = []
    mock_s_repo_none.get_latest.return_value = None
    refresh_financial_metrics(snapshot_repo=mock_s_repo_none, manual_repo=mock_m_repo)
    assert NET_WORTH_TOTAL_BRL._value.get() == 30000.0  # 0k + 50k - 20k

    # 4. Com exceção simulada no snapshot repo
    mock_s_repo_err = MagicMock()
    mock_s_repo_err.ultimos_totais_por_data.side_effect = RuntimeError("db error")
    refresh_financial_metrics(snapshot_repo=mock_s_repo_err, manual_repo=mock_m_repo)
    assert NET_WORTH_TOTAL_BRL._value.get() == 30000.0  # 0k + 50k - 20k


def test_get_manual_repo_instantiation() -> None:
    repo = get_manual_repo()
    assert isinstance(repo, ManualPositionRepository)


def test_create_and_get_manual_position(db_conn) -> None:
    payload = {
        "name": "Apartamento Moema",
        "type": "ASSET",
        "institution": "Imóvel Próprio",
        "category": "REAL_ESTATE",
        "amount": 750000.0,
    }
    res = client.post("/api/v1/manual-positions", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Apartamento Moema"
    assert data["amount"] == 750000.0
    pos_id = data["id"]

    res_get = client.get(f"/api/v1/manual-positions/{pos_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == pos_id


def test_get_manual_position_not_found(db_conn) -> None:
    res = client.get("/api/v1/manual-positions/99999")
    assert res.status_code == 404
    assert res.json()["detail"] == "Posição manual não encontrada"


def test_list_and_filter_manual_positions(db_conn) -> None:
    p1 = {
        "name": "Casa de Campo",
        "type": "ASSET",
        "institution": "Imóvel",
        "category": "REAL_ESTATE",
        "amount": 300000.0,
    }
    p2 = {
        "name": "Financiamento Habitacional Caixa",
        "type": "LIABILITY",
        "institution": "Caixa",
        "category": "MORTGAGE",
        "amount": 200000.0,
    }
    client.post("/api/v1/manual-positions", json=p1)
    client.post("/api/v1/manual-positions", json=p2)

    res_all = client.get("/api/v1/manual-positions")
    assert res_all.status_code == 200
    assert len(res_all.json()) >= 2

    res_assets = client.get("/api/v1/manual-positions?type=ASSET")
    assert res_assets.status_code == 200
    assert all(item["type"] == "ASSET" for item in res_assets.json())

    res_liab = client.get("/api/v1/manual-positions?type=LIABILITY")
    assert res_liab.status_code == 200
    assert all(item["type"] == "LIABILITY" for item in res_liab.json())


def test_manual_totals(db_conn) -> None:
    res = client.get("/api/v1/manual-positions/totals")
    assert res.status_code == 200
    data = res.json()
    assert "assets" in data
    assert "liabilities" in data
    assert "net" in data


def test_delete_manual_position(db_conn) -> None:
    payload = {
        "name": "Carro Usado",
        "type": "ASSET",
        "institution": "Garagem",
        "category": "VEHICLE",
        "amount": 45000.0,
    }
    res = client.post("/api/v1/manual-positions", json=payload)
    pos_id = res.json()["id"]

    res_del = client.delete(f"/api/v1/manual-positions/{pos_id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "deleted"

    res_del_404 = client.delete(f"/api/v1/manual-positions/{pos_id}")
    assert res_del_404.status_code == 404


def test_create_invalid_manual_position(db_conn) -> None:
    payload = {
        "name": "Inválido",
        "type": "OTHER",
        "institution": "Banco",
        "category": "TEST",
        "amount": 100.0,
    }
    res = client.post("/api/v1/manual-positions", json=payload)
    assert res.status_code == 422
