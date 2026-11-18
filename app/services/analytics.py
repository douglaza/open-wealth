"""Analytics de patrimônio — regras de negócio da Fase 5.

Funções puras: recebem a série de snapshots [(date, total)] ou
distribuições [(label, valor)] e retornam números. Sem I/O —
a busca de dados fica na camada de API/repository.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

# Normalização de categorias do Pluggy → classes de ativo do relatório
CATEGORY_MAP = {
    "cdi": "Renda Fixa",
    "cdb": "Renda Fixa",
    "tesouro": "Renda Fixa",
    "tesouro direto": "Renda Fixa",
    "renda fixa": "Renda Fixa",
    "lci": "Renda Fixa",
    "lca": "Renda Fixa",
    "acoes": "Ações",
    "ação": "Ações",
    "stock": "Ações",
    "fiis": "FIIs",
    "fii": "FIIs",
    "real estate fund": "FIIs",
    "etf": "ETFs",
    "etfs": "ETFs",
    "banco": "Caixa",
}


def normalize_category(raw: str | None) -> str:
    if not raw:
        return "Outros"
    return CATEGORY_MAP.get(raw.strip().lower(), raw.strip())


def _serie_ordenada(serie: list[tuple[date, Decimal]]) -> list[tuple[date, Decimal]]:
    return sorted(serie, key=lambda p: p[0])


def patrimonio_atual(serie: list[tuple[date, Decimal]]) -> Decimal | None:
    """Total mais recente da série. None se série vazia."""
    serie = _serie_ordenada(serie)
    return serie[-1][1] if serie else None


def _snapshot_proximo(serie: list[tuple[date, Decimal]], alvo: date) -> tuple[date, Decimal] | None:
    """Snapshot com data mais próxima do alvo (≤ alvo)."""
    anteriores = [p for p in serie if p[0] <= alvo]
    return max(anteriores, key=lambda p: p[0]) if anteriores else None


def rentabilidade_por_periodo(
    serie: list[tuple[date, Decimal]],
    inicio: date,
    fim: date | None = None,
) -> float | None:
    """Retorno % entre o snapshot mais próximo de `inicio` e o último ≤ `fim`.

    Regras de negócio:
    - Não exige snapshot na data exata: usa o mais próximo anterior.
    - Se não há snapshot anterior ao início, ou menos de 2 pontos, → None
      (histórico insuficiente; o endpoint responde null, não inventa 0%).
    """
    fim = fim or date.today()
    serie = _serie_ordenada(serie)
    if len(serie) < 2:
        return None
    base = _snapshot_proximo(serie, inicio)
    final = _snapshot_proximo(serie, fim)
    if not base or not final or base[0] == final[0] or base[1] == 0:
        return None
    return float((final[1] - base[1]) / base[1]) * 100


def rentabilidade_30d(serie: list[tuple[date, Decimal]]) -> float | None:
    return rentabilidade_por_periodo(serie, date.fromordinal(date.today().toordinal() - 30))


def rentabilidade_ytd(serie: list[tuple[date, Decimal]]) -> float | None:
    hoje = date.today()
    return rentabilidade_por_periodo(serie, date(hoje.year, 1, 1), hoje)


def alocacao_por_classe(
    distribuicao: list[tuple[str, Decimal]],
) -> list[dict]:
    """Alocação % por classe, com normalização de categorias.

    Exclusões de valor: itens com valor ≤ 0 são ignorados (cartões de
    crédito com saldo negativo não são "classe de ativo" negativa).
    """
    agregado: dict[str, Decimal] = {}
    for raw, valor in distribuicao:
        if valor <= 0:
            continue
        classe = normalize_category(raw)
        agregado[classe] = agregado.get(classe, Decimal(0)) + valor
    total = sum(agregado.values())
    if total == 0:
        return []
    return [
        {
            "classe": classe,
            "valor": float(valor),
            "percentual": round(float(valor / total * 100), 1),
        }
        for classe, valor in sorted(agregado.items(), key=lambda kv: -kv[1])
    ]


def concentracao(
    distribuicao: list[tuple[str, Decimal]],
) -> dict | None:
    """Concentração por instituição: top-1 % e índice HHI.

    HHI = soma dos quadrados das participações (%), escala 0-10.000
    (convenção DOJ para mercados; > 2500 = "altamente concentrado").
    """
    agregado: dict[str, Decimal] = {}
    for inst, valor in distribuicao:
        if valor <= 0:
            continue
        agregado[inst] = agregado.get(inst, Decimal(0)) + valor
    total = sum(agregado.values())
    if not agregado or total == 0:
        return None
    participacoes = [float(v / total * 100) for v in agregado.values()]
    hhi = round(sum(p**2 for p in participacoes))
    top1 = max(agregado.items(), key=lambda kv: kv[1])
    return {
        "top1_instituicao": top1[0],
        "top1_percentual": round(float(top1[1] / total * 100), 1),
        "n_instituicoes": len(agregado),
        "hhi": hhi,
        "classificacao": (
            "altamente concentrado"
            if hhi > 2500
            else "moderadamente concentrado"
            if hhi > 1500
            else "distribuído"
        ),
    }
