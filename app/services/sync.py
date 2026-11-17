"""Sincroniza dados da Pluggy para o banco local e gera snapshots."""

import logging
import os
import time
from datetime import date
from typing import Any

from app.core.config import settings
from app.core.exceptions import PluggyError
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


def _get_configured_item_ids() -> list[str]:
    raw = (
        getattr(settings, "pluggy_item_ids", None)
        or os.getenv("PLUGGY_ITEM_IDS")
        or getattr(settings, "pluggy_item_id", None)
        or os.getenv("PLUGGY_ITEM_ID")
        or ""
    )
    return [i.strip() for i in raw.split(",") if i.strip()]


def _infer_institution(
    accounts: list[Any],
    investments: list[Any] | None = None,
    fallback: str = "MeuPluggy",
) -> str:
    """Infere o nome amigável da instituição a partir de contas e investimentos."""
    for acc in accounts:
        name = (acc.get("name") or "").lower()
        if "itau" in name or "personnalite" in name:
            return "Itaú"
        if "c6" in name:
            return "C6 Bank"
        if "nubank" in name or "nu " in name:
            return "Nubank"
        if "btg" in name:
            return "BTG Pactual"
        if "bradesco" in name:
            return "Bradesco"
        if "santander" in name:
            return "Santander"
        if "inter" in name:
            return "Banco Inter"
        if "xp" in name:
            return "XP Investimentos"

    if investments:
        for inv in investments:
            name = (inv.get("name") or "").lower()
            if "itau" in name:
                return "Itaú"
            if "c6" in name:
                return "C6 Bank"
            if "btg" in name:
                return "BTG Pactual"
            if "bradesco" in name:
                return "Bradesco"
            if "santander" in name:
                return "Santander"

    return fallback


def sync_weekly(client=None, repo=None, item_ids: list[str] | None = None):
    """Busca os itens Pluggy configurados, salva contas/investimentos
    e persiste o snapshot diário."""
    snapshot_date = date.today().isoformat()
    logger.info("sync_started", extra={"snapshot_date": snapshot_date})

    with SYNC_DURATION_SECONDS.time():
        try:
            client = PluggyClient() if client is None else client
            repo = SnapshotRepository() if repo is None else repo

            target_ids: list[str | None]
            if item_ids is not None:
                target_ids = [i for i in item_ids] or [None]
            elif isinstance(client, PluggyClient):
                target_ids = [i for i in _get_configured_item_ids()] or [None]
            else:
                target_ids = [None]

            total_accounts = 0
            total_investments = 0
            total_patrimonio = 0.0
            any_synced = False

            for target_id in target_ids:
                item = client.get_item(target_id) if target_id else client.get_item()

                item_id = item["id"]
                connector = item.get("connector") or {}
                institution = connector.get("name") or item.get("institution") or "Desconhecida"

                accounts: list[Any] | None = None
                investments: list[Any] | None = None

                # Se o conector for genérico (MeuPluggy), identifica o banco real pelos produtos
                if institution.lower() in ("meupluggy", "desconhecida", ""):
                    accounts = client.get_accounts(item_id) or []
                    investments = client.get_investments(item_id) or []
                    institution = _infer_institution(accounts, investments, fallback=institution)

                if repo.snapshot_exists(snapshot_date, institution):
                    logger.info(
                        "snapshot_skipped",
                        extra={"snapshot_date": snapshot_date, "institution": institution},
                    )
                    continue

                if accounts is None:
                    accounts = client.get_accounts(item_id) or []
                if investments is None:
                    investments = client.get_investments(item_id) or []

                logger.info(
                    "sync_data_fetched",
                    extra={
                        "institution": institution,
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

                total_accounts += len(accounts)
                total_investments += len(investments)
                total_patrimonio += sum(float(a.get("balance") or 0.0) for a in accounts) + sum(
                    _investment_amount(i) for i in investments
                )
                any_synced = True

            repo.commit()
            LAST_SYNC_TIMESTAMP.set(time.time())

            if any_synced:
                logger.info(
                    "snapshot_saved",
                    extra={
                        "snapshot_date": snapshot_date,
                        "account_count": total_accounts,
                        "investment_count": total_investments,
                    },
                )
                ACCOUNTS_TOTAL.set(total_accounts)
                INVESTMENTS_TOTAL.set(total_investments)
                TOTAL_PATRIMONIO_BRL.set(total_patrimonio)

        except Exception as exc:
            if isinstance(exc, PluggyError):
                PLUGGY_ERRORS_TOTAL.labels(operation="sync").inc()
            logger.exception("sync_failed", extra={"snapshot_date": snapshot_date})
            raise


if __name__ == "__main__":  # pragma: no cover
    sync_weekly()
