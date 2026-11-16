"""Sincroniza dados da Pluggy para o banco local e gera snapshots."""

import logging
import time
from datetime import date

from app.core.exceptions import PluggyError  # ou sua exceção da Pluggy
from app.core.metrics import (
    ACCOUNTS_TOTAL,
    INVESTMENTS_TOTAL,
    LAST_SYNC_TIMESTAMP,
    PLUGGY_ERRORS_TOTAL,
    SYNC_DURATION_SECONDS,
    TOTAL_PATRIMONIO_BRL,
)
from app.integrations.pluggy_client import PluggyClient
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.consolidacao import _investment_amount, _map_category

logger = logging.getLogger(__name__)


def sync_weekly(client=None, repo=None):
    """Busca o item Pluggy configurado, salva contas/investimentos
    e persiste o snapshot diário."""
    snapshot_date = date.today().isoformat()
    logger.info("sync_started", extra={"snapshot_date": snapshot_date})

    with SYNC_DURATION_SECONDS.time():
        try:
            client = PluggyClient() if client is None else client
            repo = SnapshotRepository() if repo is None else repo

            item = client.get_item()
            item_id = item["id"]
            connector = item.get("connector") or {}
            institution = connector.get("name") or item.get("institution") or "Desconhecida"

            if repo.snapshot_exists(snapshot_date, institution):
                logger.info("snapshot_skipped", extra={"snapshot_date": snapshot_date})
                repo.commit()
                LAST_SYNC_TIMESTAMP.set(time.time())
                return

            accounts = client.get_accounts(item_id) or []
            investments = client.get_investments(item_id) or []
            logger.info(
                "sync_data_fetched",
                extra={
                    "account_count": len(accounts),
                    "investment_count": len(investments),
                },
            )

            repo.upsert_item(item, snapshot_date)
            for account in accounts:
                balance = account.get("balance")
                repo.save_snapshot_row(
                    snapshot_date,
                    institution,
                    account.get("type") or "outros",
                    account.get("name") or "",
                    _map_category(account),
                    float(balance) if balance is not None else 0.0,
                )
                repo.upsert_account(account, item_id, snapshot_date)

            for investment in investments:
                repo.save_snapshot_row(
                    snapshot_date,
                    institution,
                    "investment",
                    investment.get("name") or "Investimento sem nome",
                    investment.get("type") or "INVESTMENT",
                    _investment_amount(investment),
                )
                repo.upsert_investment(investment, item_id, snapshot_date)

            repo.commit()
            logger.info(
                "snapshot_saved",
                extra={
                    "snapshot_date": snapshot_date,
                    "account_count": len(accounts),
                    "investment_count": len(investments),
                },
            )
            total_patrimonio = sum(float(a.get("balance") or 0.0) for a in accounts) + sum(
                _investment_amount(i) for i in investments
            )

            ACCOUNTS_TOTAL.set(len(accounts))
            INVESTMENTS_TOTAL.set(len(investments))
            TOTAL_PATRIMONIO_BRL.set(total_patrimonio)
            LAST_SYNC_TIMESTAMP.set(time.time())

        except Exception as exc:
            if isinstance(exc, PluggyError):
                PLUGGY_ERRORS_TOTAL.labels(operation="sync").inc()
            logger.exception("sync_failed", extra={"snapshot_date": snapshot_date})
            raise


if __name__ == "__main__":  # pragma: no cover
    sync_weekly()
