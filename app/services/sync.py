"""Sincroniza dados da Pluggy para o banco local e gera snapshots."""
from datetime import date
from app.integrations.pluggy_client import PluggyClient
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.consolidacao import _map_category


def sync_weekly(client=None, repo=None):
    """Busca dados da Pluggy (modo item-único) e grava snapshot diário."""
    hoje = date.today().isoformat()
    client = client or PluggyClient()
    item = client.get_item()
    item_id = item["id"]

    repo = repo or SnapshotRepository()
    institution = item.get("connector", {}).get("name") or item.get("institution") or "Desconhecida"

    if repo.snapshot_exists(hoje, institution):
        repo.commit()
        return

    repo.upsert_item(item, hoje)   # <-- NOVO: garante o pai antes dos filhos
    for acc in client.get_accounts(item_id):
        category = _map_category(acc)          # ← use a função correta, não o mapa antigo
        repo.save_snapshot_row(
            hoje, institution, acc.get("type", "outros"),
            acc.get("name", ""), category,
            acc.get("balance", 0) or 0,
        )
        repo.upsert_account(acc, item_id, hoje)

    for inv in client.get_investments(item_id):
        repo.upsert_investment(inv, item_id, hoje)

    repo.commit()


if __name__ == "__main__":  # pragma: no cover
    sync_weekly()

