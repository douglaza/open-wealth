# tests/test_models.py
import pytest
from app.domain.models import Position

BASE = {"institution": "Banco X", "asset_name": "Conta Corrente", "category": "caixa"}

def test_patrimonio_nao_pode_ser_negativo():
    with pytest.raises(ValueError, match="patrimônio não pode ser negativo"):
        Position(**BASE, account_type="BANK", amount=-100.0)

def test_cartao_credito_pode_ser_negativo():
    acc = Position(**BASE, account_type="CREDIT", amount=-350.0)
    assert acc.amount == -350.0
