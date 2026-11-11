"""
Cliente da API Pluggy (https://pluggy.ai).
Docs: https://pluggy.readme.io/reference
"""
import time
import requests

PLUGGY_BASE_URL = "https://api.pluggy.ai"


class PluggyClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._token_expiry = 0

    # ---------- auth ----------

    def _authenticate(self) -> str:
        resp = requests.post(
            "https://api.pluggy.ai/auth",
            json={"clientId": self.client_id, "clientSecret": self.client_secret},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["apiKey"]
        self._token_expiry = time.time() + 2 * 60 * 60 - 60
        return self._token

    def _get_token(self) -> str:
        if not self._token or time.time() > self._token_expiry:
            return self._authenticate()
        return self._token

    # ---------- http core ----------

    def _get(self, path: str, params: dict = None) -> dict:
        resp = requests.get(
            f"{PLUGGY_BASE_URL}{path}",
            headers={"X-API-KEY": self._get_token()},
            params=params or {},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ---------- endpoints ----------

    def get_item(self, item_id: str) -> dict:
        return self._get(f"/items/{item_id}")

    def get_items(self) -> list:
        items, page = [], 1
        while True:
            data = self._get("/items", params={"page": page, "pageSize": 100})
            items.extend(self._extract_results(data))
            if page >= (data.get("totalPages", 1) if isinstance(data, dict) else 1):
                break
            page += 1
        return items

    @staticmethod
    def _extract_results(data) -> list:
        """Aceita tanto {'results': [...]} quanto uma lista direta."""
        if isinstance(data, list):
            return data
        return data.get("results", [])

    def get_accounts(self, item_id: str) -> list:
        return self._extract_results(
            self._get("/accounts", params={"itemId": item_id})
        )

    def get_investments(self, item_id: str) -> list:
        return self._extract_results(
            self._get("/investments", params={"itemId": item_id})
        )

    def get_transactions(self, account_id: str, from_date: str = None) -> list:
        params = {"accountId": account_id}
        if from_date:
            params["from"] = from_date
        return self._extract_results(
            self._get("/transactions", params=params)
        )

