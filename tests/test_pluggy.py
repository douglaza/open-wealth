"""
Testes do cliente Pluggy com respostas mockadas.
Nenhuma chamada real à API acontece — usamos unittest.mock.
"""
import time
from unittest.mock import patch, MagicMock

import pytest

from app.integrations.pluggy_client import PluggyClient  # <- caminho real


# ---------- FIXTURES (respostas simuladas da API) ----------

MOCK_ITEM = {
    "id": "item-123",
    "status": "UPDATED",
    "connectorId": 12,
    "institution": "Banco Exemplo",
}

MOCK_ACCOUNTS = [
    {"id": "acc-1", "type": "CHECKING", "name": "Conta Corrente",
     "balance": 5000.0, "currency": "BRL"},
    {"id": "acc-2", "type": "SAVINGS", "name": "Poupança",
     "balance": 12000.0, "currency": "BRL"},
]

MOCK_INVESTMENTS = [
    {"id": "inv-1", "name": "Tesouro Selic 2029", "type": "government_bond",
     "quantity": 1, "price": 15000.0},
    {"id": "inv-2", "name": "PETR4", "type": "stock",
     "quantity": 100, "price": 38.50},
]

MOCK_TRANSACTIONS = [
    {"id": "tx-1", "description": "Salário", "amount": -8000.0,
     "date": "2025-01-05", "category": "income"},
    {"id": "tx-2", "description": "Mercado", "amount": 450.0,
     "date": "2025-01-07", "category": "groceries"},
]


# ---------- FIXTURE DO CLIENTE ----------

@pytest.fixture
def client():
    return PluggyClient(
        client_id="fake-id",
        client_secret="fake-secret",
        settings=None,  # evita tocar no settings de produção
    )


# ---------- TESTES ----------

class TestPluggyClient:

    def test_get_item(self, client):
        with patch.object(client, "_get", return_value=MOCK_ITEM):
            item = client.get_item("item-123")
            assert item["id"] == "item-123"
            assert item["institution"] == "Banco Exemplo"

    def test_get_accounts_returns_list(self, client):
        with patch.object(client, "_get", return_value=MOCK_ACCOUNTS):
            accounts = client.get_accounts("item-123")
            assert len(accounts) == 2
            assert accounts[0]["balance"] == 5000.0

    def test_get_investments(self, client):
        with patch.object(client, "_get", return_value=MOCK_INVESTMENTS):
            investments = client.get_investments("item-123")
            assert len(investments) == 2
            # validação de valor calculado
            assert investments[1]["quantity"] * investments[1]["price"] == 3850.0

    def test_get_transactions(self, client):
        with patch.object(client, "_get", return_value=MOCK_TRANSACTIONS):
            transactions = client.get_transactions("acc-1")
            assert len(transactions) == 2
            assert transactions[0]["category"] == "income"

    def test_api_error_raises(self, client):
        with patch.object(client, "_get", side_effect=Exception("API error")):
            with pytest.raises(Exception):
                client.get_accounts("item-invalido")

    def test_token_sent_in_headers(self, client):
        client._token = "fake-token"
        client._token_expiry = time.time() + 3600  # token "válido"

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        with patch("requests.get", return_value=mock_response) as mock_get:
            client._get("/accounts")
            headers = mock_get.call_args.kwargs["headers"]
            assert headers["X-API-KEY"] == "fake-token"


# ---------- AUTH ----------

def test_init_sem_settings_usa_settings_de_producao():
    """Cobre o fallback: importa settings global quando nada é passado."""
    with patch("app.core.config.settings") as fake_settings:
        fake_settings.pluggy_client_id = "prod-id"
        fake_settings.pluggy_client_secret = "prod-secret"
        fake_settings.pluggy_base_url = "https://api.pluggy.ai"
        c = PluggyClient()
        assert c._client_id == "prod-id"
        assert c._client_secret == "prod-secret"


def test_authenticate_sucesso(client):
    """POST /auth retorna apiKey; token e expiry são gravados."""
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"apiKey": "token-novo"}
    with patch("requests.post", return_value=resp) as mock_post:
        token = client._authenticate()
    assert token == "token-novo"
    assert client._token == "token-novo"
    assert client._token_expiry > time.time()
    body = mock_post.call_args.kwargs["json"]
    assert body == {"clientId": "fake-id", "clientSecret": "fake-secret"}


