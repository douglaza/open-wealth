from pydantic import BaseModel, Field


class PortfolioContext(BaseModel):
    """Métricas determinísticas calculadas em Python para alimentar o modelo."""

    total_patrimonio: float
    variacao_90d_pct: float
    maior_custodiante: str
    concentracao_maior_custodiante_pct: float
    exposicao_renda_variavel_pct: float
    exposicao_renda_fixa_pct: float
    passivo_total: float = 0.0


class InsightChatRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="Pergunta do usuário")


class InsightChatResponse(BaseModel):
    answer: str
    context_used: PortfolioContext
