import pytest

from app.services.consolidacao import _map_category, _investment_amount, _build_positions


CONTRACT_ACCOUNT_TYPES = {"BANK", "CREDIT", "SECURITY", "MUTUAL_FUND",
                          "FIXED_INCOME", "ETF", "EQUITY"}

@pytest.mark.parametrize("t,expected", [
    ("BANK", "banco"), ("CREDIT", "cartao"),
    ("SECURITY", "investimento"), ("MUTUAL_FUND", "investimento"),
    ("FIXED_INCOME", "investimento"), ("ETF", "investimento"),
    ("EQUITY", "investimento"),
])
def test_map_category_contrato_real(t, expected):
    assert _map_category({"type": t}) == expected

def test_type_desconhecido_nao_vira_caixa():
    assert _map_category({"type": "NOVO_TYPE_FUTURO"}) == "outros"

def test_value_nunca_e_usado_como_valor():
    # regression: value é quantidade de cotas
    assert _investment_amount({"balance": None, "value": 500, "amount": 1500}) == 1500.0

def test_investimento_nao_duplica_via_contas():
    positions = _build_positions(
        [{"name": "BOVA11", "type": "ETF", "subtype": "ETF", "balance": 118.4}],
        [{"name": "BOVA11", "type": "ETF", "balance": 118.4}],
        "Teste",
    )
    assert len(positions) == 1
