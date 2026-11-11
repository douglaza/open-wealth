"""Sincroniza dados da Pluggy para o banco local e gera snapshots."""
from datetime import date
from app.core.database import get_connection
from app.services.pluggy_client import PluggyClient
from app.core.config import PLUGGY_CLIENT_ID, PLUGGY_CLIENT_SECRET


def _map_category(connector_type: str) -> str:
    """Mapeia tipos da Pluggy para nossas categorias."""
    mapping = {
        "CHECKING": "banco",
        "SAVINGS": "banco",
        "CREDIT": "cartao",
        "investment": "investimento",
    }
    return mapping.get(connector_type, "outros")


def sync_weekly():
    """Busca tudo na Pluggy e grava snapshot diário no banco."""
    client = PluggyClient(PLUGGY_CLIENT_ID, PLUGGY_CLIENT_SECRET)
    hoje = date.today().isoformat()
    conn = get_connection()

    for item in client.get_items():
        item_id = item["id"]
        institution = item.get("institution", "Desconhecida")

        # evita snapshot duplicado no mesmo dia
        already = conn.execute(
            "SELECT 1 FROM snapshots WHERE snapshot_date = ? AND institution = ?",
            (hoje, institution),
        ).fetchone()
        if already:
            continue

        for acc in client.get_accounts(item_id):
            conn.execute(
                "INSERT INTO snapshots (snapshot_date, institution, account_type, asset_name, category, amount) "
                "VALUES (?,?,?,?,?,?)",
                (hoje, institution, acc.get("type", "outros"),
                 acc.get("name", ""), _map_category(acc.get("type", "")),
                 acc.get("balance", 0) or 0),
            )
            conn.execute(
                """INSERT INTO accounts (id, item_id, name, type, balance, currency, updated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     balance=excluded.balance, updated_at=excluded.updated_at""",
                (acc["id"], item_id, acc.get("name", ""), acc.get("type"),
                 acc.get("balance", 0), acc.get("currency", "BRL"), hoje),
            )

        for inv in client.get_investments(item_id):
            qty = inv.get("quantity") or 0
            price = inv.get("price") or 0
            conn.execute(
                """INSERT INTO investments (id, item_id, name, type, quantity, price, value, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     quantity=excluded.quantity, price=excluded.price,
                     value=excluded.value, updated_at=excluded.updated_at""",
                (inv["id"], item_id, inv.get("name", ""), inv.get("type"),
                 qty, price, qty * price, hoje),
            )

    conn.commit()
    print(f"✅ Sync concluído em {hoje}")


if __name__ == "__main__":
    sync_weekly()
