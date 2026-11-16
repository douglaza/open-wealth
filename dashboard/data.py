from datetime import timedelta
from collections.abc import Mapping, Sequence
from typing import Any
from dataclasses import dataclass

import pandas as pd


EXCLUDED_CATEGORIES = frozenset({"banco", "cartao"})
"""Categorias não relacionadas a investimentos, excluídas dos agregados do dashboard."""


def _hygienize(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if dict(row).get("category") not in EXCLUDED_CATEGORIES
    ]


@dataclass(frozen=True)
class SnapshotSummary:
    """Agregados do snapshot mais recente, prontos para o dashboard."""
    snapshots: pd.DataFrame        # linhas do snapshot mais recente
    total: float                   # patrimônio total
    evolution: pd.DataFrame        # série histórica [snapshot_date, amount]
    institutions: pd.DataFrame     # concentração por instituição
    institutions_pct: pd.DataFrame # idem + coluna [pct] (0-1)
    hhi: float | None              # índice de Herfindahl (0=difuso, 1=concentrado)
    allocation: pd.DataFrame       # alocação por categoria no snapshot mais recente
    returns: dict                  # {"return_30d": float|None, "return_ytd": float|None}


def prepare_snapshot_data(
    rows: Sequence[Mapping[str, Any]],
) -> SnapshotSummary:
    rows = _hygienize(list(rows))
    snapshots = pd.DataFrame([dict(row) for row in rows])
    if snapshots.empty:
        return SnapshotSummary(
            snapshots=snapshots,
            total=0.0,
            evolution=pd.DataFrame(columns=["snapshot_date", "amount"]),
            institutions=pd.DataFrame(columns=["institution", "amount"]),
            institutions_pct=pd.DataFrame(columns=["institution", "amount", "pct"]),
            hhi=None,
            allocation=pd.DataFrame(columns=["category", "amount"]),
            returns={"return_30d": None, "return_ytd": None},
        )


    snapshots["snapshot_date"] = pd.to_datetime(
        snapshots["snapshot_date"], errors="raise"
    )
    snapshots["amount"] = pd.to_numeric(
        snapshots["amount"], errors="raise"
    ).astype("float64")

    latest_date = snapshots["snapshot_date"].max()
    latest_snapshots = snapshots[snapshots["snapshot_date"] == latest_date]
    latest_total = float(latest_snapshots["amount"].sum())
    evolution = (
        snapshots.groupby("snapshot_date", as_index=False)["amount"]
        .sum()
        .sort_values("snapshot_date")
    )
    institutions = (
        latest_snapshots.groupby("institution", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
        .reset_index(drop=True)
    )
    returns = calculate_returns(evolution, latest_total)

    institutions_pct, hhi = calculate_concentration(institutions, latest_total)
    allocation = calculate_allocation(latest_snapshots)

    return SnapshotSummary(
        snapshots=snapshots,
        total=latest_total,
        evolution=evolution,
        institutions=institutions,
        institutions_pct=institutions_pct,
        hhi=hhi,
        allocation=allocation,
        returns=returns,
    )


def calculate_concentration(
    institutions: pd.DataFrame,
    total: float,
) -> tuple[pd.DataFrame, float | None]:
    """
    Adiciona coluna [pct] (share 0-1 de cada instituição) e calcula o HHI.

    HHI = soma dos quadrados dos shares. 1.0 = 100% em uma instituição;
    próximo de 0 = patrimônio difuso.
    """
    if institutions.empty or total <= 0:
        return institutions.assign(pct=[]), None

    pct = institutions.assign(pct=institutions["amount"] / total)
    hhi = float((pct["pct"] ** 2).sum())
    return pct, hhi


def calculate_allocation(latest_snapshots: pd.DataFrame) -> pd.DataFrame:
    """Soma patrimônio por categoria no snapshot mais recente, ordenado desc."""
    colunas = ["category", "amount"]
    if latest_snapshots.empty:
        return pd.DataFrame(columns=colunas + ["pct"])
    if "category" not in latest_snapshots.columns:
        latest_snapshots = latest_snapshots.assign(category="Não classificado")
    allocation = (
        latest_snapshots.fillna({"category": "Não classificado"})
        .groupby("category", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
        .reset_index(drop=True)
    )
    total = allocation["amount"].sum()
    allocation = allocation.assign(
        pct=allocation["amount"] / total if total > 0 else 0.0
    )
    return allocation



def _find_closest_before(df: pd.DataFrame, target_date: pd.Timestamp) -> float | None:
    """Retorna o valor do snapshot mais próximo ANTES da data alvo."""
    candidates = df[df["snapshot_date"] <= target_date]
    if candidates.empty:
        return None
    row = candidates.sort_values("snapshot_date").iloc[-1]
    return float(row["amount"])


def calculate_returns(evolution: pd.DataFrame, current_total: float) -> dict:
    """
    Calcula rentabilidade 30d e YTD a partir da série de evolução.

    Returns: {"return_30d": float | None, "return_ytd": float | None}
    None = dado insuficiente (ex.: menos de 30 dias de histórico).
    """
    if evolution.empty:
        return {"return_30d": None, "return_ytd": None}

    evolution = evolution.copy()
    evolution["snapshot_date"] = pd.to_datetime(
        evolution["snapshot_date"], errors="raise"
    )
    latest_date = evolution["snapshot_date"].max()

    # --- 30 dias ---
    base_30d = _find_closest_before(evolution, latest_date - timedelta(days=30))
    return_30d = (
        (current_total / base_30d) - 1 if base_30d and base_30d > 0 else None
    )

    # --- YTD ---
    last_year = latest_date.year - 1
    year_end = pd.Timestamp(f"{last_year}-12-31")
    base_ytd = _find_closest_before(evolution, year_end)
    return_ytd = (
        (current_total / base_ytd) - 1 if base_ytd and base_ytd > 0 else None
    )

    return {"return_30d": return_30d, "return_ytd": return_ytd}
