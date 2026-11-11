
# OpenWealth 📊

Aplicação Python para acompanhar patrimônio pessoal. Integra dados de contas e
investimentos via **Pluggy**, armazena snapshots no SQLite e exibe indicadores em
um dashboard Streamlit.

## Funcionalidades

- Cliente Pluggy com autenticação e consultas de contas, investimentos e
  transações pela API v2, com paginação por cursor.
- Persistência SQLite para contas, investimentos e snapshots patrimoniais.
- Repositório de snapshots com gravação por data, consulta do snapshot mais
  recente e consulta por período.
- API FastAPI com endpoints `/health` e `/patrimonio`.
- Dashboard Streamlit com patrimônio consolidado, investimentos e evolução.
- Agendamento semanal para segunda-feira às 06:00 (horário de São Paulo).
- Testes automatizados com respostas simuladas e banco de dados temporário.

## Arquitetura

```text
Pluggy API → app/services → app/repositories → SQLite
                                      ↓
                         FastAPI e dashboard Streamlit
```

## Requisitos

- Python 3.12 ou compatível com as dependências do projeto.
- Credenciais Pluggy (`PLUGGY_CLIENT_ID` e `PLUGGY_CLIENT_SECRET`).
- Para o modo Development da Pluggy, o ID do item sandbox (`PLUGGY_ITEM_ID`).

## Instalação e configuração

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure o arquivo `.env`:

```env
PLUGGY_CLIENT_ID=seu_client_id
PLUGGY_CLIENT_SECRET=seu_client_secret
PLUGGY_ITEM_ID=seu_item_id
DATABASE_URL=sqlite:///data/database.db
```

O caminho do banco pode ser sobrescrito com `OW_DB_PATH`. O banco e o schema são
inicializados quando a aplicação FastAPI inicia.

## Executar

Inicie a API:

```bash
uvicorn main:app --reload
```

Atualmente, a inicialização está bloqueada porque `main.py` importa `get_all`,
função ainda ausente no repositório de snapshots. Consulte as pendências abaixo.

Rotas disponíveis:

- `GET /health` — status da aplicação.
- `GET /patrimonio` — dados patrimoniais armazenados.

Em outro terminal, inicie o dashboard:

```bash
streamlit run dashboard/Home.py
```

## Testes

Execute a suíte com:

```bash
pytest -q
```

No estado atual, a suíte contém 13 testes.

## Observações sobre sincronização

O agendador registra `sync_weekly` para segunda-feira às 06:00, no fuso
`America/Sao_Paulo`. A listagem de itens (`get_items`) está desabilitada no
cliente Pluggy porque retorna `401` no modo Development. Como o serviço de
sincronização ainda depende dessa listagem, a execução automática precisa ser
adaptada para usar o `PLUGGY_ITEM_ID` nesse modo antes de funcionar de ponta a
ponta.

Além disso, a rota `/patrimonio` depende de `get_all` no repositório de snapshots;
essa função ainda precisa ser implementada para que a aplicação FastAPI possa
ser importada e iniciada.

## Tecnologias

Python · FastAPI · Streamlit · SQLite · Pluggy API · Pandas · pytest
