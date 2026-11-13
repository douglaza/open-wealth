from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.domain.models import Position, Snapshot
from app.api.main import app


@pytest.fixture
def client(monkeypatch, repo):
    # injeção: get_repo e get_client devolvem os nossos doubles
    import app.api.routes as routes

    monkeypatch.setattr(routes, "get_repo", lambda: repo)
    monkeypatch.setattr(routes, "get_client", lambda: object())  # nunca usado sem sync
    return TestClient(app)


@pytest.fixture
def snapshot_povoado(repo):
    repo.save_all([Snapshot(
        snapshot_date=date(2025, 6, 1),
        positions=[
            Position(institution="XP", account_type="broker",
                     asset_name="ITSA4", category="Ações", amount=1000.0),
            Position(institution="XP", account_type="broker",
                     asset_name="HGLG11", category="FIIs", amount=500.0),
            Position(institution="NuInvest", account_type="cdb",
                     asset_name="CDB", category="Renda Fixa", amount=500.0),
        ],
    )])


class TestDependencies:
    def test_get_repo_retorna_repository(self):
        from app.api.routes import get_repo
        assert get_repo() is not None

    def test_get_client_importa_lazy(self):
        """O import de PluggyClient é lazy dentro da função — não explode sem credenciais."""
        from app.api.routes import get_client
        assert get_client() is not None


class TestCarteiraInstituicoes:
    def test_sem_snapshot_retorna_mensagem(self, client):
        r = client.get("/api/v1/carteira/instituicoes")
        assert r.status_code == 200
        assert "Nenhum snapshot" in r.json()["msg"]

    def test_agrega_por_instituicao_ordenado(self, client, snapshot_povoado):
        r = client.get("/api/v1/carteira/instituicoes")
        data = r.json()
        assert data == [
            {"institution": "XP", "total": 1500.0},
            {"institution": "NuInvest", "total": 500.0},
        ]

    def test_carteira_total(self, client, snapshot_povoado):
        r = client.get("/api/v1/carteira")
        assert r.json() == {
            "snapshot_date": "2025-06-01",
            "total": 2000.0,
        }

    def test_alocacao_pct(self, client, snapshot_povoado):
        data = client.get("/api/v1/carteira/alocacao").json()
        xp = next(i for i in data if i["institution"] == "XP")
        assert xp["pct"] == 75.0

    def test_alocacao_patrimonio_zerado(self, client, repo):
        repo.save_all([Snapshot(
            snapshot_date=date(2025, 6, 1),
            positions=[Position(
                institution="XP",
                account_type="broker",
                asset_name="ITSA4",
                category="Ações",
                amount=0,
            )],
        )])
        r = client.get("/api/v1/carteira/alocacao")
        assert "zerado" in r.json()["msg"]

    def test_posicoes_model_dump(self, client, snapshot_povoado):
        data = client.get("/api/v1/carteira/posicoes").json()
        assert len(data["positions"]) == 3
        assert {"institution", "account_type", "asset_name",
                "category", "amount"} == set(data["positions"][0].keys())
