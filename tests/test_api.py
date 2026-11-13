"""Testes da API. FakeClient/FakeRepo no padrão dos testes de sync."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.routes import get_client, get_repo
from app.core.exceptions import PluggyError


class FakeClient:
    def __init__(self, fail=False):
        self._fail = fail

    def get_item(self):
        if self._fail:
            raise PluggyError("Auth falhou: 401")
        return {"id": "item-1", "connector": {"name": "Nubank"}}

    def get_accounts(self, item_id):
        return []

    def get_investments(self, item_id):
        return []


class FakeRepo:
    def __init__(self):
        self.calls = []

    def snapshot_exists(self, snapshot_date, institution):
        return False

    def save_snapshot_row(self, *args):
        self.calls.append(("save_snapshot_row", args))

    def upsert_item(self, *args):
        self.calls.append(("upsert_item", args))

    def upsert_account(self, *args):
        self.calls.append(("upsert_account", args))

    def upsert_investment(self, *args):
        self.calls.append(("upsert_investment", args))

    def commit(self):
        self.calls.append(("commit",))

    def ultimos_totais_por_data(self, n):
        return [
            {"snapshot_date": "2025-01-01", "total": 100.0},
            {"snapshot_date": "2025-01-02", "total": 110.0},
        ]

    def totais_por_instituicao_ultimas_datas(self):
        return [
            {
                "data_atual": "2025-01-02",
                "data_anterior": "2025-01-01",
                "institution": "Nubank",
                "valor_anterior": 100.0,
                "valor_atual": 110.0,
            }
        ]


@pytest.fixture
def client():
    repo = FakeRepo()
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_client] = lambda: FakeClient()
    return TestClient(app), repo


def test_sync_endpoint_commita(client):
    tc, repo = client
    resp = tc.post("/api/v1/sync")
    assert resp.status_code == 202
    assert resp.json()["status"] == "ok"
    assert ("commit",) in repo.calls
    assert any(c[0] == "upsert_item" for c in repo.calls)


def test_sync_pluggy_error_vira_502(client):
    tc, _ = client
    tc.app.dependency_overrides[get_client] = lambda: FakeClient(fail=True)
    resp = tc.post("/api/v1/sync")
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Falha ao consultar o Pluggy"


def test_rentabilidade_total(client):
    tc, _ = client
    resp = tc.get("/api/v1/rentabilidade/total")
    assert resp.status_code == 200
    body = resp.json()
    assert body["variacao_abs"] == 10.0
    assert body["variacao_pct"] == 10.0


def test_rentabilidade_instituicoes(client):
    tc, _ = client
    resp = tc.get("/api/v1/rentabilidade/instituicoes")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["institution"] == "Nubank"
    assert body[0]["variacao_abs"] == 10.0


def test_rentabilidade_sem_dados(client):
    tc, _ = client
    tc.app.dependency_overrides[get_repo] = lambda: FakeRepoVazio()
    resp = tc.get("/api/v1/rentabilidade/total")
    assert resp.status_code == 200
    assert "msg" in resp.json()


class FakeRepoVazio(FakeRepo):
    def ultimos_totais_por_data(self, n):
        return []

    def totais_por_instituicao_ultimas_datas(self):
        return []
