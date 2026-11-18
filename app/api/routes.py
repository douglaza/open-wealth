"""Endpoints da API. Orquestram serviços — não tocam em SQL nem no cliente."""

import os
import time
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.metrics import (
    INSIGHTS_LATENCY_SECONDS,
    INSIGHTS_REQUESTS_TOTAL,
    refresh_financial_metrics,
)
from app.domain.insights import InsightChatRequest, InsightChatResponse
from app.domain.models import ManualPosition
from app.integrations.llm_client import (
    BaseLLMClient,
    MockLLMClient,
    OllamaLLMClient,
    OpenAILLMClient,
)
from app.repositories.manual_position_repository import (
    ManualPositionRepository,
)
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.context_builder import ContextBuilder
from app.services.historico import (
    crescimento_acumulado,
    evolucao_patrimonial,
)
from app.services.insights_service import InsightsService
from app.services.sync import sync_weekly

router = APIRouter(prefix="/api/v1")


def get_repo() -> SnapshotRepository:
    return SnapshotRepository()


def get_client():
    from app.integrations.pluggy_client import PluggyClient

    return PluggyClient()


@router.post("/sync", status_code=202)
def post_sync(
    repo: SnapshotRepository = Depends(get_repo),
    client=Depends(get_client),
):
    sync_weekly(client=client, repo=repo)
    refresh_financial_metrics(snapshot_repo=repo)
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


# ---- Posições manuais (ativos/passivos) ----


class ManualPositionCreate(BaseModel):
    name: str = Field(..., min_length=1)
    type: Literal["ASSET", "LIABILITY"]
    institution: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0.0)


class ManualPositionResponse(BaseModel):
    id: int
    name: str
    type: str
    institution: str
    category: str
    amount: float
    updated_at: str


class ManualTotalsResponse(BaseModel):
    assets: float
    liabilities: float
    net: float


def get_manual_repo() -> ManualPositionRepository:
    return ManualPositionRepository()


@router.post(
    "/manual-positions",
    response_model=ManualPositionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_position(
    payload: ManualPositionCreate,
    repo: ManualPositionRepository = Depends(get_manual_repo),
) -> ManualPositionResponse:
    pos = ManualPosition(
        name=payload.name,
        type=payload.type,
        institution=payload.institution,
        category=payload.category,
        amount=payload.amount,
    )
    saved = repo.save(pos)
    refresh_financial_metrics(manual_repo=repo)

    assert saved.id is not None
    assert saved.updated_at is not None
    return ManualPositionResponse(
        id=saved.id,
        name=saved.name,
        type=saved.type,
        institution=saved.institution,
        category=saved.category,
        amount=saved.amount,
        updated_at=saved.updated_at,
    )


@router.get(
    "/manual-positions",
    response_model=list[ManualPositionResponse],
)
def list_manual_positions(
    pos_type: Literal["ASSET", "LIABILITY"] | None = Query(default=None, alias="type"),
    repo: ManualPositionRepository = Depends(get_manual_repo),
) -> list[ManualPositionResponse]:
    items = repo.list_by_type(pos_type) if pos_type else repo.list_all()
    return [
        ManualPositionResponse(
            id=item.id or 0,
            name=item.name,
            type=item.type,
            institution=item.institution,
            category=item.category,
            amount=item.amount,
            updated_at=item.updated_at or "",
        )
        for item in items
    ]


@router.get(
    "/manual-positions/totals",
    response_model=ManualTotalsResponse,
)
def get_manual_totals(
    repo: ManualPositionRepository = Depends(get_manual_repo),
) -> ManualTotalsResponse:
    totals = repo.get_totals()
    return ManualTotalsResponse(
        assets=totals.get("assets", 0.0),
        liabilities=totals.get("liabilities", 0.0),
        net=totals.get("net", 0.0),
    )


@router.get(
    "/manual-positions/{position_id}",
    response_model=ManualPositionResponse,
)
def get_manual_position(
    position_id: int,
    repo: ManualPositionRepository = Depends(get_manual_repo),
) -> ManualPositionResponse:
    item = repo.get_by_id(position_id)
    if not item or item.id is None or item.updated_at is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Posição manual não encontrada",
        )
    return ManualPositionResponse(
        id=item.id,
        name=item.name,
        type=item.type,
        institution=item.institution,
        category=item.category,
        amount=item.amount,
        updated_at=item.updated_at,
    )


@router.delete(
    "/manual-positions/{position_id}",
    status_code=status.HTTP_200_OK,
)
def delete_manual_position(
    position_id: int,
    repo: ManualPositionRepository = Depends(get_manual_repo),
) -> dict[str, str]:
    deleted = repo.delete(position_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Posição manual não encontrada",
        )
    refresh_financial_metrics(manual_repo=repo)
    return {"status": "deleted"}


def get_llm_client() -> BaseLLMClient:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "openai":
        return OpenAILLMClient(api_key=os.getenv("OPENAI_API_KEY", ""))
    if provider == "ollama":
        model_name = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
        print(f"🤖 [IA ATIVA] Chamando Ollama com modelo: {model_name}")
        return OllamaLLMClient(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=model_name,
        )
    return MockLLMClient()


def get_insights_service(
    repo: SnapshotRepository = Depends(get_repo),
    manual_repo: ManualPositionRepository = Depends(get_manual_repo),
    llm_client: BaseLLMClient = Depends(get_llm_client),
) -> InsightsService:
    builder = ContextBuilder(snapshot_repo=repo, manual_position_repo=manual_repo)
    return InsightsService(context_builder=builder, llm_client=llm_client)


@router.post("/insights/chat", response_model=InsightChatResponse, status_code=status.HTTP_200_OK)
async def chat_insights(
    request: InsightChatRequest,
    service: InsightsService = Depends(get_insights_service),
) -> InsightChatResponse:
    start_time = time.perf_counter()
    try:
        response = await service.answer_query(request.query)
        INSIGHTS_REQUESTS_TOTAL.labels(status="success").inc()
        return response
    except Exception as exc:
        INSIGHTS_REQUESTS_TOTAL.labels(status="error").inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao gerar insights: {exc}",
        ) from exc
    finally:
        latency = time.perf_counter() - start_time
        INSIGHTS_LATENCY_SECONDS.observe(latency)
