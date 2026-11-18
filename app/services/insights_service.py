from app.domain.insights import InsightChatResponse, PortfolioContext
from app.integrations.llm_client import BaseLLMClient
from app.services.context_builder import ContextBuilder

SYSTEM_PROMPT = """Você é o consultor de patrimônio do Open Wealth.
Responda única e exclusivamente ao que o usuário perguntou, em 2 a 3 frases conversacionais.

Regras obrigatórias:
1. Responda apenas à pergunta específica. NUNCA adicione listas de resumo,
bullets de patrimônio ou tópicos não solicitados ao final.
2. Use os dados do contexto apenas se forem relevantes para justificar
a resposta da pergunta.
3. Se a pergunta for um panorama geral (ex: "como está minha carteira?"),
aí sim faça uma visão geral breve.
4. Conclua a resposta imediatamente após responder, sem despedidas ou enrolação."""


class InsightsService:
    def __init__(self, context_builder: ContextBuilder, llm_client: BaseLLMClient):
        self.context_builder = context_builder
        self.llm_client = llm_client

    async def answer_query(self, query: str) -> InsightChatResponse:
        context: PortfolioContext = await self.context_builder.build_context()

        user_prompt = (
            f"Pergunta do usuário: {query}\n\n"
            f"Contexto Financeiro Consolidado (dados oficiais do sistema):\n"
            f"- Patrimônio Líquido Total: R$ {context.total_patrimonio:,.2f}\n"
            f"- Variação nos últimos 90 dias: {context.variacao_90d_pct}%\n"
            f"- Maior Custodiante: {context.maior_custodiante} "
            f"({context.concentracao_maior_custodiante_pct}% do total investido)\n"
            f"- Alocação em Renda Variável: {context.exposicao_renda_variavel_pct}%\n"
            f"- Alocação em Renda Fixa: {context.exposicao_renda_fixa_pct}%\n"
            f"- Passivos / Dívidas (ex: Financiamento Caixa): R$ {context.passivo_total:,.2f}"
        )

        resposta = await self.llm_client.generate(SYSTEM_PROMPT, user_prompt)
        return InsightChatResponse(answer=resposta, context_used=context)
