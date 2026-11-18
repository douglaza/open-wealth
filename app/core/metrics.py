from typing import Any

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

PATRIMONIO_BY_INSTITUTION_BRL = Gauge(
    "open_wealth_patrimonio_by_institution_brl",
    "Patrimônio consolidado por instituição em BRL",
    labelnames=["institution"],
)

PATRIMONIO_BY_CATEGORY_BRL = Gauge(
    "open_wealth_patrimonio_by_category_brl",
    "Patrimônio consolidado por categoria de ativo em BRL",
    labelnames=["category"],
)

# --- Métricas Manuais e Patrimônio Líquido ---
MANUAL_ASSETS_BRL = Gauge(
    "open_wealth_manual_assets_brl",
    "Valor total de ativos manuais cadastrados em BRL",
)
MANUAL_LIABILITIES_BRL = Gauge(
    "open_wealth_manual_liabilities_brl",
    "Valor total de passivos e dividas manuais em BRL",
)
NET_WORTH_TOTAL_BRL = Gauge(
    "open_wealth_net_worth_total_brl",
    "Patrimonio liquido real consolidado (Ativos Pluggy + Ativos Manuais - Passivos)",
)


def refresh_financial_metrics(
    snapshot_repo: Any = None,
    manual_repo: Any = None,
) -> None:
    """Recalcula e atualiza gauges Prometheus com dados do banco."""
    from app.repositories.manual_position_repository import (
        ManualPositionRepository,
    )
    from app.repositories.snapshot_repository import SnapshotRepository

    s_repo = snapshot_repo if snapshot_repo is not None else SnapshotRepository()
    m_repo = manual_repo if manual_repo is not None else ManualPositionRepository()

    totals = m_repo.get_totals()
    assets = float(totals.get("assets", 0.0))
    liabilities = float(totals.get("liabilities", 0.0))

    MANUAL_ASSETS_BRL.set(assets)
    MANUAL_LIABILITIES_BRL.set(liabilities)

    pluggy_total = 0.0
    try:
        latest_totals = s_repo.ultimos_totais_por_data(n=1)
        if latest_totals:
            pluggy_total = float(latest_totals[0].get("total", 0.0))
        else:
            latest_snap = s_repo.get_latest()
            if latest_snap is not None:
                pluggy_total = float(latest_snap.total)
    except Exception:
        pluggy_total = 0.0

    if pluggy_total > 0:
        TOTAL_PATRIMONIO_BRL.set(pluggy_total)

    net_worth = pluggy_total + assets - liabilities
    NET_WORTH_TOTAL_BRL.set(net_worth)


# --- Métricas do Assistente IA (Insights) ---
INSIGHTS_REQUESTS_TOTAL = Counter(
    "open_wealth_insights_requests_total",
    "Total de requisições enviadas ao assistente de IA",
    labelnames=["status"],  # success, error
)

INSIGHTS_LATENCY_SECONDS = Histogram(
    "open_wealth_insights_latency_seconds",
    "Tempo de resposta do assistente de IA em segundos",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
)
