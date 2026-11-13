"""
Cliente da API Pluggy (https://pluggy.ai).
Docs: https://pluggy.readme.io/reference
"""
import logging
import time
import requests

from app.core.config import Settings
from app.core.exceptions import PluggyError


logger = logging.getLogger(__name__)


class PluggyClient:

    TOKEN_LIFETIME = 2 * 60 * 60 - 60  # tokens duram 2h; renovamos 1min antes

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        settings: Settings | None = None,
    ):
        if settings is None and (client_id is None or client_secret is None):
            from app.core.config import settings as _s
            settings = _s
        s = settings
        self._client_id = client_id or (s.pluggy_client_id if s else "")
        self._client_secret = client_secret or (s.pluggy_client_secret if s else "")
        self._base_url = s.pluggy_base_url if s else "https://api.pluggy.ai"
        self._item_id = getattr(s, "pluggy_item_id", None) if s else None
        self._token = None
        self._token_expiry = 0

    # ---------- auth ----------

    def _authenticate(self) -> str:
        try:
            resp = requests.post(
                f"{self._base_url}/auth",
                json={
                    "clientId": self._client_id,
                    "clientSecret": self._client_secret,
                },
                headers={"accept": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            body = e.response.text[:200] if e.response is not None else ""
            raise PluggyError(f"Auth falhou: {status} {body}") from e
        except requests.RequestException as e:
            raise PluggyError("Falha de rede na autenticação") from e

        self._token = resp.json()["apiKey"]
        self._token_expiry = time.time() + self.TOKEN_LIFETIME
        return self._token

    def _get_token(self) -> str:
        if not self._token or time.time() > self._token_expiry:
            return self._authenticate()
        return self._token


    # ---------- http core ----------

    def _get(self, path: str, params: dict = None) -> dict:
        try:
            resp = requests.get(
                f"{self._base_url}{path}",
                headers={"X-API-KEY": self._get_token()},
                params=params or {},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            raise PluggyError(f"Pluggy respondeu {status} em {path}") from e
        except requests.RequestException as e:
            raise PluggyError(f"Falha de rede ao chamar {path}") from e

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
