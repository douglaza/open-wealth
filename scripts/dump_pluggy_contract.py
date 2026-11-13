# scripts/dump_pluggy_contract.py
"""Captura os valores reais de type/subtype da Pluggy para o item do .env. Descartável."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.integrations.pluggy_client import PluggyClient

client = PluggyClient()

item = client.get_item()
print(f"=== item: {item.get('connector', {}).get('name')} ===")

for acc in client.get_accounts():
    print(json.dumps({
        "name": acc.get("name"),
        "type": acc.get("type"),
        "subtype": acc.get("subtype"),
        "balance": acc.get("balance"),
    }, ensure_ascii=False))

for inv in client.get_investments():
    print(json.dumps({
        "name": inv.get("name"),
        "type": inv.get("type"),
        "subtype": inv.get("subtype"),
        "balance": inv.get("balance"),
        "value": inv.get("value"),
        "amount": inv.get("amount"),
    }, ensure_ascii=False))
