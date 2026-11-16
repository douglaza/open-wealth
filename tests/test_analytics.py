from decimal import Decimal

from app.services.analytics import (
    alocacao_por_classe,
    concentracao,
    patrimonio_atual,
)


def test_patrimonio_serie_vazia():
    assert patrimonio_atual([]) is None


def test_alocacao_normaliza_categorias():
    dist = [("CDI", Decimal(500)), ("Tesouro Direto", Decimal(500)), ("Stock", Decimal(1000))]
    out = alocacao_por_classe(dist)
    classes = {c["classe"]: c["percentual"] for c in out}
    assert classes["Renda Fixa"] == 50.0
    assert classes["Ações"] == 50.0


def test_alocacao_ignora_valores_negativos():
    dist = [("CDI", Decimal(900)), ("Credit Card", Decimal(-100)), ("ETF", Decimal(100))]
    out = alocacao_por_classe(dist)
    assert all(c["percentual"] > 0 for c in out)
    assert sum(c["percentual"] for c in out) == 100.0


def test_concentracao_hhi_um_player():
    out = concentracao([("Rico", Decimal(100))])
    assert out["hhi"] == 10000 and out["classificacao"] == "altamente concentrado"


def test_concentracao_hhi_quatro_iguais():
    dist = [(f"b{i}", Decimal(25)) for i in range(4)]
    out = concentracao(dist)
    assert out["hhi"] == 2500  # 4 X 25²
    assert out["top1_percentual"] == 25.0


def test_concentracao_distribuicao_vazia():
    assert concentracao([]) is None
