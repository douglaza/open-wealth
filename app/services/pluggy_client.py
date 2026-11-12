"""
Cliente da API Pluggy (https://pluggy.ai).
Docs: https://pluggy.readme.io/reference
"""
import time
import requests

from app.core.config import settings


class PluggyClient:
    TOKEN_LIFETIME = 2 * 60 * 60 - 60  # tokens duram 2h; renovamos 1min antes

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self._client_id = client_id or settings.pluggy_client_id
        self._client_secret = client_secret or settings.pluggy_client_secret
        self._base_url = settings.pluggy_base_url
        self._item_id = getattr(settings, "pluggy_item_id", None)
        self._token = None
        self._token_expiry = 0

    # ---------- auth ----------

    def _authenticate(self) -> str:
        resp = requests.post(
            f"{self._base_url}/auth",
            json={
                "clientId": self._client_id,
                "clientSecret": self._client_secret,
            },
            headers={"accept": "application/json"},
            timeout=30,
        )
        if resp.status_code != 200:
            print("AUTH ERROR:", resp.status_code, resp.text)
        resp.raise_for_status()
        self._token = resp.json()["apiKey"]
        self._token_expiry = time.time() + self.TOKEN_LIFETIME
        return self._token

    def _get_token(self) -> str:
        if not self._token or time.time() > self._token_expiry:
            return self._authenticate()
        return self._token

    # ---------- http core ----------

    def _get(self, path: str, params: dict = None) -> dict:
        resp = requests.get(
            f"{self._base_url}{path}",
            headers={"X-API-KEY": self._get_token()},
            params=params or {},
            timeout=30,
        )
        if resp.status_code != 200:
            print("GET ERROR:", resp.status_code, resp.text)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _extract_results(data) -> list:
        if isinstance(data, list):
            return data
        return data.get("results", [])

    # ---------- endpoints ----------

    def get_item(self, item_id: str = None) -> dict:
        """Item atual (do .env) ou um específico."""
        return self._get(f"/items/{item_id or self._item_id}")

    def get_accounts(self, item_id: str = None) -> list:
        return self._extract_results(
            self._get("/accounts", params={"itemId": item_id or self._item_id})
        )

    def get_investments(self, item_id: str = None) -> list:
        return self._extract_results(
            self._get("/investments", params={"itemId": item_id or self._item_id})
        )


    def get_transactions(self, account_id: str, cursor: str = None) -> dict:
        """API v2: paginação por cursor. Retorna {'results': [...], 'hasNext': bool, 'nextCursor': ...}."""
        params = {"accountId": account_id}
        if cursor:
            params["cursor"] = cursor
        return self._get("/v2/transactions", params=params)


    def get_all_transactions(self, account_id: str) -> list:
        """Percorre todas as páginas da v2."""
        all_tx, cursor = [], None
        while True:
            data = self.get_transactions(account_id, cursor=cursor)
            all_tx.extend(self._extract_results(data))
            if not data.get("hasNext"):
                break
            cursor = data.get("nextCursor")
        return all_tx

    # Deixar comentado por enquanto — a listagem /items dá 401 no modo Development
    # def get_items(self) -> list:
    #     items, page = [], 1
    #     while True:
    #         data = self._get("/items", params={"page": page, "pageSize": 100})
    #         items.extend(self._extract_results(data))
    #         if page >= (data.get("totalPages", 1) if isinstance(data, dict) else 1):
    #             break
    #         page += 1
    #     return items
