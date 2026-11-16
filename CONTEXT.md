# Contexto vigente — open-wealth

> Referência operacional do projeto, atualizada em 2026-11-16.
> O histórico cronológico está em [docs/CONTEXT-HISTORY.md](docs/CONTEXT-HISTORY.md).
> Use este arquivo para entender o estado atual; o histórico pode conter
> planos e descrições que já foram superados.

## Em uma frase

Open Wealth sincroniza contas e investimentos de um item Pluggy, persiste
snapshots diários e oferece uma API FastAPI e um dashboard Streamlit para
consultar patrimônio e evolução.

## Estado atual

- Sync real com Pluggy e persistência de snapshots estão implementados.
- O sync é idempotente por data e instituição: se já existe snapshot daquele
  dia, uma nova execução não duplica os dados.
- A cascata de valoração de investimentos é
  `balance → quantity * price → amount → 0`.
- O dashboard inclui todas as categorias por padrão. Visões que precisarem
  excluir categorias devem passar `exclude_categories` explicitamente a
  `prepare_snapshot_data`.
- A camada de domínio canônica é `app.domain.models`. O módulo
  `app.models.snapshot` é apenas um re-export de compatibilidade.
- O banco é selecionado por `DATABASE_URL`: SQLite para desenvolvimento local
  ou PostgreSQL quando configurado. Não execute limpezas ou seeds no banco
  configurado sem confirmar o alvo.

## Arquitetura e pontos de entrada

| Área | Responsabilidade |
|---|---|
| `app/integrations/pluggy_client.py` | Autenticação e chamadas à API Pluggy. |
| `app/domain/models.py` | Modelos canônicos `Position` e `Snapshot`. |
| `app/domain/valuation.py` | Regra compartilhada de valoração de investimentos. |
| `app/services/consolidacao.py` | Mapeamento de categorias e montagem das posições. |
| `app/services/sync.py` | Orquestra a leitura da Pluggy e a gravação do snapshot diário. |
| `app/services/historico.py` | Séries de evolução e crescimento acumulado. |
| `app/repositories/snapshot_repository.py` | Schema, migrações e persistência de snapshots. |
| `app/api/routes.py` | Endpoints de sync, carteira e histórico sob `/api/v1`. |
| `dashboard/data.py` | Agregações compartilhadas do dashboard. |
| `dashboard/Home.py` | Página inicial Streamlit; páginas adicionais ficam em `dashboard/pages/`. |

Fluxo de sync:

```text
PluggyClient → sync_weekly → SnapshotRepository → snapshots/accounts/investments
```

`sync_weekly` grava saldos das contas e investimentos no snapshot. Os
investimentos também são persistidos em `investments.value` usando a mesma
cascata de valoração. O snapshot inclui valores de cartões, que podem ser
negativos por representarem dívida.

## Regras para interpretar os dados

- O dashboard lê todas as categorias, inclusive `banco` e `cartao`, salvo
  quando o chamador passa uma exclusão explícita.
- O total bruto pode incluir saldo bancário, investimentos e dívida de cartão.
- Parte do histórico anterior a 2026-11-13 é sintética. Os valores dos
  investimentos em 2026-11-13, 14 e 15 foram copiados do snapshot de
  2026-11-16 por aproximação; não são cotações históricas confirmadas pela
  Pluggy.
- A API Pluggy em modo Development opera com o item configurado por
  `PLUGGY_ITEM_ID`; não dependa da listagem geral de itens.

## API e execução local

Rotas principais:

- `POST /api/v1/sync`
- `GET /api/v1/historico/evolucao`
- `GET /api/v1/historico/acumulado`
- `GET /api/v1/carteira`
- `GET /api/v1/carteira/posicoes`
- `GET /api/v1/carteira/instituicoes`
- `GET /api/v1/carteira/alocacao`

Comandos usuais, a partir da raiz:

```bash
./.venv/bin/pytest -q
./.venv/bin/uvicorn main:app --reload
./.venv/bin/streamlit run dashboard/Home.py
```

Credenciais e configuração local ficam no `.env` e não devem ser incluídas
em documentação, logs compartilhados ou commits.

## Critérios para atualizar este contexto

1. Mantenha aqui apenas arquitetura, regras e limitações ainda vigentes.
2. Registre decisões e mudanças superadas em
   [docs/CONTEXT-HISTORY.md](docs/CONTEXT-HISTORY.md), em ordem cronológica.
3. Remova pendências daqui quando forem concluídas; não replique um backlog
   antigo como se ainda estivesse aberto.
4. Ao documentar comportamento, confirme no código e nos testes atuais.
