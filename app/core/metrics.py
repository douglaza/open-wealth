from prometheus_client import Counter, Gauge, Histogram

# Tempo de execução da sincronização
SYNC_DURATION_SECONDS = Histogram(
    "open_wealth_sync_duration_seconds",
    "Tempo de execução da sincronização em segundos",
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

# Total de falhas de comunicação com a Pluggy
PLUGGY_ERRORS_TOTAL = Counter(
    "open_wealth_pluggy_errors_total",
    "Total de falhas ou exceções em chamadas à API da Pluggy",
    ["operation"],  # ex: auth, accounts, investments
)

# Estado do último snapshot consolidado
ACCOUNTS_TOTAL = Gauge(
    "open_wealth_accounts_total",
    "Quantidade de contas sincronizadas no último snapshot",
)

INVESTMENTS_TOTAL = Gauge(
    "open_wealth_investments_total",
    "Quantidade de investimentos sincronizados no último snapshot",
)

TOTAL_PATRIMONIO_BRL = Gauge(
    "open_wealth_total_patrimonio_brl",
    "Valor total do patrimônio consolidado em Reais",
)

LAST_SYNC_TIMESTAMP = Gauge(
    "open_wealth_last_sync_timestamp",
    "Timestamp Unix da última sincronização bem-sucedida",
)
