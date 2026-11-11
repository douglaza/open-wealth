
# OpenWealth 📊

Consolidação patrimonial pessoal em Python. Conecte suas contas
bançárias e corretoras via **Pluggy** e acompanhe seu patrimônio
em um dashboard Streamlit.

## Funcionalidades

- ✅ Sincronização de saldos e investimentos (Pluggy API)
- ✅ Histórico patrimonial em SQLite
- ✅ Dashboard com evolução, alocação por instituição e por classe de ativo
- ✅ Job de sincronização semanal

## Arquitetura

```
Pluggy API → Integrations → Services → SQLite → Streamlit
```

## Instalação

```bash
git clone https://github.com/seuusuario/openwealth.git
cd openwealth
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # preencha suas credenciais
```

## Configuração

Obtenha `CLIENT_ID` e `CLIENT_SECRET` em [dashboard.pluggy.ai](https://dashboard.pluggy.ai)
e preencha o `.env`:

```env
PLUGGY_CLIENT_ID=seu_id
PLUGGY_CLIENT_SECRET=seu_secret
DATABASE_URL=sqlite:///data/database.db
```

## Uso

```bash
# Sincronizar patrimônio
python -m app.jobs.sync_weekly

# Rodar dashboard
streamlit run dashboard/Home.py
```

## Stack

FastAPI · Streamlit · SQLite · Pluggy API · Pandas · Playwright (futuro)
