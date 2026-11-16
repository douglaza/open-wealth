from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.analytics import (
    alocacao_por_classe,
    concentracao,
    normalize_category,
    patrimonio_atual,
    rentabilidade_30d,
    rentabilidade_por_periodo,
    rentabilidade_ytd,
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


# ---- normalize_category ----


def test_normalize_none_e_vazio():
    assert normalize_category(None) == "Outros"
    assert normalize_category("") == "Outros"


def test_normalize_case_e_espacos():
    assert normalize_category("  CDB ") == "Renda Fixa"
    assert normalize_category("FIIs") == "FIIs"


def test_normalize_desconhecida_retorna_original():
    assert normalize_category("Criptomoeda") == "Criptomoeda"


# ---- rentabilidade_por_periodo ----


def _serie(*valores):
    base = date(2025, 1, 1)
    return [(base + timedelta(days=30 * i), Decimal(v)) for i, v in enumerate(valores)]


def test_rentabilidade_basica():
    serie = _serie("1000", "1100")  # +10%
    out = rentabilidade_por_periodo(serie, date(2025, 1, 1), date(2025, 3, 1))
    assert out == pytest.approx(10.0)


def test_rentabilidade_serie_um_ponto_retorna_none():
    serie = _serie("1000")
    assert rentabilidade_por_periodo(serie, date(2025, 1, 1)) is None


def test_rentabilidade_serie_vazia_retorna_none():
    assert rentabilidade_por_periodo([], date(2025, 1, 1)) is None


def test_rentabilidade_base_zero_retorna_none():
    serie = _serie("0", "1000")
    assert rentabilidade_por_periodo(serie, date(2025, 1, 1), date(2025, 3, 1)) is None


def test_rentabilidade_mesmo_snapshot_inicio_fim_retorna_none():
    serie = _serie("1000", "1100")
    # início e fim caem no mesmo snapshot (o último)
    out = rentabilidade_por_periodo(serie, date(2025, 3, 15), date(2025, 3, 20))
    assert out is None


def test_rentabilidade_sem_snapshot_anterior_ao_inicio_retorna_none():
    serie = _serie("1000", "1100")
    # início antes de qualquer snapshot
    out = rentabilidade_por_periodo(serie, date(2024, 1, 1), date(2025, 3, 1))
    assert out is None


def test_rentabilidade_30d_e_ytd():
    hoje = date.today()
    serie = [
        (hoje - timedelta(days=40), Decimal("1000")),
        (hoje - timedelta(days=10), Decimal("1200")),
    ]
    assert rentabilidade_30d(serie) == pytest.approx(20.0)
    # YTD: base = 1º de janeiro; se hoje é jan/fev, sem ponto anterior → None
    ytd = rentabilidade_ytd(serie)
    assert ytd is None


def test_rentabilidade_ytd_com_base_no_ano_anterior(monkeypatch):
    from app.services import analytics

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2025, 6, 1)

    monkeypatch.setattr(analytics, "date", FixedDate)
    serie = [
        (date(2024, 12, 31), Decimal("1000")),
        (date(2025, 1, 15), Decimal("1100")),
        (date(2025, 6, 1), Decimal("1250")),
    ]
    assert rentabilidade_ytd(serie) == pytest.approx(25.0)


def test_alocacao_vazia_ou_somente_valores_nao_positivos():
    assert alocacao_por_classe([]) == []
    assert alocacao_por_classe([("CDI", Decimal(0)), ("ETF", Decimal(-10))]) == []


def test_concentracao_ignora_valores_nao_positivos():
    assert concentracao([("XP", Decimal(0)), ("Rico", Decimal(-10))]) is None


def test_concentracao_moderada():
    result = concentracao([(f"Instituição {i}", Decimal(1)) for i in range(5)])
    assert result["hhi"] == 2000
    assert result["classificacao"] == "moderadamente concentrado"


def test_concentracao_distribuida():
    result = concentracao([(f"Instituição {i}", Decimal(1)) for i in range(10)])
    assert result["hhi"] == 1000
    assert result["classificacao"] == "distribuído"
