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
│   │   ├── config.py # configurações (env vars, credenciais Pluggy)
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
└── requirements.txt
```

## 3. Módulos principais

### `app/services/pluggy_client.py`

- Autenticação via `POST /auth` com `clientId`/`clientSecret`; token válido
  ~2h (renovado 60s antes da expiração).
- Token enviado no header `X-API-KEY` em todas as chamadas.
- `_get()` centraliza GET com `requests`, timeout 30s e `raise_for_status()`.
- `_extract_results()` aceita tanto `{"results": [...]}` quanto lista direta —
  a API mudou de formato entre versões/docs, então o cliente é tolerante.
- Endpoints: `get_item`, `get_items` (com paginação), `get_accounts`,
  `get_investments`, `get_transactions`.

### `app/services/consolidacao.py`

- `sync_all(client)` → itera items, e para cada item cria `Position` a partir
  de contas (`balance`) e investimentos (`value`); instituição vem de
  `item["connector"]["name"]` com fallback "Desconhecido".
- `get_totals(snapshot)` → total geral + agregação por instituição.

## 4. Problemas, desafios e soluções

### 4.1. Refatoração: pastas órfãs e imports quebrados

**Problema:** durante a evolução, módulos foram movidos/renomeados e restou código
referenciando caminhos antigos:

- `app.services.consolidacao` importava `app.integrations.pluggy`
  (accounts/investments), que não existia mais.
- `app/jobs`, `app/integrations`, `app/dashboard`, `app/api` e
  `run_dashboard.py` ficaram órfãos.

**Solução:** remoção deliberada das pastas antigas
(`rm -rf app/jobs app/integrations app/dashboard app/api run_dashboard.py`) e
centralização:

- dashboard movido para `dashboard/` na raiz (executado via
  `.venv/bin/streamlit run dashboard/Home.py`);
- `consolidacao.py` passou a consumir diretamente os métodos do
  `PluggyClient` (`get_items`, `get_accounts`, `get_investments`) em vez de
  módulos intermediários de integração.

**Lição:** mover módulo = atualizar imports + apagar caches (`__pycache__`,
`.pytest_cache`), senão o Python continua carregando bytecode velho e os erros
se mantêm misteriosamente.

### 4.2. Scheduler: job não registrado no teste

**Problema:** `test_sync_weekly_runs` fazia `scheduler.get_job("sync_weekly")`
e recebia `None` (`assert None is not None`). O job só é registrado quando
`start_scheduler()` é chamado — e nada o chamava no teste.

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

Lição: garantir que o scheduler NÃO inicie automaticamente na importação do
módulo; exportar apenas funções (start_scheduler, stop_scheduler).

### 4.3. Bug de lógica em consolidacao.py

**Problema:** na refatoração, uma linha ficou como
`positions=date.today() and positions` — funciona "por acidente" (retorna
positions quando a data é truthy), mas é semântica errada e frágil. Também havia
import morto de `app.integrations.pluggy` e uso de `client.get("items")["results"]`
com caminhos manuais.

**Solução:** reescrita limpa de `sync_all` usando os métodos do cliente, import de
`date` movido para o topo, e `client.get_items()` direto (que já retorna lista
plana via `_extract_results`).

### 4.4. Teste de consolidacao não coletado (collected 0 items)

**Problema:** `pytest tests/test_consolidacao.py` rodou com 0 testes — o arquivo
estava vazio/quase vazio (resto da refatoração).

**Solução:** reescrita do arquivo com testes usando `unittest.mock.MagicMock` para
simular o PluggyClient (items/accounts/investments com dados fixos) e verificar
snapshot montado e agregação por instituição.

**Lição:** após refatorações grandes, rodar `pytest --collect-only` para detectar
arquivos que perderam os testes silenciosamente.

### 4.5. Cache de bytecode de versões antigas do pytest

**Problema:** `__pycache__` com artefatos do pytest 8.3.2 junto com 9.2.0, risco de
comportamento estranho/estaleiro.

**Solução:** `rm -rf tests/__pycache__ .pytest_cache` e rerun.

## 5. Estado dos testes

10 passed (pytest 9.2.0, Python 3.12.7):

| Arquivo | Testes | O que cobre |
|---|---:|---|
| test_consolidacao.py | 2 | sync_all monta Snapshot; get_totals agrega por instituição |
| test_pluggy.py | 6 | get_item, listas de accounts/investments/transactions, erro de API, token no header |
| test_rentabilidade.py | 1 | cálculo de rentabilidade total |
| test_scheduler.py | 1 | job "sync_weekly" registrado |

Mocks: MagicMock (client fake) e pytest-mock instalado.

## 6. Ambiente

- Python 3.12.7 (venv em .venv/), Linux (VMware VM)
- pytest 9.2.0, pytest-mock 3.17.0, pluggy 1.7.0
- Streamlit servindo em http://localhost:8502
- Banco: SQLite em data/database.db

## 7. Próximos passos planejados

- Fixture JSON realista da Pluggy (sandbox) em tests/fixtures/ para validar
  mapeamento de campos reais (connector.name, type, value).
- Edge cases de consolidacao: item sem connector, balance/value ausentes → 0.0,
  item só com contas ou só com investimentos.
- Persistência: ligar sync_all ao snapshot_repository e testar ciclo salvar → ler
  (usando :memory: ou tmp_path, nunca o banco de produção).
- Teste de fumaça do dashboard: importar dashboard.Home num teste para pegar erros
  de import antes de abrir o navegador.
- Cobertura: pytest-cov com --cov=app --cov-report=term-missing.

## 8. Convenções adotadas

- Testes com pytest, mocks via MagicMock/pytest-mock.
- Cliente Pluggy tolerante a dois formatos de resposta (lista ou results).
- Sem state global em módulos com side effects (scheduler inicia só via função
  explícita).
- Sempre limpar __pycache__/.pytest_cache após mover módulos.
