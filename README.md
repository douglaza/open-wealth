
# Open Wealth

MVP em Python para consolidar patrimônio pessoal a partir dos dados da Pluggy.
O projeto contém um cliente para a API Pluggy, lógica de consolidação em
snapshots, persistência SQLite, API FastAPI e visualizações Streamlit.

> **Estado do MVP:** os componentes principais e suas regras de negócio têm
> testes automatizados, e o ciclo de sincronização ponta a ponta já persiste
> snapshots reais no banco. As limitações restantes estão descritas abaixo.

## Tutorial

- [Tutorial da Fase 1](tutorial/ow1_mvp.html) — arquitetura, fluxo de
  consolidação, regra de valoração de investimentos, repositório de snapshots
  e testes de regressão.
- [Tutorial da Fase 2](tutorial/ow2_fase2.html) — API de sincronização,
  persistência com schema autoconstruído, idempotência diária e log
  estruturado.

## Funcionalidades implementadas

- Cliente Pluggy com autenticação, consultas de item, contas e investimentos.
- Consulta de transações pela API v2 da Pluggy, com paginação por cursor.
- Consolidação do item configurado em um `Snapshot` diário.
- Cálculo de totais gerais e por instituição.
- Persistência de snapshots no SQLite, com schema autoconstruído na
  instanciação do repositório (`CREATE TABLE IF NOT EXISTS` + migração
  incremental).
- **Idempotência diária:** rodar o sync duas vezes no mesmo dia não duplica
  dados — o snapshot existente é pulado sem nova chamada à API.
- Endpoint `POST /api/v1/sync` que dispara o ciclo Pluggy → posições → banco
  e responde `202 Accepted`.
- Log estruturado em JSON com eventos nomeados por etapa do sync
  (`sync_started`, `sync_data_fetched`, `snapshot_saved`, `snapshot_skipped`).
- Dashboard Streamlit para visualizar snapshots, patrimônio, investimentos e
  evolução.
- Scheduler configurado para executar às segundas-feiras às 06:00, no fuso
  `America/Sao_Paulo`.
- 17 testes automatizados, incluindo regressões da valoração de investimentos
  e dedup diária do repositório contra SQLite real.

### Regra de valoração dos investimentos

O valor de cada posição usa a seguinte prioridade:

1. `balance`, quando disponível;
2. `value`, como fallback;
3. `quantity * price`, se ambos estiverem disponíveis;
4. `0.0`, quando não houver valor utilizável.

O campo `amount` da API não é usado: pode divergir do saldo exibido pela
instituição. O valor resolvido pela cascata é usado na agregação patrimonial.

## Arquitetura

```text
POST /api/v1/sync
        ↓
   sync_weekly(client, repo)
        ↓
Pluggy API → PluggyClient → sync_all → Snapshot
                                      ↓
                         SnapshotRepository ↔ SQLite
                                (dedup por dia)

                 FastAPI e dashboard Streamlit
```

O endpoint não contém regra de negócio: monta as dependências
(PluggyClient, SnapshotRepository) e delega ao sync_weekly. A dedup
diária vive no repositório, então qualquer chamador (endpoint, scheduler,
teste) herda a garantia.

O cliente e a consolidação trabalham com um item por vez, usando
`PLUGGY_ITEM_ID` no modo Development da Pluggy. A listagem de itens está
desabilitada porque não está disponível nesse modo.

## Estrutura do projeto

```text
app/
├── core/          # configurações, banco de dados e scheduler
├── models/        # modelos de conta, investimento e snapshot
├── repositories/  # persistência e consultas
└── services/      # Pluggy, consolidação, rentabilidade e sincronização
dashboard/         # aplicação Streamlit e páginas
data/              # banco SQLite e exports
tests/             # testes unitários e de persistência
tutorial/          # tutoriais visuais das Fases 1 e 2
main.py            # aplicação FastAPI
```

## Requisitos

- Python 3.12 ou compatível com as dependências listadas em
  [requirements.txt](requirements.txt).
- Credenciais da Pluggy para consultar dados reais.
- Um item sandbox conectado e seu ID para o modo Development.

