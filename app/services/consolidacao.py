from collections import defaultdict
from datetime import date

from app.models.snapshot import Position, Snapshot


def sync_all(client) -> Snapshot:
    positions = []
    items = client.get_items()          # <- agora retorna lista direta

    for item in items:
        institution = item.get("connector", {}).get("name", "Desconhecido")
        item_id = item["id"]

        for acc in client.get_accounts(item_id):
            positions.append(Position(
                institution=institution,
                account_type=acc.get("type", "conta"),
                asset_name=acc.get("name", ""),
                category="Conta",
                amount=acc.get("balance", 0.0),
            ))

        for inv in client.get_investments(item_id):
            positions.append(Position(
                institution=institution,
                account_type="investimentos",
                asset_name=inv.get("name", ""),
                category=inv.get("type", "Investimento"),
                amount=inv.get("value", 0.0),
            ))

    return Snapshot(snapshot_date=date.today(), positions=positions)


def get_totals(snapshot: Snapshot) -> dict:
    by_inst = defaultdict(float)
    for p in snapshot.positions:
        by_inst[p.institution] += p.amount
    return {"total": snapshot.total, "institutions": dict(by_inst)}
