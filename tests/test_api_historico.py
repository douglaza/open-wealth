import pytest
from fastapi.testclient import TestClient


from datetime import date
from app.domain.models import Position, Snapshot
from app.repositories.snapshot_repository import SnapshotRepository


# @pytest.fixture
# def seed_snapshots():
#     def _seed(datas: list[str], valores: list[float]):
#         repo = SnapshotRepository()
#         repo.add_all(
#             Snapshot(snapshot_date=date.fromisoformat(d), total=v)
#             for d, v in zip(datas, valores)
#         )
#     return _seed


@pytest.fixture
def seed_snapshots():
    def _seed(datas: list[str], valores: list[float]):
        repo = SnapshotRepository()
        repo.add_all(
            Snapshot(
                snapshot_date=date.fromisoformat(d),
                positions=[
                    Position(institution="X", account_type="Y",
                             asset_name="Z", category="C", amount=v)
                ],
            )
            for d, v in zip(datas, valores)
        )
    return _seed


# @pytest.fixture
# def client(monkeypatch):
#     # segue o padrão dos seus outros testes de API (sqlite temporário, deps sobrescritas)
#     from app.api.main import app
#     yield TestClient(app)

@pytest.fixture
def client(monkeypatch, tmp_path):
    from app.api import main
    db = tmp_path / "test.db"

    def _fake_conn():
        import sqlite3
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr("app.core.database.get_connection", _fake_conn)
    # se as rotas usam Depends(get_repo) ou similar, sobrescreva a dependency também
    yield TestClient(main.app)



def test_evolucao_retorna_200_com_serie(client):
    resp = client.get("/api/v1/historico/evolucao")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"datas", "valores"}
    assert isinstance(body["datas"], list)
    assert isinstance(body["valores"], list)
    assert len(body["datas"]) == len(body["valores"])


def test_acumulado_retorna_200(client):
    resp = client.get("/api/v1/historico/acumulado")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"datas", "valores"}


def test_evolucao_com_snapshots_retorna_pontos_corretos(client, seed_snapshots):
    seed_snapshots(["2026-11-01", "2026-11-08"], [180_000.0, 183_000.0])
    resp = client.get("/api/v1/historico/evolucao")
    assert resp.status_code == 200
    assert resp.json()["valores"] == pytest.approx([180_000.0, 183_000.0])


def test_filtro_por_periodo(client, seed_snapshots):
    seed_snapshots(["2026-11-01", "2026-12-01"], [100.0, 200.0])
    resp = client.get("/api/v1/historico/evolucao", params={"inicio": "2026-11-15", "fim": "2026-12-31"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["datas"] == ["2026-12-01"]


def test_repo_roundtrip(seed_snapshots):
    seed_snapshots(["2026-11-01", "2026-11-08"], [180_000.0, 183_000.0])
    repo = SnapshotRepository()
    snaps = repo.get_between("2026-11-01", "2026-11-30")
    assert [s.snapshot_date.isoformat() for s in snaps] == ["2026-11-01", "2026-11-08"]
