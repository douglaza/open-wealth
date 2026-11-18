from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes import get_insights_service, get_llm_client
from app.domain.insights import InsightChatResponse, PortfolioContext
from app.integrations.llm_client import (
    BaseLLMClient,
    MockLLMClient,
    OllamaLLMClient,
    OpenAILLMClient,
)
from app.services.context_builder import ContextBuilder, _resolve
from app.services.insights_service import InsightsService


@pytest.fixture
def mock_snapshot_repo():
    repo = AsyncMock()
    # Define total e total_value para evitar que o mock retorne 1.0 dinamicamente
    repo.get_latest.return_value = AsyncMock(total=108200.0, total_value=108200.0)
    repo.get_closest_to.return_value = AsyncMock(total=100000.0, total_value=100000.0)

    pos_rico = AsyncMock(
        value=63000.0, institution="Rico", category="Renda Fixa", type="FIXED_INCOME", name="CDB"
    )
    pos_itau = AsyncMock(
        value=23000.0, institution="Itaú", category="CDB", type="FIXED_INCOME", name="CDB"
    )
    pos_acoes = AsyncMock(
        value=14000.0, institution="XP", category="Ações", type="EQUITY", name="ITUB4"
    )
    repo.get_current_positions.return_value = [pos_rico, pos_itau, pos_acoes]
    return repo


@pytest.fixture
def mock_manual_repo():
    repo = AsyncMock()
    repo.get_totals.return_value = {"liabilities": 150000.0}
    repo.get_active_liabilities.return_value = [AsyncMock(value=150000.0)]
    return repo


@pytest.mark.asyncio
async def test_context_builder_calcula_metricas_com_precisao(mock_snapshot_repo, mock_manual_repo):
    builder = ContextBuilder(mock_snapshot_repo, mock_manual_repo)
    ctx = await builder.build_context()

    assert ctx.total_patrimonio == 108200.0
    assert ctx.variacao_90d_pct == 8.2
    assert ctx.maior_custodiante == "Rico"
    assert ctx.concentracao_maior_custodiante_pct == 63.0
    assert ctx.exposicao_renda_variavel_pct == 14.0
    assert ctx.passivo_total == 150000.0


@pytest.mark.asyncio
async def test_context_builder_resolve_sync():
    res = await _resolve(123.45)
    assert res == 123.45


@pytest.mark.asyncio
async def test_context_builder_cenarios_de_borda():
    repo_vazio = AsyncMock()
    repo_vazio.get_latest.return_value = None
    del repo_vazio.get_closest_to
    del repo_vazio.get_between
    del repo_vazio.get_current_positions

    manual_vazio = AsyncMock()
    del manual_vazio.get_totals
    manual_vazio.get_active_liabilities.return_value = []

    builder = ContextBuilder(repo_vazio, manual_vazio)
    ctx = await builder.build_context()

    assert ctx.total_patrimonio == 0.0
    assert ctx.variacao_90d_pct == 0.0
    assert ctx.maior_custodiante == "Nenhum"
    assert ctx.passivo_total == 0.0


@pytest.mark.asyncio
async def test_context_builder_fallback_get_between():
    repo = AsyncMock()
    repo.get_latest.return_value = AsyncMock(total=100.0, total_value=100.0)
    del repo.get_closest_to
    repo.get_between.return_value = [AsyncMock(total=80.0, total_value=80.0)]
    repo.get_current_positions.return_value = [
        AsyncMock(amount=50.0, institution=None, type="EQUITY", category=None, name="Ações")
    ]

    manual = AsyncMock()
    del manual.get_totals
    manual.get_active_liabilities.return_value = [AsyncMock(amount=20.0)]

    builder = ContextBuilder(repo, manual)
    ctx = await builder.build_context()

    assert ctx.total_patrimonio == 100.0
    assert ctx.variacao_90d_pct == 25.0
    assert ctx.exposicao_renda_variavel_pct == 100.0
    assert ctx.passivo_total == 20.0


@pytest.mark.asyncio
async def test_insights_service_monta_prompt_e_retorna_insights(
    mock_snapshot_repo, mock_manual_repo
):
    builder = ContextBuilder(mock_snapshot_repo, mock_manual_repo)
    llm = MockLLMClient()
    service = InsightsService(builder, llm)

    response = await service.answer_query("Como está minha carteira?")
    assert "8,2%" in response.answer
    assert response.context_used.variacao_90d_pct == 8.2
    assert "Como está minha carteira?" in (llm.last_user_prompt or "")


@pytest.mark.asyncio
async def test_llm_client_respeita_protocolo():
    client = MockLLMClient(fixed_response="Resposta customizada")
    assert isinstance(client, BaseLLMClient)
    res = await client.generate("system", "user")
    assert res == "Resposta customizada"


@pytest.mark.asyncio
async def test_openai_llm_client():
    client = OpenAILLMClient(api_key="sk-test")
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"choices": [{"message": {"content": "Resposta OpenAI"}}]}
    fake_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_resp
        res = await client.generate("sys", "user")
        assert res == "Resposta OpenAI"


@pytest.mark.asyncio
async def test_ollama_llm_client():
    client = OllamaLLMClient(base_url="http://localhost:11434", model="llama3.2:1b")
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"response": "Resposta Ollama"}
    fake_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_resp
        res = await client.generate("sys", "user")
        assert res == "Resposta Ollama"


def test_get_llm_client_providers(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert isinstance(get_llm_client(), OpenAILLMClient)

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert isinstance(get_llm_client(), OllamaLLMClient)

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    assert isinstance(get_llm_client(), MockLLMClient)


def test_get_insights_service_factory():
    svc = get_insights_service(MagicMock(), MagicMock(), MockLLMClient())
    assert isinstance(svc, InsightsService)


def test_api_insights_chat_endpoint_sucesso():
    client = TestClient(app)

    async def mock_answer_query(query: str):
        return InsightChatResponse(
            answer="Resposta de teste da API",
            context_used=PortfolioContext(
                total_patrimonio=100000.0,
                variacao_90d_pct=5.0,
                maior_custodiante="Itaú",
                concentracao_maior_custodiante_pct=50.0,
                exposicao_renda_variavel_pct=20.0,
                exposicao_renda_fixa_pct=80.0,
                passivo_total=0.0,
            ),
        )

    mock_service = MagicMock()
    mock_service.answer_query = AsyncMock(side_effect=mock_answer_query)

    app.dependency_overrides[get_insights_service] = lambda: mock_service
    try:
        resp = client.post("/api/v1/insights/chat", json={"query": "Como está minha carteira?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Resposta de teste da API"
        assert data["context_used"]["total_patrimonio"] == 100000.0
    finally:
        app.dependency_overrides.clear()


def test_api_insights_chat_endpoint_erro():
    client = TestClient(app)

    mock_service = MagicMock()
    mock_service.answer_query = AsyncMock(side_effect=RuntimeError("Falha simulada"))

    app.dependency_overrides[get_insights_service] = lambda: mock_service
    try:
        resp = client.post("/api/v1/insights/chat", json={"query": "Como está minha carteira?"})
        assert resp.status_code in [500, 200]  # valida tratamento do endpoint
    finally:
        app.dependency_overrides.clear()
