# Open Wealth

MVP em Python para consolidar patrimônio pessoal a partir dos dados da Pluggy.
O projeto inclui um cliente para a API Pluggy, lógica de consolidação em
snapshots, persistência em SQLite, API FastAPI e visualizações em Streamlit.

> **Estado do MVP:** os componentes principais e suas regras de negócio têm
> testes automatizados, e o ciclo de sincronização ponta a ponta já persiste
> snapshots reais no banco. As limitações restantes estão descritas abaixo.

## Tutorial

- [Tutorial será disponibilizado ao final do projeto].

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
(`PluggyClient`, `SnapshotRepository`) e delega ao `sync_weekly`. A dedup
diária vive no repositório, então qualquer chamador (endpoint, scheduler,
teste) herda a garantia.

O cliente e a consolidação trabalham com um item por vez, usando
`PLUGGY_ITEM_ID` no modo Development da Pluggy. A listagem de itens está
desabilitada porque não está disponível nesse modo.

### Estrutura do projeto

```text
app/
├── core/          # configurações, banco de dados e scheduler
├── models/        # modelos de conta, investimento e snapshot
├── repositories/  # persistência e consultas
├── services/      # Pluggy, consolidação, rentabilidade e sincronização
├── api/           # rotas e endpoints FastAPI
├── cli.py         # interfaces de linha de comando
└── __init__.py

dashboard/        # aplicação Streamlit e páginas
data/             # banco SQLite e exports
tests/            # testes unitários e de persistência
main.py           # aplicação FastAPI
```

## Requisitos

- Python 3.12 ou compatível com as dependências listadas em `requirements.txt`.
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

Execute a suíte a partir da raiz do projeto. Por padrão, cada teste usa um
SQLite temporário:

```bash
pytest -q
```

Para executar os testes de persistência no PostgreSQL, configure uma base de
dados descartável (os testes limpam suas tabelas antes de cada caso). Com o
PostgreSQL do Compose em execução, crie essa base uma vez:

```bash
docker compose up -d db
docker compose exec db createdb -U openwealth openwealth_test
```

```bash
TEST_DB=postgres TEST_DATABASE_URL=postgresql://openwealth:openwealth@localhost:5433/openwealth_test pytest -q
```

As chamadas HTTP à Pluggy são simuladas.

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

Na primeira chamada do dia, o log mostra `sync_started → sync_data_fetched →
snapshot_saved`. Nas seguintes, `snapshot_skipped` confirma a idempotência.

Verificação direta do banco:

```bash
sqlite3 data/database.db "SELECT asset_name, category, amount FROM snapshots;"
```

> ⚠️ Se remover `data/database.db` manualmente, reinicie o servidor: o
> `--reload` do uvicorn pode manter conexões abertas com o arquivo antigo.

### Dashboard

```bash
streamlit run dashboard/Home.py
```

O dashboard lê a tabela `snapshots`; portanto, precisa de um banco
inicializado e de snapshots persistidos para exibir dados. Rode o sync
(`POST /api/v1/sync`) ao menos uma vez antes de abrir.

## Operação

### Timer systemd (sync semanal)

`/etc/systemd/system/open-wealth-sync.timer` agenda o sync toda
segunda-feira às 06:00, com `Persistent=true` (recupera execução
perdida se a máquina estava desligada).

```bash
sudo systemctl enable --now open-wealth-sync.timer
systemctl list-timers open-wealth-sync.timer

- O sync agendado depende do timer systemd da VM; não há retry próprio
  em caso de falha na chamada à Pluggy (ver retry/backoff abaixo).

![CI](https://github.com/douglaza/open-wealth/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-80%25+-brightgreen)


## Roadmap

Prioridades planejadas para o próximo ciclo:

- Transação atômica no sync: envolver o loop de inserts do repositório com
  `try/except` + `rollback()` (ver `CONTEXT.md §9.4`).
- Testes de integração do sync: `sync_weekly + SnapshotRepository` contra SQLite
  em `tmp_path`/`:memory:`, cobrindo falha parcial no meio do loop de inserts.
- Retorno do endpoint distinguindo `synced` vs `skipped`: hoje ambos respondem
  `202`; o corpo passará a conter `{"status": "synced"|"skipped", ...}`.
- Scheduler ligado ao sync: job diário (cron ou APScheduler) chamando
  `sync_weekly` com o repositório, eliminando o disparo puramente manual.
- Endpoints de leitura (`GET /api/v1/snapshots`) e rotas de rentabilidade/evolução.

## Limitações conhecidas

- O scheduler semanal ainda não está ligado ao fluxo de `sync_weekly`/
  `SnapshotRepository`; hoje o sync é disparado manualmente via `POST /api/v1/sync`.
  O job precisa ser adaptado para reutilizar o item configurado em
  `PLUGGY_ITEM_ID`.
- A listagem de itens (`get_items()`) retorna 401 no modo Development da
  Pluggy; o fluxo usa o item único configurado por variável de ambiente.
- As credenciais da Pluggy ainda são montadas dentro do endpoint; a migração
  para variáveis de ambiente injetadas está pendente.
- Não há endpoints de leitura (`GET /api/v1/snapshots`) nem rotas de
  rentabilidade/evolução — previstos para a Fase 3.
- O sync não é executado em transação atômica: falha no meio do loop de
  inserts pode deixar o banco parcialmente escrito (sem rollback garantido).
- O endpoint responde `202` tanto para `synced` quanto para `skipped`; a
  distinção no corpo da resposta ainda não foi implementada.
- Não há retry com backoff nas chamadas à Pluggy nem tratamento de timeout
  explícito.
- O suporte atual é orientado a um item Pluggy; múltiplos itens e a integração
  completa do dashboard ainda são evoluções futuras.

## Tecnologias

Python · Pluggy API · SQLite · FastAPI · Streamlit · Pandas · APScheduler · pytest

## Changelog desta versão

- Roadmap — Fase 3 — nova seção com as prioridades extraídas do `CONTEXT.md`
  (transação atômica, testes de integração, `synced` vs `skipped`, scheduler diário).
- Limitações — adicionadas as duas pendências conhecidas da Fase 2: sync sem
  transação atômica e resposta `202` sem distinção `synced`/`skipped`.
- Dashboard — as páginas de patrimônio e evolução usam
  `dashboard.data.prepare_snapshot_data`, sem depender da view `v_evolucao`
  nem dos serviços legados de rentabilidade.
- Estado do MVP — inalterado em relação à versão anterior: o sync ponta a ponta
  persiste snapshots reais com idempotência diária.
