"""Testes das séries históricas (Fase 3) — padrão AAA."""

from datetime import date
from dataclasses import dataclass
from app.domain.models import Snapshot, Position
import pytest

from app.services.historico import (
    SerieHistorica,
    evolucao_patrimonial,
    evolucao_mensal,
    crescimento_acumulado,
)


@dataclass
class SnapshotFake:
    """Substituto leve do Snapshot real: só data e total."""
    snapshot_date: date
    total: float


def snap(iso: str, total: float) -> SnapshotFake:
    return SnapshotFake(snapshot_date=date.fromisoformat(iso), total=total)


# ---------- evolucao_patrimonial ----------

def test_evolucao_retorna_pares_data_total_em_ordem():
    # Arrange: snapshots fora de ordem de propósito
    snapshots = [snap("2026-11-15", 184_000.0),
                 snap("2026-11-01", 180_000.0),
                 snap("2026-11-08", 183_000.0)]

    # Act
    serie = evolucao_patrimonial(snapshots)

    # Assert: datas ordenadas, valores casados
    assert serie.datas == ["2026-11-01", "2026-11-08", "2026-11-15"]
    assert serie.valores == [180_000.0, 183_000.0, 184_000.0]


def test_evolucao_com_lista_vazia_retorna_serie_vazia():
    assert evolucao_patrimonial([]) == SerieHistorica(datas=[], valores=[])


def test_evolucao_com_snapshot_unico():
    serie = evolucao_patrimonial([snap("2026-11-01", 100.0)])
    assert serie.datas == ["2026-11-01"]
    assert serie.valores == [100.0]


# ---------- evolucao_mensal ----------

def test_mensal_usa_ultimo_snapshot_de_cada_mes():
    # Arrange: 3 meses, com vários snapshots dentro de novembro
    snapshots = [snap("2026-09-30", 170_000.0),
                 snap("2026-10-05", 175_000.0),
                 snap("2026-10-20", 178_000.0),   # último de outubro
                 snap("2026-11-01", 180_000.0),
                 snap("2026-11-15", 184_000.0)]   # último de novembro

    # Act
    serie = evolucao_mensal(snapshots)

    # Assert: fechamento de cada mês, meses em ordem
    assert serie.datas == ["2026-09", "2026-10", "2026-11"]
    assert serie.valores == [170_000.0, 178_000.0, 184_000.0]


def test_mensal_com_mes_de_snapshot_unico():
    # Arrange: setembro tem um snapshot só — ele é o fechamento
    snapshots = [snap("2026-09-15", 171_000.0),
                 snap("2026-10-31", 179_000.0)]

    # Act
    serie = evolucao_mensal(snapshots)

    # Assert
    assert serie.datas == ["2026-09", "2026-10"]
    assert serie.valores == [171_000.0, 179_000.0]


def test_mensal_lista_vazia():
    assert evolucao_mensal([]) == SerieHistorica(datas=[], valores=[])


# ---------- crescimento_acumulado ----------

def test_acumulado_calcula_variacao_relativa_ao_primeiro():
    # Arrange
    snapshots = [snap("2026-11-01", 180_000.0),
                 snap("2026-11-08", 183_000.0),
                 snap("2026-11-15", 184_000.0)]

    # Act
    serie = crescimento_acumulado(snapshots)

    # Assert
    # (183000-180000)/180000 = 0.016666...
    # (184000-180000)/180000 = 0.022222...
    assert serie.datas == ["2026-11-01", "2026-11-08", "2026-11-15"]
    assert serie.valores[0] == pytest.approx(0.0)
    assert serie.valores[1] == pytest.approx(3_000.0 / 180_000.0)
    assert serie.valores[2] == pytest.approx(4_000.0 / 180_000.0)


def test_acumulado_com_total_inicial_zero_nao_divide_por_zero():
    # Arrange: primeiro snapshot zerado (cascata de valoração pode gerar 0.0)
    snapshots = [snap("2026-11-01", 0.0),
                 snap("2026-11-08", 500.0)]

    # Act
    serie = crescimento_acumulado(snapshots)

    # Assert: pontos anteriores à primeira base positiva valem 0.0
    assert serie.valores == [0.0, 0.0]


def test_acumulado_com_base_positiva_apos_zero():
    # Arrange: zero no início, depois patrimônio aparece
    snapshots = [snap("2026-11-01", 0.0),
                 snap("2026-11-08", 0.0),
                 snap("2026-11-15", 100.0),
                 snap("2026-11-22", 150.0)]

    # Act
    serie = crescimento_acumulado(snapshots)

    # Assert: base vira o primeiro snapshot > 0 (100.0)
    # 15/11: (100-100)/100 = 0.0 ; 22/11: (150-100)/100 = 0.5
    assert serie.valores == [0.0, 0.0, 0.0, pytest.approx(0.5)]


def test_acumulado_lista_vazia():
    assert crescimento_acumulado([]) == SerieHistorica(datas=[], valores=[])


def test_acumulado_snapshot_unico_e_zero_por_definicao():
    serie = crescimento_acumulado([snap("2026-11-01", 180_000.0)])
    assert serie.valores == [0.0]


def test_evolucao_aceita_snapshot_do_dominio():
    s = Snapshot(
        snapshot_date=date(2026, 11, 1),
        positions=[Position(
            institution="XP",
            account_type="corretagem",
            asset_name="Tesouro Selic",
            category="renda_fixa",
            amount=1000.0,
        )],
    )

    serie = evolucao_patrimonial([s])

    assert serie.datas == ["2026-11-01"]
    assert serie.valores == [pytest.approx(1000.0)]
