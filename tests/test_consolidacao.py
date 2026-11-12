from datetime import date
from unittest.mock import MagicMock

from app.services.consolidacao import sync_all, get_totals


def _fake_client():
    client = MagicMock()
    client.get_item.return_value = {
        "id": "item-123",
        "connector": {"name": "Itaú"},
    }
    client.get_accounts.return_value = [
        {"name": "Conta Corrente", "type": "CHECKING", "balance": 43701.43},
        {"name": "Cartão", "type": "CREDIT", "balance": -1006.20},
    ]
    client.get_investments.return_value = [
        {"name": "CDB", "type": "FIXED_INCOME", "value": 10000.0},
    ]
    return client


def test_sync_all_monta_snapshot():
    snapshot = sync_all(_fake_client())

    assert snapshot.snapshot_date == date.today()
    assert len(snapshot.positions) == 3
    assert snapshot.positions[0].institution == "Itaú"
    assert snapshot.positions[0].amount == 43701.43


def test_get_totals_agrega_por_instituicao():
    snapshot = sync_all(_fake_client())
    totals = get_totals(snapshot)

    assert totals["total"] == 43701.43 - 1006.20 + 10000.0
    assert totals["by_institution"]["Itaú"] == 43701.43 - 1006.20 + 10000.0


class TestValorPosicaoInvestimento:
    """Regressão: bug do value null / amount divergente (CONTEXT.md 4.8)."""

    def _make_client(self, investments):
        client = MagicMock()
        client.get_item.return_value = {
            "id": "item-123",
            "connector": {"name": "BANCO BTG PACTUAL S/A"},
        }
        client.get_accounts.return_value = []
        client.get_investments.return_value = investments
        return client

    def test_investment_value_null_usa_balance(self):
        """value null NÃO pode zerar a posição; balance é a fonte da verdade."""
        client = self._make_client([
            {
                "name": "ISUS11 STOCK",
                "type": "ETF",
                "balance": 2000.0,
                "value": None,
                "amount": 2000.0,
                "quantity": 1,
            },
        ])
        snapshot = sync_all(client)

        pos = next(p for p in snapshot.positions if p.asset_name == "ISUS11 STOCK")
        assert pos.amount == 2000.0

    def test_investment_nao_usa_amount_quando_diverge_de_balance(self):
        """CDR do sandbox: amount=2500 mas balance=2000 (dashboard exibe 2000).
        Usar amount inflaria o patrimônio."""
        client = self._make_client([
            {
                "name": "CDR",
                "type": "FIXED_INCOME",
                "subtype": "CDB",
                "balance": 2000.0,
                "value": None,
                "amount": 2500.0,
            },
        ])
        snapshot = sync_all(client)

        pos = next(p for p in snapshot.positions if p.asset_name == "CDR")
        assert pos.amount == 2000.0, "posição deve usar balance (2000), não amount (2500)"

    def test_investment_balance_ausente_faz_fallback_para_value(self):
        """Cascata: balance ausente → value → 0.0."""
        client = self._make_client([
            {"name": "X", "type": "ETF", "balance": None, "value": 150.0},
            {"name": "Y", "type": "ETF", "balance": None, "value": None},
        ])
        snapshot = sync_all(client)

        valores = {p.asset_name: p.amount for p in snapshot.positions}
        assert valores["X"] == 150.0
        assert valores["Y"] == 0.0

    def test_agregacao_soma_valores_apos_cascata(self):
        """Mesma instituição, fontes de verdade diferentes:
        CDB usa balance (2000, ignorando amount=2500) e ETF cai no fallback value (150).
        A agregação tem que somar os valores APÓS a cascata, não os brutos."""
        client = self._make_client([
            {
                "name": "CDB",
                "type": "FIXED_INCOME",
                "subtype": "CDB",
                "balance": 2000.0,
                "value": None,
                "amount": 2500.0,
            },
            {"name": "ETF", "type": "ETF", "balance": None, "value": 150.0},
        ])
        snapshot = sync_all(client)
        totals = get_totals(snapshot)

        assert totals["by_institution"]["BANCO BTG PACTUAL S/A"] == 2150.0
        assert totals["total"] == 2150.0


def test_cartao_negativo_e_dívida():
    snapshot = sync_all(_fake_client())
    cartao = [p for p in snapshot.positions if p.account_type == "CREDIT"][0]
    assert cartao.amount == -1006.2        # dívida preservada, não clampada
    patrimonios = [p for p in snapshot.positions if p.account_type != "CREDIT"]
    assert all(p.amount >= 0 for p in patrimonios)
