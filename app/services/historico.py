from dataclasses import dataclass, field

from app.domain.models import Snapshot


@dataclass
class SerieHistorica:
    datas: list[str] = field(default_factory=list)
    valores: list[float] = field(default_factory=list)


def evolucao_patrimonial(snapshots: list[Snapshot]) -> SerieHistorica:
    ordenados = sorted(snapshots, key=lambda s: s.snapshot_date)
    return SerieHistorica(
        datas=[s.snapshot_date.isoformat() for s in ordenados],
        valores=[s.total for s in ordenados],
    )


def evolucao_mensal(snapshots: list[Snapshot]) -> SerieHistorica:
    por_mes: dict[tuple[int, int], Snapshot] = {}
    for s in snapshots:
        chave = (s.snapshot_date.year, s.snapshot_date.month)
        atual = por_mes.get(chave)
        if atual is None or s.snapshot_date >= atual.snapshot_date:
            por_mes[chave] = s
    ordenados = sorted(por_mes.values(), key=lambda s: s.snapshot_date)
    return SerieHistorica(
        datas=[s.snapshot_date.strftime("%Y-%m") for s in ordenados],
        valores=[s.total for s in ordenados],
    )


def crescimento_acumulado(snapshots: list[Snapshot]) -> SerieHistorica:
    serie = evolucao_patrimonial(snapshots)
    base = next((v for v in serie.valores if v > 0), None)
    if base is None:
        return SerieHistorica(datas=serie.datas, valores=[0.0] * len(serie.valores))
    variacoes = []
    for v in serie.valores:
        if v <= 0:
            variacoes.append(0.0)          # antes da base: sem variação definida
        else:
            variacoes.append((v - base) / base)
    return SerieHistorica(datas=serie.datas, valores=variacoes)