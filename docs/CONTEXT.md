# Contexto vigente — open-wealth

> Referência operacional consolidada do projeto.
> Atualizada em 2026-11-18.

## Em uma frase

Open Wealth sincroniza contas e investimentos de um item Pluggy, persiste
snapshots patrimoniais diários e oferece API FastAPI e dashboard Streamlit
para consulta, evolução e análise por IA.

## Estado atual

- Sync real com Pluggy e persistência de snapshots estão implementados.
- SQLite é usado localmente e PostgreSQL em Docker pode ser selecionado por
  `DATABASE_URL`.
- O sync é idempotente por data e instituição. Uma nova execução no mesmo dia
  não duplica dados nem toca novamente na API Pluggy.
- O cliente opera pelo `PLUGGY_ITEM_ID` no modo Development; a listagem geral
  de itens pode retornar 401 nesse modo.
- A cascata de valoração de investimentos é
  `balance → quantity * price → amount → 0`.
- O banco cria e migra seu schema incrementalmente na inicialização dos
  repositórios.
- O dashboard lê todas as categorias por padrão. Exclusões devem ser passadas
  explicitamente por `exclude_categories` a `prepare_snapshot_data`.
- Observabilidade em tempo real integrada com Prometheus e Grafana.
- O lifespan do FastAPI inicializa o banco e atualiza as métricas no startup.
- Assistente patrimonial integrado via LLM (Fase 9), com `PortfolioContext`
  calculado deterministicamente em Python antes da consulta ao modelo.
- Provedores suportados pelo protocolo `BaseLLMClient`: `Ollama` com Llama 3.2,
  `OpenAI` com GPT-4o-mini e `MockLLMClient`.
- `POST /api/v1/insights/chat` disponível, com contadores e latência no
  Prometheus.
- Chat do Streamlit disponível em `dashboard/pages/insights.py`.
- 221 testes automatizados, com cobertura exigida de 100% em `app/`.

## Arquitetura e pontos de entrada

| Área | Responsabilidade |
|---|---|
| `app/core/config.py` | Configurações e credenciais por ambiente. |
| `app/core/database.py` | Seleção SQLite/PostgreSQL e inicialização do schema. |
| `app/core/scheduler.py` | Agendamento diário do sync. |
| `app/integrations/pluggy_client.py` | Autenticação e chamadas à API Pluggy. |
| `app/domain/models.py` | Modelos canônicos `Position` e `Snapshot`. |
| `app/domain/insights.py` | `PortfolioContext`, `InsightChatRequest` e `InsightChatResponse`. |
| `app/domain/valuation.py` | Regra compartilhada de valoração de investimentos. |
| `app/integrations/llm_client.py` | `BaseLLMClient` e clientes Ollama, OpenAI e mock. |
| `app/services/consolidacao.py` | Mapeamento de categorias e montagem das posições. |
| `app/services/sync.py` | Orquestra leitura da Pluggy e persistência diária. |
| `app/services/historico.py` | Séries de evolução e crescimento acumulado. |
| `app/services/context_builder.py` | Context Engine de métricas, alocação RV/RF e concentração. |
| `app/services/insights_service.py` | Montagem do prompt executivo e acesso ao LLM. |
| `app/repositories/snapshot_repository.py` | Schema, migrações e persistência de snapshots. |
| `app/api/routes.py` | Endpoints de sync, carteira, histórico e insights. |
| `dashboard/Home.py` | Entrada do Streamlit. |
| `dashboard/pages/insights.py` | Interface interativa de chat. |
| `dashboard/data.py` | Agregações compartilhadas do dashboard. |

Fluxo principal:

```text
PluggyClient → sync_weekly → SnapshotRepository → snapshots/accounts/investments
                                      ↓
ContextBuilder → InsightsService → BaseLLMClient → InsightChatResponse
                                      ↓
                FastAPI e dashboard Streamlit
```

## Regras para interpretar os dados

- Total bruto pode incluir saldo bancário, investimentos e dívida de cartão.
- Valores negativos de cartões representam dívidas.
- O campo `value` da API não substitui a cascata de valoração dos
  investimentos.
- Comparações financeiras no PostgreSQL devem aceitar `Decimal`, não apenas
  `float`.
- Parte do histórico anterior a 2026-11-13 é sintética. Os valores de
  investimentos em 13, 14 e 15 de novembro de 2026 foram aproximados pelo
  snapshot de 16 de novembro e não são cotações Pluggy confirmadas.
- O dashboard deve receber categorias explícitas quando uma visão precisa
  excluí-las.
- Não execute seeds, drops ou limpezas no banco configurado sem confirmar o
  alvo de `DATABASE_URL`.

## API e execução local

Rotas principais:

- `POST /api/v1/sync`
- `POST /api/v1/insights/chat`
- `GET /api/v1/historico/evolucao`
- `GET /api/v1/historico/acumulado`
- `GET /api/v1/carteira`
- `GET /api/v1/carteira/posicoes`
- `GET /api/v1/carteira/instituicoes`
- `GET /api/v1/carteira/alocacao`
- `GET /metrics`

Comandos usuais:

```bash
./.venv/bin/pytest -q
./.venv/bin/uvicorn main:app --reload
./.venv/bin/streamlit run dashboard/Home.py
```

Credenciais ficam no `.env` e não devem ser incluídas em documentação, logs
ou commits.

## Decisões e armadilhas conhecidas

- Idempotência deve viver no `SnapshotRepository`; endpoint, scheduler e
  testes herdam essa garantia.
- Falhas parciais de persistência devem disparar rollback. Inserts do snapshot
  fazem parte de uma única transação.
- O modo Development da Pluggy não oferece `get_items()`. Usar o item fixo
  do ambiente; em produção, avaliar a reativação da listagem.
- A API Pluggy migrada da v1 para a v2 usa transações por cursor. Não enviar
  `pageSize`, rejeitado pela v2; usar `hasNext` e `nextCursor`.
- Ler a mensagem de erro HTTP antes de procurar documentação externa:
  respostas 400 e 410 já indicaram migrações e parâmetros inválidos.
- Schema e migração incremental devem coexistir em SQLite e PostgreSQL.
- Aplicações devem compartilhar a regra de valoração e não recalcular
  investimentos a partir de campos divergentes.
- O LLM recebe contexto e instruções, mas não deve executar cálculos
  patrimoniais. Métricas financeiras são responsabilidade do `ContextBuilder`.
- Nunca iniciar scheduler ou serviços com side effects apenas pela importação
  de um módulo.
- Após refatorações, executar `pytest --collect-only` para detectar arquivos
  de teste que deixaram de ser coletados.
- Atualizar este contexto ao concluir uma fase ou mudança arquitetural.
