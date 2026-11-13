"""Sincroniza dados da Pluggy para o banco local e gera snapshots."""
import logging
from datetime import date

from app.integrations.pluggy_client import PluggyClient
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.consolidacao import _map_category

logger = logging.getLogger(__name__)


def sync_weekly(client=None, repo=None):
    """Busca o item Pluggy configurado, salva contas/investimentos
    e persiste o snapshot diário."""
    snapshot_date = date.today().isoformat()
    logger.info("sync_started", extra={"snapshot_date": snapshot_date})

    try:
        client = PluggyClient() if client is None else client
        repo = SnapshotRepository() if repo is None else repo

        item = client.get_item()
        item_id = item["id"]
        connector = item.get("connector") or {}
        institution = (
            connector.get("name") or item.get("institution") or "Desconhecida"
        )

        if repo.snapshot_exists(snapshot_date, institution):
            logger.info("snapshot_skipped", extra={"snapshot_date": snapshot_date})
            repo.commit()
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
    except Exception:
        logger.exception("sync_failed", extra={"snapshot_date": snapshot_date})
        raise


if __name__ == "__main__":  # pragma: no cover
    sync_weekly()
