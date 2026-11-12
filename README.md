# Open Wealth

MVP em Python para consolidar patrimônio pessoal a partir dos dados da Pluggy.
O projeto contém um cliente para a API Pluggy, lógica de consolidação em
snapshots, persistência SQLite, visualizações Streamlit e uma API FastAPI em
desenvolvimento.

> **Estado do MVP:** os componentes principais e suas regras de negócio têm
> testes automatizados, mas a execução ponta a ponta ainda não está concluída.
> As limitações atuais da API e da sincronização estão descritas abaixo.

## Tutorial

Veja o [tutorial da Fase 1](tutorial/ow1_mvp.html) para uma explicação visual
da arquitetura, do fluxo de consolidação, da regra de valoração de investimentos,
do repositório de snapshots e dos testes de regressão.

## Funcionalidades implementadas

- Cliente Pluggy com autenticação, consultas de item, contas e investimentos.
- Consulta de transações pela API v2 da Pluggy, com paginação por cursor.
- Consolidação do item configurado em um `Snapshot` diário.
- Cálculo de totais gerais e por instituição.
- Persistência de snapshots no SQLite, com consulta do mais recente e por
  período.
- Dashboard Streamlit para visualizar snapshots, patrimônio, investimentos e
  evolução.
- Scheduler configurado para executar às segundas-feiras às 06:00, no fuso
  `America/Sao_Paulo`.
- 17 testes automatizados, incluindo regressões da valoração de investimentos.

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
Pluggy API → PluggyClient → sync_all → Snapshot
                                      ↓
                         SnapshotRepository ↔ SQLite

                 FastAPI e dashboard Streamlit
```

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
tutorial/          # tutorial visual da Fase 1
main.py            # aplicação FastAPI (em desenvolvimento)
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

A suíte atual tem **17 testes**. As chamadas HTTP à Pluggy são simuladas; os
testes não precisam de credenciais nem acessam o banco de produção.

## Executar as aplicações

### Dashboard

```bash
streamlit run dashboard/Home.py
```

O dashboard lê a tabela `snapshots`; portanto, precisa de um banco inicializado
e de snapshots persistidos para exibir dados.

### API

A API FastAPI define as rotas `GET /health` e `GET /patrimonio`. O comando
previsto para iniciá-la é:

```bash
uvicorn main:app --reload
```

**A API ainda não inicia no estado atual:** `main.py` importa `get_all`, que não
existe em `app.repositories.snapshot_repository`. A consulta correspondente
precisa ser implementada antes de executar a API.

## Limitações conhecidas

- A sincronização agendada ainda não está ligada ao fluxo atual de
  `sync_all`/`SnapshotRepository`. O serviço `sync_weekly` chama
  `get_items()`, mas esse método está desabilitado no cliente e a listagem
  retorna `401` no modo Development.
- `PLUGGY_ITEM_ID` permite obter o item e consolidá-lo pelo fluxo manual de
  `sync_all`, mas o job semanal ainda precisa ser adaptado para usar esse item e
  persistir o snapshot.
- A rota `/patrimonio` depende da implementação pendente de `get_all` citada
  acima.
- O suporte atual é orientado a um item Pluggy; múltiplos itens e a integração
  completa do dashboard ainda são evoluções futuras.

## Tecnologias

Python · Pluggy API · SQLite · FastAPI · Streamlit · Pandas · APScheduler ·
pytest
