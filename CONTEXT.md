# CONTEXT.md — open-wealth

Histórico e contexto do desenvolvimento do projeto até o primeiro commit.
Serve como memória de decisões, problemas encontrados e soluções adotadas.

> Estado: Fase 4 concluída (Docker/Postgres, scheduler diário, endpoints de
> leitura, views SQL). Próxima: Fase 5 — Analytics.
> Última atualização: 2026-11-13.

---

## 1. Visão do projeto

**open-wealth** é um agregador de patrimônio pessoal que:

1. Conecta-se à API da [Pluggy.ai](https://pluggy.ai) (open finance) para
   sincronizar contas bancárias e investimentos de múltiplas instituições.
2. Consolida tudo em um `Snapshot` diário de posições (`Position`).
3. Calcula rentabilidade e totais (por instituição e geral).
4. Agenda sincronização semanal via scheduler.
5. Exibe dashboard em Streamlit.

## 2. Estrutura atual

```text
open-wealth/
├── app/
│   ├── core/
│   │   ├── config.py # configurações (env vars, credenciais Pluggy, item_id)
│   │   ├── database.py # setup do banco (dual: SQLite local / Postgres em Docker)
│   │   └── scheduler.py # agendador; registra job "sync_weekly"
│   ├── models/
│   │   ├── account.py
│   │   ├── investment.py
│   │   └── snapshot.py # Snapshot (data + positions + total) e Position
│   ├── repositories/
│   │   ├── account_repository.py
│   │   ├── investment_repository.py
│   │   └── snapshot_repository.py
│   └── services/
│       ├── pluggy_client.py # cliente HTTP da API Pluggy
│       ├── consolidacao.py # sync_all: monta Snapshot; get_totals: agregações
│       ├── rentabilidade.py # cálculo de retorno
│       └── sync.py
├── dashboard/
│   ├── Home.py # entrada do Streamlit (streamlit run dashboard/Home.py)
│   └── pages/
│       ├── evolucao.py
│       ├── investimentos.py
│       └── patrimonio.py
├── tests/
│   ├── test_consolidacao.py # sync_all + get_totals + regressões de valor
│   ├── test_pluggy.py # testes do PluggyClient (v2 transactions)
│   ├── test_rentabilidade.py
│   ├── test_scheduler.py
│   └── test_sync_repository.py # integração sync_weekly + SnapshotRepository
├── data/
│   ├── database.db
│   └── exports/
├── docker-compose.yml # serviço db (postgres:16-alpine)
├── main.py
├── conftest.py
├── .env # PLUGGY_CLIENT_ID/SECRET + PLUGGY_ITEM_ID
└── requirements.txt
```

## 3. Módulos principais

### `app/core/config.py`

Settings (pydantic-settings, lê .env): pluggy_client_id,
pluggy_client_secret, pluggy_base_url (default https://api.pluggy.ai)
e pluggy_item_id (usado no modo Development; ver 4.6).

### `app/core/database.py`

Modo dual via DATABASE_URL: SQLite local ou Postgres (Docker). Dois
schemas equivalentes (SCHEMA_SQLITE / SCHEMA_PG); PG usa NUMERIC(20,4).

### `app/services/pluggy_client.py`

- Autenticação via POST /auth com clientId/clientSecret; token válido
  ~2h (renovado 60s antes da expiração).
- Token enviado no header X-API-KEY em todas as chamadas.
- _get() centraliza GET com requests, timeout 30s e raise_for_status().
- _extract_results() aceita tanto {"results": [...]} quanto lista direta —
  a API mudou de formato entre versões/docs, então o cliente é tolerante.
- Endpoints:
  - get_item(item_id=None) — usa item_id arg ou settings.pluggy_item_id.
  - get_accounts(item_id=None), get_investments(item_id=None) — mesmo
    padrão de fallback para o item do .env.
  - get_transactions(account_id, cursor=None) — API v2
    (GET /v2/transactions), paginação por cursor, SEM pageSize (a v2
    rejeita o parâmetro com 400 "property pageSize should not exist").
  - get_all_transactions(account_id) — itera hasNext/nextCursor até
    esgotar e retorna lista plana.
  - get_items() — comentada/desabilitada: dá 401 no modo Development
    (ver 4.6). Reativar quando migrar para produção.

### `app/services/consolidacao.py`

- sync_all(client) → itera items, e para cada item cria Position a partir
  de contas (balance) e investimentos (value); instituição vem de
  item["connector"]["name"] com fallback "Desconhecido".
- No modo Development opera sobre o item único do .env (ver 4.7).
- get_totals(snapshot) → total geral + agregação por instituição.

## 4. Problemas, desafios e soluções

### 4.1. Refatoração: pastas órfãs e imports quebrados

**Problema:** durante a evolução, módulos foram movidos/renomeados e restou código
referenciando caminhos antigos:

- app.services.consolidacao importava app.integrations.pluggy
  (accounts/investments), que não existia mais.
- app/jobs, app/integrations, app/dashboard, app/api e
  run_dashboard.py ficaram órfãos.

**Solução:** remoção deliberada das pastas antigas
(rm -rf app/jobs app/integrations app/dashboard app/api run_dashboard.py) e
centralização:

- dashboard movido para dashboard/ na raiz (executado via
  .venv/bin/streamlit run dashboard/Home.py);
- consolidacao.py passou a consumir diretamente os métodos do
  PluggyClient (get_items, get_accounts, get_investments) em vez de
  módulos intermediários de integração.

**Lição:** mover módulo = atualizar imports + apagar caches (__pycache__,
.pytest_cache), senão o Python continua carregando bytecode velho e os erros
se mantêm misteriosamente.

### 4.2. Scheduler: job não registrado no teste

**Problema:** test_sync_weekly_runs fazia scheduler.get_job("sync_weekly")
e recebia None (assert None is not None). O job só é registrado quando
start_scheduler() é chamado — e nada o chamava no teste.

**Solução:** o teste agora inicializa e desliga o scheduler explicitamente:

```python
def test_sync_weekly_runs():
    from app.core import scheduler as sched
    sched.start_scheduler()
    try:
        job = sched.scheduler.get_job("sync_weekly")
        assert job is not None
    finally:
        sched.stop_scheduler()
```

**Lição:** garantir que o scheduler NÃO inicie automaticamente na importação do
módulo; exportar apenas funções (start_scheduler, stop_scheduler).

### 4.3. Bug de lógica em consolidacao.py

**Problema:** na refatoração, uma linha ficou como
positions=date.today() and positions — funciona "por acidente" (retorna
positions quando a data é truthy), mas é semântica errada e frágil. Também havia
import morto de app.integrations.pluggy e uso de client.get("items")["results"]
com caminhos manuais.

**Solução:** reescrita limpa de sync_all usando os métodos do cliente, import de
date movido para o topo, e client.get_items() direto (que já retorna lista
plana via _extract_results).

### 4.4. Teste de consolidacao não coletado (collected 0 items)

**Problema:** pytest tests/test_consolidacao.py rodou com 0 testes — o arquivo
estava vazio/quase vazio (resto da refatoração).

**Solução:** reescrita do arquivo com testes usando unittest.mock.MagicMock para
simular o PluggyClient (items/accounts/investments com dados fixos) e verificar
snapshot montado e agregação por instituição.

**Lição:** após refatorações grandes, rodar pytest --collect-only para detectar
arquivos que perderam os testes silenciosamente.

### 4.5. Cache de bytecode de versões antigas do pytest

**Problema:** __pycache__ com artefatos do pytest 8.3.2 junto com 9.2.0, risco de
comportamento estranho/estaleiro.

**Solução:** rm -rf tests/__pycache__ .pytest_cache e rerun.

### 4.6. API Pluggy real: modo Development e migração para a v2

**Contexto:** após a primeira bateria de testes unitários (com mocks), a
integração foi testada contra a API real do Pluggy em modo Development
(chaves sandbox). Vários comportamentos divergiram da documentação:

GET /items retorna 401 Unauthorized no modo Development. A listagem
de items é privilégio de contas de produção. No Development só é possível
acessar o item criado via sandbox, conhecendo seu ID.

**Solução:** o ID do item sandbox foi fixado no .env
(PLUGGY_ITEM_ID=c9f56a01-...) e exposto em config.py como
pluggy_item_id. Os métodos get_item, get_accounts e
get_investments aceitam item_id=None e fazem fallback para esse valor.
get_items() foi comentada no cliente, com nota para reativar em produção.

GET /transactions deprecada (HTTP 410) com mensagem apontando para
GET /v2/transactions com paginação por cursor.

**Solução:** migração completa no cliente:

get_transactions(account_id, cursor=None) → GET /v2/transactions;
resposta da v2: {"results": [...], "hasNext": bool, "nextCursor": str};
get_all_transactions(account_id) percorre as páginas via cursor e
devolve lista plana (o resto do app continua consumindo lista).
pageSize rejeitado na v2 (HTTP 400, "property pageSize should not
exist"). A v2 valida estritamente os query params e não aceita o
pageSize que funcionava na v1.

**Solução:** parâmetro removido; a v2 pagina por cursor sem limite
explícito. Se um dia for preciso limitar, testar limit — mas a lição é:
a v2 é rigorosa com query params desconhecidos.

Colagem incorreta durante a edição do cliente: código sugerido foi
colado dentro do corpo da classe com método inexistente (self._request)
e ITEM_ID = settings.pluggy_item_id como atributo de classe (avaliado
na importação, acoplado ao settings). Detectado ao revisar o cat do
arquivo antes de rodar.

**Solução:** reescrita coerente do cliente: item_id vira parâmetro do
__init__ (com fallback para settings), métodos usam self._get real,
e get_items antigo mantido apenas comentado.

Validação ponta a ponta (sandbox):

```text
get_item() → status UPDATED
Conta Corrente   43701.43   (boleto, salário, condomínio...)
Mastercard Black -1006.20   (SMART FIT, SPOTIFY, NETFLIX...)
```

### 4.7. sync_all adaptado ao modo Development

**Problema:** sync_all dependia de get_items() → 401 no modo Development.

**Solução:** sync_all agora usa get_item() (item único do .env) e propaga
item_id para get_accounts/get_investments. Extraído _build_positions()
com fallbacks (balance/value ausentes → 0.0, listas None tratadas).
Validado ponta a ponta no sandbox: Snapshot com 2 posições,
total R$ 42.695,23. Em produção, bastará reativar get_items() no cliente.

#### Lições

- Modo Development ≠ produção: nem todos os endpoints estão disponíveis
  (listagem de items é 401); desenhar o cliente para aceitar item fixo.
- Endpoints mudam: a API responde 410 com instrução explícita de migração —
  ler a mensagem do erro economiza tempo (foi ela que apontou a v2).
- Validar query params: um parâmetro "inofensivo" (pageSize) quebra a v2
  com 400; testar contra a API real cedo, não só contra mocks.
- Sempre cat no arquivo depois de colar código — colagem desalinhada gerou
método inexistente; revisar sempre após colar.

### 4.8. Migração de esquema incremental no SQLite

**Problema:** tabela snapshots antiga sem colunas novas (ex.: category).
INSERT falhava silenciosamente ou com erro de coluna.

**Solução:** SnapshotRepository cria o schema com CREATE TABLE IF NOT
EXISTS e verifica colunas existentes (PRAGMA table_info / information_schema)
para migrar incrementalmente (ALTER TABLE ADD COLUMN quando faltar).

**Lição:** schema autoconstruído no construtor do repositório evita a classe
de bugs "funciona no teste, quebra no banco real".

### 4.9. Dedup diária do repositório

**Problema:** rodar o sync duas vezes no mesmo dia duplicava snapshots,
inflando o histórico e distorcendo a série temporal.

**Solução:** dedup por snapshot_date no repositório: snapshot existente é
pulado sem nova chamada à API (evento snapshot_skipped no log). Testado
contra SQLite real (tmp_path), não apenas mock.

**Lição:** garantias de idempotência devem viver na camada de persistência,
não no chamador — assim endpoint, scheduler e testes herdam a garantia.

### 4.10. Resposta 202 sem distinção synced/skipped

**Problema:** POST /api/v1/sync responde 202 tanto quando gravou quanto
quando pulou; impossível distinguir pelo cliente.

**Solução planejada (Fase 3→4):** corpo da resposta com
{"status": "synced"|"skipped", ...}.

## 5. Estado dos testes

10 passed (pytest 9.2.0, Python 3.12.7):

| Arquivo               | Testes | O que cobre                                                                          |
|-----------------------|-------:|--------------------------------------------------------------------------------------|
| test_consolidacao.py  |      2 | sync_all monta Snapshot; get_totals agrega por instituição                           |
| test_pluggy.py        |      6 | get_item, listas de accounts/investments/transactions, erro de API, token no header |
| test_rentabilidade.py |      1 | cálculo de rentabilidade total                                                      |
| test_scheduler.py     |      1 | job "sync_weekly" registrado                                                         |

Mocks: MagicMock (client fake) e pytest-mock instalado.

Pendente: test_pluggy.py ainda testa o formato antigo (v1) de
transações; precisa ser atualizado para a v2 (cursor/hasNext) — ver seção 7.

## 6. Ambiente

- Python 3.12.7 (venv em .venv/), Linux (VMware VM)
- pytest 9.2.0, pytest-mock 3.17.0, pluggy 1.7.0 (pacote python; sem relação
  com a API Pluggy.ai — homônimo)
- Streamlit servindo em http://localhost:8502
- Banco: SQLite em data/database.db
- Credenciais Pluggy em .env (modo Development/sandbox), item fixo em
  PLUGGY_ITEM_ID

## 7. Próximos passos planejados

- Atualizar test_pluggy.py para a v2: mockar respostas com
  {"results": [...], "hasNext", "nextCursor"} e testar a paginação de
  get_all_transactions (múltiplas páginas, última sem hasNext).
- Ajustar sync_all para o modo Development: operar sobre o item único
  (get_item + fallback do settings) sem depender de get_items(),
  mantendo compatibilidade com produção quando ela for reativada.
- Fixture JSON realista da Pluggy (sandbox) em tests/fixtures/ para validar
  mapeamento de campos reais (connector.name, type, value, e os campos
  de transação da v2: description, amount, date).
- Edge cases de consolidacao: item sem connector, balance/value ausentes → 0.0,
  item só com contas ou só com investimentos.
- ~~Persistência: ligar sync_all ao snapshot_repository e testar ciclo salvar → ler
  (usando :memory: ou tmp_path, nunca o banco de produção).~~
- Teste de fumaça do dashboard: importar dashboard.Home num teste para pegar erros
  de import antes de abrir o navegador.
- Cobertura: pytest-cov com --cov=app --cov-report=term-missing.
- Método refresh_item() no cliente (POST /items/{id}/refresh) para
  forçar atualização dos dados sandbox sob demanda.
- Normalização de transações (conta corrente vs cartão) em modelo Pydantic
  interno, para o resto do app não depender do formato bruto da API.
- Em produção: descomentar get_items(), remover dependência do item fixo,
  e revisar limites de paginação (limit?) na v2.

### 7.1 — pendências

- Integrar run_scheduled_sync ao snapshot_repository (persistir cada
  execução).
- Testes de regressão do bug de valor (ainda não criados):
  test_investment_value_null_usa_balance e
  test_investment_nao_usa_amount_quando_diverge_de_balance.
- Decisões de produto em aberto: múltiplos items (feature flag?),
  posições zeradas contam no total?, liabilities (cartões) separadas
  do patrimônio.
- Rentabilidade: campos rate/rateType/fixedAnnualRate (ex.: 150% CDI2,5% p.a.) e lastMonthRate/lastTwelveMonthsRate vêm de graça no
  payload da Pluggy — usar antes de calcular de séries históricas.
- Com snapshots diários + balance confiável, séries históricas reais
  ficam viáveis para evolucao.py.

## 8. Convenções adotadas

- Testes com pytest, mocks via MagicMock/pytest-mock.
- Cliente Pluggy tolerante a dois formatos de resposta (lista ou results).
- Sem state global em módulos com side effects (scheduler inicia só via função
  explícita).
- Sempre limpar pycache/.pytest_cache após mover módulos.
- Métodos do cliente aceitam item_id opcional com fallback para
  settings.pluggy_item_id — facilita o modo Development sem quebrar a
  assinatura para produção.
- Ler a mensagem de erro da API (410/400 com instruções) antes de sair
  procurando em fóruns — o próprio erro costuma indicar o caminho.
- cat no arquivo após colar código sugerido: detectar colagens desalinhadas
  antes de rodar.
- Valor de posição de investimento: sempre balance; nunca amount
  (diverge no sandbox); value só como último recurso.
- Atualizar CONTEXT.md é critério de done de cada fase, não tarefa
  opcional.
- Seção de "armadilhas conhecidas da API" é a mais valiosa do arquivo:
  registrar todo comportamento não-documentado descoberto.


## 9. Fase 2 — API (FastAPI) e persistência de snapshots

### 9.1. Arquitetura da camada API

```text
app/api/
├── main.py        # FastAPI app, router include, lifespan opcional
└── routers/       # endpoints /api/v1/sync, snapshot, etc.
```

Banco: data/database.db (SQLite), schema criado automaticamente.

Fluxo do sync: POST /api/v1/sync → sync_weekly(client, repo) →
Pluggy → posições → SnapshotRepository.upsert_snapshot → 202 Accepted.

Log estruturado em JSON (time/level/module/event) com eventos:
sync_started, sync_data_fetched, snapshot_saved, snapshot_skipped.

### 9.2. Repositório de snapshots

upsert_snapshot(snapshot, snapshot_date):

- snapshot_exists(date) → se já há snapshot do dia, pula (idempotência).
- Persiste posições em tabela snapshots com asset_name, category,
  amount, e metadados de contas em accounts.
- commit() explícito ao final; rollback recomendado em falhas parciais
  (ver 9.4 — pendência).
- _ensure_schema() chamado no __init__ do repositório: cria tabelas
  se não existirem (DDL idempotente), além de _migrate_schema() para
  evoluções incrementais.

### 9.3. Idempotência do sync — validada

Segunda chamada ao POST /api/v1/sync no mesmo dia loga
snapshot_skipped e retorna 202 sem tocar na API Pluggy.

202 em ambos os casos (synced ou skipped) — se precisar distinguir na
resposta, fazer o endpoint retornar {"status": "synced"|"skipped", ...}.

⚠️ Apagar data/database.db enquanto o uvicorn --reload está rodando
funciona (SQLite recria na próxima conexão), mas o processo antigo pode
segurar conexões — preferir reiniciar o server após rm.

### 9.4. Pendências conhecidas (da Fase 2)

- Transação atômica no sync: se falhar no meio do loop de inserts,
  não há rollback garantido — envolver com try/except +
  self._conn.rollback() no repositório.
- Type hint inconsistente: upsert_snapshot(snapshot_date: date) repassa
  direto para upsert_item que espera str — padronizar com .isoformat().
- Divergência histórica de totais (R
  42.695
  ,
  23
  v
  s
  R
  42.695,23vsR 32.695,23) era
  resíduo do banco antigo antes do reset — resolvido, mas reforça: sempre
  validar soma de snapshots contra posições após reset do banco.

### 9.5 Sync atômico (Fase 4)

O loop de inserts do repositório roda dentro de uma transação única;
falha em qualquer posição faz rollback do snapshot inteiro — nunca fica
parcialmente escrito.

### 9.6 Scheduler sobre o item configurado (Fase 4)

O job diário reutiliza PLUGGY_ITEM_ID em vez de get_items() (que retorna
401 no modo Development). Mesma decisão da Fase 2 (4.7), agora aplicada
ao agendamento.

### 9.7 Views como contrato de agregação (Fase 4)

Agregações (classe, instituição) vivem em views SQL, não em Python.
Mudança de regra de agrupamento = mudança no SQL, sem tocar código.

### 9.8 Dual backend de banco (Fase 4)

DATABASE_URL decide SQLite vs Postgres; schemas equivalentes
(SCHEMA_SQLITE / SCHEMA_PG). NUMERIC(20,4) no PG retorna Decimal —
código de comparação não pode assumir float.

### 9.9 Docker como limite de recriação (Fase 4)

Recriar o banco em Docker exige docker compose down -v (destruir o
volume); equivale ao "apagar database.db + reiniciar servidor" do SQLite.

## 10. Registro da Fase 4

### 10.1 Dockerização — SQLite → Postgres

- docker-compose.yml com serviço db (postgres:16-alpine, porta host 5433,
  healthcheck, volume persistente). Container: open-wealth-db.
- app/core/database.py em modo dual (ver 9.8). Efeito colateral corrigido:
  comparações com == 0.0 quebravam silenciosamente com Decimal.
- Lição: docker compose down -v para destruir o volume ao recriar o banco.

### 10.2 Scheduler diário

- Segundas-feiras 06:00, America/Sao_Paulo, reutilizando PLUGGY_ITEM_ID.
- Dedup diária no repositório: reinício do container não infla o histórico.
- Efeito estratégico: a coleta automática constrói a série temporal que
  alimenta os indicadores da Fase 5.

### 10.3 Views SQL

- v_alocacao_classe e v_alocacao_instituicao: agregação (% por category /
  institution), agrupada por snapshot_date. Endpoint faz apenas
  SELECT * FROM view — a view é o contrato.

### 10.4 API de leitura

- 10 endpoints em app/api/routes.py, incluindo:
  - GET /carteira → snapshot_date + total (patrimônio consolidado).
  - GET /carteira/alocacao → alocação por classe (view).
  - GET /carteira/instituicoes → alocação por instituição (view).
  - GET /historico/evolucao → série temporal do patrimônio.

### 10.5 Validação ponta a ponta (dados reais)

- Sync Pluggy → Postgres consolidado em R$ 42.695,23 no snapshot de
  2026-11-13, consistente entre tabela snapshots, views e API.
- Verificação: docker exec -it open-wealth-db psql -U openwealth -d
  openwealth -c "SELECT snapshot_date, COUNT(*), SUM(amount) FROM
  snapshots GROUP BY snapshot_date ORDER BY snapshot_date;"