# Arquitetura — Open Wealth

Referência das camadas, suas responsabilidades e do estado atual da
implementação. Consultar antes de refatorações.

## Princípio de dependências

A direção desejada é para dentro: o domínio não conhece HTTP, banco de dados ou
frameworks; as camadas externas dependem dos modelos e regras do domínio.

```text
app/api ──▶ app/services ──▶ app/domain
                  │
                  ├──▶ app/integrations ──▶ Pluggy API
                  └──▶ app/repositories ──▶ app/core/database ──▶ SQLite
```

Esse é o limite arquitetural buscado, não uma abstração completa: hoje serviços
importam implementações concretas de integração e repositório, e alguns serviços
criam essas dependências quando não são injetadas.

## Camadas

### `app/domain/` — modelos e invariantes

- `Position` e `Snapshot` são modelos Pydantic.
- `Position` valida que valores negativos só sejam aceitos para contas do tipo
  `CREDIT`; `Snapshot.total` soma os valores de suas posições.
- O domínio não deve fazer chamadas HTTP nem acesso a banco.

### `app/integrations/` — comunicação com sistemas externos

- `PluggyClient` autentica e consulta item, contas, investimentos e transações.
- A autenticação usa `X-API-KEY`; transações são consultadas em
  `/v2/transactions` com paginação por cursor.
- Erros HTTP e de rede são convertidos em `PluggyError`, tratados pela API como
  `502 Bad Gateway`.
- A listagem de itens está desabilitada no modo Development; o cliente usa o item
  configurado em `PLUGGY_ITEM_ID`.
- Retry com backoff ainda não está implementado.

### `app/repositories/` — persistência e consultas

- `SnapshotRepository` concentra operações sobre as tabelas de snapshots, itens,
  contas e investimentos.
- O repositório recebe uma conexão SQLite opcional; sem conexão fornecida, usa
  `app.core.database.get_connection()`.
- O schema é assegurado na inicialização do repositório com DDL idempotente e
  migrações incrementais.
- Há operações para verificar snapshots existentes, gravar posições e metadados,
  consultar snapshots, e obter totais para rentabilidade.
- O repositório conhece SQLite e SQL; os chamadores devem usar seus métodos em
  vez de espalhar consultas pelo serviço ou pela API.

### `app/services/` — regras e orquestração

- `consolidacao.py` transforma os dados Pluggy em posições e calcula totais.
- `sync.py` coordena a leitura do item, contas e investimentos e persiste os
  resultados pelo repositório.
- `rentabilidade.py` calcula variações a partir das consultas do repositório.
- `sync_weekly` aceita cliente e repositório para facilitar testes; se omitidos,
  instancia as implementações concretas. A transação da sincronização ainda não
  tem rollback garantido em todas as falhas parciais.
- A seleção de campos e a classificação de posições pertencem à consolidação,
  não ao cliente HTTP.

#### Regra atual para valor de investimentos

Em `app/services/consolidacao.py`, o valor é resolvido nesta ordem:

1. `balance`, quando não for `None`;
2. `amount`, quando `balance` estiver ausente;
3. `0.0`, quando ambos estiverem ausentes.

No contrato atual, `value` representa quantidade de cotas, não o valor
monetário da posição; por isso não é usado como fallback. Confirme essa semântica
com dados reais da Pluggy antes de alterar a regra. Não substitua essa cascata
por `quantity * price` sem validar o significado desses campos por produto.

### `app/api/` — entrada HTTP

- `app.api.main` cria a aplicação FastAPI e registra o router.
- `app.api.routes` define endpoints, resolve dependências com `Depends` e delega
  o trabalho aos serviços e repositórios.
- Endpoints implementados:
  - `POST /api/v1/sync` — inicia uma sincronização e responde `202`.
  - `GET /api/v1/rentabilidade/total`.
  - `GET /api/v1/rentabilidade/instituicoes`.
