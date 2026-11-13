"""Endpoints da API. Orquestram serviços — não tocam em SQL nem no cliente."""
from datetime import date
from fastapi import APIRouter, Depends

from app.repositories.snapshot_repository import SnapshotRepository
from app.services.rentabilidade import (
    rentabilidade_por_instituicao,
    rentabilidade_total,
)
from app.services.sync import sync_weekly

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


# ...

@router.post("/sync", status_code=202)
def post_sync(
    repo: SnapshotRepository = Depends(get_repo),
    client=Depends(get_client),
):
    sync_weekly(client=client, repo=repo)
    return {"status": "ok", "snapshot_date": date.today().isoformat()}



# @router.post("/sync", status_code=202)
# def post_sync(
#     repo: SnapshotRepository = Depends(get_repo),
#     client=Depends(get_client),
# ):
#     sync_weekly(client=client, repo=repo)
#     return {"status": "ok", "snapshot_date": __import__("date").today().isoformat()}