## Instalação e configuração

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edite o `.env` com suas credenciais e o ID do item Pluggy:

```env
PLUGGY_CLIENT_ID=seu_client_id
PLUGGY_CLIENT_SECRET=seu_client_secret
PLUGGY_ITEM_ID=seu_item_id
DATABASE_URL=sqlite:///data/database.db
```

`PLUGGY_ITEM_ID` é necessário no modo Development, embora ainda precise ser
adicionado manualmente ao `.env`. O caminho do banco pode ser sobrescrito pela
variável `OW_DB_PATH`. Não compartilhe nem versione credenciais reais.

## Testes

Execute a suíte a partir da raiz do projeto:

```bash
pytest -q
```

A suíte atual tem 17 testes. As chamadas HTTP à Pluggy são simuladas; os
testes de repositório rodam contra SQLite em banco temporário, sem acessar o
banco de produção.

## Executar as aplicações

### API

```bash
uvicorn main:app --reload
```

Rotas disponíveis:

- `GET /health` — verificação de disponibilidade.
- `POST /api/v1/sync` — dispara o sync; responde `202 Accepted` e grava o
  snapshot do dia (ou pula se já existir).

Disparo manual do sync:

```bash
curl -X POST http://localhost:8000/api/v1/sync
```

Na primeira chamada do dia, o log mostra
`sync_started → sync_data_fetched → snapshot_saved`. Nas seguintes,
`snapshot_skipped` confirma a idempotência.

Verificação direta do banco:

```bash
sqlite3 data/database.db "SELECT asset_name, category, amount FROM snapshots;"
```

⚠️ Se remover `data/database.db` manualmente, reinicie o servidor: o
`--reload` do uvicorn pode manter conexões abertas com o arquivo antigo.

### Dashboard

```bash
streamlit run dashboard/Home.py
```

O dashboard lê a tabela `snapshots`; portanto, precisa de um banco
inicializado e de snapshots persistidos para exibir dados. Rode o sync
(`POST /api/v1/sync`) ao menos uma vez antes de abrir.

## Limitações conhecidas

- O scheduler semanal ainda não está ligado ao fluxo de
  `sync_weekly`/`SnapshotRepository`; hoje o sync é disparado manualmente via
  `POST /api/v1/sync`. O job precisa ser adaptado para reutilizar o item
  configurado em `PLUGGY_ITEM_ID`.
- A listagem de itens (`get_items()`) retorna 401 no modo Development da
  Pluggy; o fluxo usa o item único configurado por variável de ambiente.
- As credenciais da Pluggy ainda são montadas dentro do endpoint; a migração
  para variáveis de ambiente injetadas está pendente.
- Não há endpoints de leitura (`GET /api/v1/snapshots`) nem rotas de
  rentabilidade/evolução — previstos para a Fase 3.
- Não há retry com backoff nas chamadas à Pluggy nem tratamento de
  timeout explícito.
- O suporte atual é orientado a um item Pluggy; múltiplos itens e a integração
  completa do dashboard ainda são evoluções futuras.

## Tecnologias

Python · Pluggy API · SQLite · FastAPI · Streamlit · Pandas · APScheduler ·
pytest

**Principais mudanças em relação à versão anterior:**

1. **Estado do MVP** — deixou de dizer que a execução ponta a ponta "não está
   concluída"; agora o sync persiste de verdade.
2. **Novas funcionalidades** — schema autoconstruído, idempotência diária,
   `POST /api/v1/sync` (202) e log estruturado.
3. **Arquitetura** — o diagrama agora mostra o fluxo a partir do endpoint.
4. **Seção API** — substitui o aviso "a API ainda não inicia" pelas rotas
   funcionais e pelo exemplo de `curl`.
5. **Limitações** — removidas as três limitações resolvidas (sync órfão,
   `get_all` inexistente, item não persistido) e adicionadas as pendências reais
   da Fase 3 (endpoints de leitura, credenciais em env, retry, scheduler ligado).

> Ajuste o caminho do tutorial da Fase 2 (`tutorial/ow2_fase2.html`) se o nome
> do arquivo for outro.