- A API converte `PluggyError` em resposta `502`. Não há endpoint `/health` ou
  de leitura geral de snapshots neste router atualmente.

### `app/core/` — infraestrutura compartilhada

- `config.py` carrega configurações com `pydantic-settings`.
- `database.py` configura conexões SQLite e também declara o schema da aplicação.
- `logging.py` configura logs JSON; `app/__init__.py` ativa essa configuração.
- `scheduler.py` define um job semanal para segunda-feira às 06:00 em
  `America/Sao_Paulo`; o agendador precisa ser iniciado explicitamente.

### `dashboard/` — interface Streamlit

- `Home.py` e `pages/` leem os dados persistidos para apresentar patrimônio,
  investimentos e evolução.
- O dashboard depende de snapshots existentes no banco.

## Fluxos principais

### Sincronização via API

```text
POST /api/v1/sync
    → dependências FastAPI (PluggyClient, SnapshotRepository)
    → sync_weekly
    → busca item e verifica se já há snapshot para a data/instituição
    → busca contas e investimentos
    → grava item, posições e metadados
    → commit
    → resposta 202
```

A verificação de duplicata ocorre depois de buscar o item, pois a instituição é
obtida dos dados desse item. Se já houver snapshot para a data e instituição, o
serviço registra `snapshot_skipped` e não consulta contas nem investimentos.

### Observabilidade

Os eventos do serviço de sincronização são registrados como JSON:

| Evento | Significado |
|---|---|
| `sync_started` | A sincronização começou |
| `sync_data_fetched` | Contagens de contas e investimentos obtidas |
| `snapshot_saved` | A persistência foi concluída |
| `snapshot_skipped` | Já existia snapshot para a data e instituição |
| `sync_failed` | A sincronização falhou; o traceback é registrado e a exceção é propagada |

## Decisões de mudança

| Mudança | Principal local |
|---|---|
| Ajustar endpoint, rota ou dependência HTTP | `app/api/` |
| Alterar protocolo, autenticação ou parsing da Pluggy | `app/integrations/pluggy_client.py` |
| Alterar a regra de valor ou classificação de posição | `app/services/consolidacao.py` |
| Alterar a coordenação/persistência da sincronização | `app/services/sync.py` |
| Alterar consultas e escrita de snapshots | `app/repositories/snapshot_repository.py` |
| Trocar ou ajustar a conexão/schema SQLite | `app/core/database.py` e repositórios |
| Alterar um modelo ou uma invariante do domínio | `app/domain/models.py` |
| Alterar visualização | `dashboard/` |

Trocar SQLite por outro banco exige alterar o repositório e a infraestrutura de
banco; a persistência ainda não é independente de tecnologia por interface
formal.

## Verificações

Execute os testes e a cobertura configurada no projeto:

```bash
pytest -q
```

Verificações rápidas das fronteiras arquiteturais:

```bash
# O domínio não deve importar HTTP nem persistência.
rg -n 'requests|httpx|sqlite3|database|FastAPI' app/domain

# Serviços não devem executar SQL ou abrir conexões diretamente.
rg -n 'get_connection|sqlite3|SELECT |INSERT |UPDATE |DELETE ' app/services
```

Sem correspondências é o resultado esperado. Revise qualquer ocorrência antes
de aprovar uma refatoração; essas buscas são verificações simples, não substituem
testes nem revisão de dependências.

## Pendências arquiteturais

- Garantir rollback da unidade completa de sincronização quando qualquer
  persistência falhar.
- Isolar as implementações concretas de cliente e repositório atrás de
  interfaces, se a evolução justificar essa complexidade.
- Ligar o scheduler ao fluxo de sincronização e persistência.
- Implementar endpoints de leitura de snapshots e a rota de saúde, caso sejam
  necessários para a aplicação.
- Rever a configuração: `database.py` e `SnapshotRepository` atualmente
  participam da criação do schema.
- Adicionar retry com backoff à integração Pluggy, com política e limites
  explícitos.
