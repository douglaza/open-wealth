"""
Testes do cliente Pluggy com respostas mockadas.
Nenhuma chamada real à API acontece — usamos unittest.mock.
"""
import pytest
import time
from unittest.mock import patch, MagicMock
from app.services.pluggy_client import PluggyClient


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
    """Cliente Pluggy com credenciais fake, sem chamar a API real."""
    with patch.object(PluggyClient, "_authenticate", return_value="fake-token"):
        return PluggyClient(client_id="fake", client_secret="fake")


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
