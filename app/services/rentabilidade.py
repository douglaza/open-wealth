"""Cálculo de rentabilidade. Funções puras + fina camada de acesso a dados."""
from app.repositories.snapshot_repository import SnapshotRepository


def _variacao(valor_anterior, valor_atual):
    var_abs = valor_atual - valor_anterior
    var_pct = round(var_abs / valor_anterior * 100, 2) if valor_anterior else None
    return var_abs, var_pct


def calcular_rentabilidade_total(anterior: dict, atual: dict) -> dict:
    var_abs, var_pct = _variacao(anterior["total"], atual["total"])
    return {
        "data_anterior": anterior["snapshot_date"],
        "data_atual": atual["snapshot_date"],
        "valor_anterior": anterior["total"],
        "valor_atual": atual["total"],
        "variacao_abs": round(var_abs, 2),
        "variacao_pct": var_pct,
    }


def calcular_rentabilidade_por_instituicao(rows: list[dict]) -> list[dict]:
    resultado = []
    for r in rows:
        var_abs, var_pct = _variacao(r["valor_anterior"], r["valor_atual"])
        resultado.append({**r, "variacao_abs": var_abs, "variacao_pct": var_pct})
    return resultado


def rentabilidade_total(repo=None):
    """Patrimônio total nos dois últimos snapshots."""
    repo = repo or SnapshotRepository()
    rows = repo.ultimos_totais_por_data(2)
    if len(rows) < 2:
        return {"msg": "Dados insuficientes — precisa de 2 snapshots"}
    return calcular_rentabilidade_total(rows[0], rows[1])


def rentabilidade_por_instituicao(repo=None):
    """Retorno entre os dois snapshots mais recentes, por instituição."""
    repo = repo or SnapshotRepository()
    return calcular_rentabilidade_por_instituicao(repo.totais_por_instituicao_ultimas_datas())
