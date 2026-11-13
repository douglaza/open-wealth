"""Endpoints da API. Orquestram serviços — não tocam em SQL nem no cliente."""
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.repositories.snapshot_repository import SnapshotRepository
from app.services.rentabilidade import (
    rentabilidade_por_instituicao,
    rentabilidade_total,
)
from app.services.sync import sync_weekly

from app.services.historico import (
    evolucao_patrimonial,
    crescimento_acumulado,
    SerieHistorica,
)


router = APIRouter(prefix="/api/v1")


def get_repo() -> SnapshotRepository:
    return SnapshotRepository()


def get_client():
    from app.integrations.pluggy_client import PluggyClient
    return PluggyClient()


@router.get("/rentabilidade/total")
def get_rentabilidade_total(repo: SnapshotRepository = Depends(get_repo)):
    return rentabilidade_total(repo)


@router.get("/rentabilidade/instituicoes")
def get_rentabilidade_instituicoes(repo: SnapshotRepository = Depends(get_repo)):
    return rentabilidade_por_instituicao(repo)


@router.post("/sync", status_code=202)
def post_sync(
    repo: SnapshotRepository = Depends(get_repo),
    client=Depends(get_client),
):
    sync_weekly(client=client, repo=repo)
    return {"status": "ok", "snapshot_date": date.today().isoformat()}


# ---- Histórico ----

@router.get("/historico/evolucao")
def get_evolucao(
    inicio: str | None = Query(None, description="YYYY-MM-DD"),
    fim: str | None = Query(None, description="YYYY-MM-DD"),
    repo: SnapshotRepository = Depends(get_repo),
):
    snapshots = repo.get_between(inicio, fim) if inicio or fim else repo.get_all()
    return evolucao_patrimonial(snapshots)


@router.get("/historico/acumulado")
def get_acumulado(
    inicio: str | None = Query(None),
    fim: str | None = Query(None),
    repo: SnapshotRepository = Depends(get_repo),
):
    snapshots = repo.get_between(inicio, fim) if inicio or fim else repo.get_all()
    return crescimento_acumulado(snapshots)



# ---- Carteira (snapshot atual) ----

@router.get("/carteira")
def get_carteira(repo: SnapshotRepository = Depends(get_repo)):
    snapshot = repo.get_latest()
    if snapshot is None:
        return {"msg": "Nenhum snapshot disponível. Execute /sync primeiro."}
    return {
        "snapshot_date": snapshot.snapshot_date.isoformat(),
        "total": snapshot.total,
    }


@router.get("/carteira/posicoes")
def get_posicoes(repo: SnapshotRepository = Depends(get_repo)):
    snapshot = repo.get_latest()
    if snapshot is None:
        return {"msg": "Nenhum snapshot disponível. Execute /sync primeiro."}
    return {
        "snapshot_date": snapshot.snapshot_date.isoformat(),
        "positions": [p.model_dump(exclude={"updated_at"}) for p in snapshot.positions],
    }


@router.get("/carteira/instituicoes")
def get_instituicoes(repo: SnapshotRepository = Depends(get_repo)):
    snapshot = repo.get_latest()
    if snapshot is None:
        return {"msg": "Nenhum snapshot disponível. Execute /sync primeiro."}
    por_inst: dict[str, float] = {}
    for p in snapshot.positions:
        por_inst[p.institution] = por_inst.get(p.institution, 0.0) + p.amount
    return [
        {"institution": inst, "total": total}
        for inst, total in sorted(por_inst.items(), key=lambda x: -x[1])
    ]


@router.get("/carteira/alocacao")
def get_alocacao(repo: SnapshotRepository = Depends(get_repo)):
    snapshot = repo.get_latest()
    if snapshot is None:
        return {"msg": "Nenhum snapshot disponível. Execute /sync primeiro."}
    total = snapshot.total
    if total == 0:
        return {"msg": "Patrimônio zerado; alocação indisponível."}
    por_inst: dict[str, float] = {}
    for p in snapshot.positions:
        por_inst[p.institution] = por_inst.get(p.institution, 0.0) + p.amount
    return [
        {"institution": inst, "total": v, "pct": round(v / total * 100, 2)}
        for inst, v in sorted(por_inst.items(), key=lambda x: -x[1])
    ]