def test_authenticate_erro_levanta(client):
    resp = MagicMock(status_code=401, text="invalid credentials")
    resp.raise_for_status.side_effect = Exception("401")
    with patch("requests.post", return_value=resp):
        with pytest.raises(Exception):
            client._authenticate()


def test_get_token_reusa_token_valido(client):
    client._token = "ainda-valido"
    client._token_expiry = time.time() + 3600
    assert client._get_token() == "ainda-valido"


def test_get_token_renova_quando_expirado(client):
    client._token = "expirado"
    client._token_expiry = time.time() - 1
    with patch.object(client, "_authenticate", return_value="renovado") as m:
        assert client._get_token() == "renovado"
        m.assert_called_once()


def test_get_token_renova_quando_ausente(client):
    with patch.object(client, "_authenticate", return_value="novo") as m:
        assert client._get_token() == "novo"
        m.assert_called_once()


# ---------- HTTP CORE ----------

def _fake_resp(status=200, payload=None):
    r = MagicMock(status_code=status, text="")
    r.json.return_value = payload or {}
    return r


def test_get_envia_token_e_retorna_json(client):
    client._token = "tk"
    client._token_expiry = time.time() + 3600
    with patch("requests.get", return_value=_fake_resp(payload={"results": [1]})) as mg:
        data = client._get("/accounts", params={"itemId": "i1"})
    assert data == {"results": [1]}
    url = mg.call_args.args[0]
    assert url == "https://api.pluggy.ai/accounts"
    assert mg.call_args.kwargs["headers"]["X-API-KEY"] == "tk"


def test_get_erro_levanta(client):
    client._token = "tk"
    client._token_expiry = time.time() + 3600
    resp = _fake_resp(status=500, payload={"error": "boom"})
    resp.raise_for_status.side_effect = Exception("500")
    with patch("requests.get", return_value=resp):
        with pytest.raises(Exception):
            client._get("/accounts")


# ---------- EXTRACT ----------

def test_extract_results_dict():
    assert PluggyClient._extract_results({"results": [1, 2]}) == [1, 2]

def test_extract_results_list():
    assert PluggyClient._extract_results([1, 2]) == [1, 2]

def test_extract_results_sem_chave_results():
    assert PluggyClient._extract_results({}) == []


# ---------- ENDPOINTS ----------

def test_get_item_usa_item_id_do_ambiente(client):
    client._item_id = "item-do-env"
    with patch.object(client, "_get", return_value={"id": "item-do-env"}) as m:
        client.get_item()
    m.assert_called_once_with("/items/item-do-env")


def test_get_accounts_e_investments(client):
    with patch.object(client, "_get", return_value={"results": MOCK_ACCOUNTS}) as m:
        accs = client.get_accounts("i1")
    m.assert_called_once_with("/accounts", params={"itemId": "i1"})
    assert len(accs) == 2

    with patch.object(client, "_get", return_value={"results": MOCK_INVESTMENTS}):
        invs = client.get_investments("i1")
    assert len(invs) == 2


def test_get_transactions_sem_cursor(client):
    with patch.object(client, "_get", return_value={"results": [], "hasNext": False}) as m:
        client.get_transactions("acc-1")
    m.assert_called_once_with("/v2/transactions", params={"accountId": "acc-1"})


def test_get_transactions_com_cursor(client):
    with patch.object(client, "_get", return_value={"results": []}) as m:
        client.get_transactions("acc-1", cursor="abc")
    m.assert_called_once_with("/v2/transactions",
                              params={"accountId": "acc-1", "cursor": "abc"})


def test_get_all_transactions_pagina_ate_fim(client):
    """Cobre o loop de paginação."""
    paginas = [
        {"results": [{"id": "tx-1"}], "hasNext": True, "nextCursor": "c2"},
        {"results": [{"id": "tx-2"}], "hasNext": False},
    ]
    with patch.object(client, "get_transactions", side_effect=paginas):
        txs = client.get_all_transactions("acc-1")
    assert [t["id"] for t in txs] == ["tx-1", "tx-2"]


def test_get_all_transactions_primeira_pagina_vazia(client):
    with patch.object(client, "get_transactions",
                      return_value={"results": [], "hasNext": False}):
        assert client.get_all_transactions("acc-1") == []
