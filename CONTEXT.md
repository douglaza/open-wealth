# CONTEXT.md — open-wealth

Histórico e contexto do desenvolvimento do projeto até o primeiro commit.
Serve como memória de decisões, problemas encontrados e soluções adotadas.

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
│   │   ├── database.py # setup do banco (SQLite em data/database.db)
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
│   ├── test_consolidacao.py # 2 testes (sync_all + get_totals, mocks)
│   ├── test_pluggy.py # 6 testes do PluggyClient
│   ├── test_rentabilidade.py # 1 teste
│   └── test_scheduler.py # 1 teste (job "sync_weekly" registrado)
├── data/
│   ├── database.db
│   └── exports/
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
- Atenção: no modo Development há apenas 1 item fixo (o do .env) —
  sync_all precisará de ajuste para operar sobre o item único sem depender
  de get_items() (ver 7. Próximos passos).
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
  método inexistente que só estouraria em runtime.

### 4.8. Investimentos com value null e amount divergente (bug silencioso)

**Problema:** a primeira execução E2E mostrava CDR e ISUS11 STOCK com
R0,00enquantoodashboarddaPluggyexibiaR0,00 enquanto o dashboard da Pluggy exibia R0,00enquantoodashboarddaPluggyexibiaR 2.000,00 cada.
Investigação direta na API revelou que o problema era maior do que
parecia: 6 de 8 investimentos do sandbox vinham com value: null, e o
patrimônio real estava subestimado em R$ 19.185,59 desde sempre
(total real: R63.371,23,na~oR63.371,23, não R63.371,23,na~oR 44.185,64).

**Armadilha adicional:** amount NÃO é fallback seguro para balance.
No CDR do sandbox: amount=2500 mas balance=2000 (que é o valor exibido
no dashboard). Usar amount geraria posição inflada.

**Solução:** consolidacao.py passou a usar SEMPRE balance como valor
da posição de investimento. Fallback em cascata apenas se balance
ausente: value → quantity × price → 0.0. Extraído
_investment_amount() centralizando a regra, com docstring explicando
o porquê.

**Lição:** não confiar em nenhum campo único da API como
"sempre preenchido" — validar contra o dashboard oficial cedo.
Campos com mesmo nome têm semântica diferente por type de
investimento.

### 4.9.Instituição null em investimentos

**Problema:** ISUS11 STOCK vem com institution: null (o CDR traz
"Discussão BTG PACTUAL S/A").

**Solução:** fallback para o nome do item quando institution ausente.

#### 4.10 — Regressão de posições de investimento (2025-XX-XX)

### Problema

API de investments da Pluggy retorna campos inconsistentes por produto:

- `value: null` com `balance` preenchido (ETF ISUS11)
- `amount` divergente de `balance` (CDB: amount=2500, balance=2000 — dashboard exibe 2000)

### Decisão de contrato

Fonte de verdade do valor da posição é `balance`, nesta cascata:
`balance` → `value` → `0.0`
`amount` NUNCA é usado (pode divergir do que o banco exibe).

### Verificação

- `sync_all` já cumpria o contrato; bug não se materializou no nosso código.
- Adicionados 4 testes de regressão em `tests/test_consolidacao.py`
  (`TestValorPosicaoInvestimento`) para travar a cascata e a agregação
  pós-cascata. Suite: 17 passed.
- Se alguém reordenar a cascata, o CI acusa.

### Campos do modelo `Position` (dataclass, não pydantic)

`institution, account_type, asset_name, category, amount, updated_at`
⚠️ Nome do ativo é `asset_name`, não `name`.

### Lições aplicadas/reforçadas

- 4.6: `cat` após colar pegou bloco que não tinha sido salvo na 1ª tentativa ✅
- 4.7: introspecção (`__dataclass_fields__`) revelou o campo real em vez de adivinhar ✅
- Testes escritos ANTES de verificar o código: como passaram de primeira,
  confirmamos o contrato em vez de "corrigir" às cegas.

### Próximo passo

Fase 2: [descrever aqui]

## 5. Estado dos testes

10 passed (pytest 9.2.0, Python 3.12.7):

| Arquivo               | Testes | O que cobre                                                                         |
| --------------------- | -----: | ----------------------------------------------------------------------------------- |
| test_consolidacao.py  |      2 | sync_all monta Snapshot; get_totals agrega por instituição                        |
| test_pluggy.py        |      6 | get_item, listas de accounts/investments/transactions, erro de API, token no header |
| test_rentabilidade.py |      1 | cálculo de rentabilidade total                                                     |
| test_scheduler.py     |      1 | job "sync_weekly" registrado                                                        |

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
