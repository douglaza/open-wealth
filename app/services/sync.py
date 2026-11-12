"""Sincroniza dados da Pluggy para o banco local e gera snapshots."""
from datetime import date
from app.integrations.pluggy_client import PluggyClient
from app.repositories.snapshot_repository import SnapshotRepository


def _map_category(connector_type: str) -> str:
    """Mapeia tipos da Pluggy para nossas categorias."""
    mapping = {
        "CHECKING": "banco",
        "SAVINGS": "banco",
        "CREDIT": "cartao",
        "investment": "investimento",
    }
    return mapping.get(connector_type, "outros")


def sync_weekly(client=None, repo=None):
    """Busca tudo na Pluggy e grava snapshot diário no banco."""
    client = client or PluggyClient()
    repo = repo or SnapshotRepository()
    hoje = date.today().isoformat()

    for item in client.get_items():
        item_id = item["id"]
        institution = item.get("institution", "Desconhecida")

        # evita snapshot duplicado no mesmo dia
        if repo.snapshot_exists(hoje, institution):
            continue

        for acc in client.get_accounts(item_id):
            repo.save_snapshot_row(
                hoje, institution, acc.get("type", "outros"),
                acc.get("name", ""), _map_category(acc.get("type", "")),
                acc.get("balance", 0) or 0,
            )
            repo.upsert_account(acc, item_id, hoje)

        for inv in client.get_investments(item_id):
            repo.upsert_investment(inv, item_id, hoje)

    repo.commit()
    print(f"✅ Sync concluído em {hoje}")


if __name__ == "__main__":
    sync_weekly()
