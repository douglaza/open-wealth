import pytest
import requests

from app.core.config import Settings
from app.core.exceptions import PluggyError
from app.integrations.pluggy_client import PluggyClient
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.sync import sync_weekly


class FakeClient:
    """Imita a interface usada pelo sync_weekly."""

    DEFAULT_ITEM = {"id": "item-1", "connector": {"name": "Banco Falso"}}
    DEFAULT_ACCOUNTS = [
        {
            "id": "acc-1",
            "name": "Corrente",
            "type": "checking",
            "balance": 100.0,
            "currency": "BRL",
        },
    ]
    DEFAULT_INVESTMENTS = [
        {
            "id": "i1",
            "name": "CDB",
            "type": "banco",
            "quantity": 1.0,
            "price": 50.0,
            "balance": 60.0,
        },
    ]

    def __init__(self, item=None, accounts=None, investments=None):
        self._item = item or self.DEFAULT_ITEM
        self._accounts = accounts or self.DEFAULT_ACCOUNTS
        self._investments = investments or self.DEFAULT_INVESTMENTS

    def get_item(self):
        return self._item

    def get_accounts(self, item_id):
        return self._accounts

    def get_investments(self, item_id):
        return self._investments


class FakeRepo:
    def __init__(self):
        self.calls = []

    def snapshot_exists(self, d, inst):
        return False

    def upsert_item(self, item, d):
        self.calls.append(("upsert_item", item["id"]))

    def save_snapshot_row(self, *args):
        self.calls.append(("save_snapshot_row", args))

    def upsert_account(self, *args):
        self.calls.append(("upsert_account", args))

    def upsert_investment(self, *args):
        self.calls.append(("upsert_investment", args))

    def commit(self):
        self.calls.append(("commit",))


class ExplodingClient(FakeClient):
    def get_item(self):
        raise RuntimeError("API fora do ar")


class PluggyErrorClient(FakeClient):
    def get_item(self):
        raise PluggyError("API fora")


def test_sync_propaga_pluggy_error(caplog):
    repo = FakeRepo()
    with pytest.raises(PluggyError):
        sync_weekly(client=PluggyErrorClient(), repo=repo)
    assert ("commit",) not in repo.calls
    failure = next(r for r in caplog.records if r.getMessage() == "sync_failed")
    assert failure.exc_info[0] is PluggyError


def test_sync_client_error_propagates_sem_commit(caplog):
    repo = FakeRepo()
    with pytest.raises(RuntimeError):
        sync_weekly(client=ExplodingClient(), repo=repo)
    assert ("commit",) not in repo.calls  # nada parcial persistido
    assert all(op != "upsert_item" for op, *_ in repo.calls)  # nada foi gravado
    failure = next(record for record in caplog.records if record.getMessage() == "sync_failed")
    assert failure.exc_info[0] is RuntimeError


def test_sync_flows_through_dependencies(caplog):
    repo = FakeRepo()
    sync_weekly(client=FakeClient(), repo=repo)

    ops = [op for op, *_ in repo.calls]
    # ordem correta: item primeiro, depois snapshots/accounts, investimentos, commit
    assert ops == [
        "upsert_item",
        "save_snapshot_row",
        "upsert_account",
        "save_snapshot_row",
        "upsert_investment",
        "commit",
    ]
    events = [record.getMessage() for record in caplog.records]
    assert events == [
        "sync_started",
        "sync_data_fetched",
        "snapshot_saved",
    ]
    fetched = next(
        record for record in caplog.records if record.getMessage() == "sync_data_fetched"
    )
    assert fetched.account_count == 1
    assert fetched.investment_count == 1
    assert not hasattr(fetched, "item_id")


def test_sync_skips_existing_snapshot():
    repo = FakeRepo()
    repo.snapshot_exists = lambda d, inst: True
    sync_weekly(client=FakeClient(), repo=repo)
    assert repo.calls == [("commit",)]  # só commit, nada gravado


def test_sync_weekly_com_sqlite_real(banco_limpo, mocker):
    mocker.patch(
        "app.services.sync._map_category",
        return_value="Conta",
    )
    client = FakeClient(
        item={"id": "item-1", "connector": {"name": "Banco X"}},
        accounts=[
            {
                "id": "acc-1",
                "name": "Corrente",
                "type": "CHECKING",
                "balance": 1000.0,
                "currency": "BRL",
            },
            {
                "id": "acc-2",
                "name": "Poupança",
                "type": "SAVINGS",
                "balance": 500.0,
                "currency": "BRL",
            },
        ],
        investments=[
            {
                "id": "inv-1",
                "name": "Tesouro IPCA",
                "type": "fixed_income",
                "quantity": 2.0,
                "price": 100.0,
                "balance": 60.0,
            },
        ],
    )
    repo = SnapshotRepository()

    sync_weekly(client=client, repo=repo)

    # snapshots gravados
    rows = repo._conn.execute("SELECT * FROM snapshots").fetchall()
    assert len(rows) == 3
    total = sum(r["amount"] for r in rows)
    assert total == 1560.0
    investment_row = next(r for r in rows if r["account_type"] == "investment")
    assert investment_row["amount"] == 60.0
    assert all(r["institution"] == "Banco X" for r in rows)

    # accounts upsertadas
    accs = repo._conn.execute("SELECT * FROM accounts").fetchall()
    assert len(accs) == 2
    assert {a["id"] for a in accs} == {"acc-1", "acc-2"}

    # investments com value calculado (qty * price)
    invs = repo._conn.execute("SELECT * FROM investments").fetchall()
    assert len(invs) == 1
    assert invs[0]["value"] == 60.0

    # rodar de novo no mesmo dia = idempotente (não duplica)
    sync_weekly(client=client, repo=repo)
    rows = repo._conn.execute("SELECT * FROM snapshots").fetchall()
    assert len(rows) == 3


def make_client():
    return PluggyClient(
        client_id="id",
        client_secret="secret",
        settings=Settings(pluggy_client_id="id", pluggy_client_secret="secret"),
    )


@pytest.mark.parametrize("exc", [requests.HTTPError, requests.ConnectionError])
def test_auth_erro_vira_pluggy_error(mocker, exc):
    mocker.patch("requests.post", side_effect=exc("boom"))
    with pytest.raises(PluggyError):
        make_client()._authenticate()


def test_auth_http_error_inclui_status(mocker):
    resp = mocker.Mock(status_code=401, text="unauthorized")
    resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    mocker.patch("requests.post", return_value=resp)
    with pytest.raises(PluggyError, match="401"):
        make_client()._authenticate()


def test_get_http_error_vira_pluggy_error(mocker):
    client = make_client()
    client._token = "tok"  # pula auth
    client._token_expiry = 1e12
    resp = mocker.Mock(status_code=404)
    resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    mocker.patch("requests.get", return_value=resp)
    with pytest.raises(PluggyError, match="404"):
        client._get("/items/x")


def test_get_sucesso_retorna_json(mocker):
    client = make_client()
    client._token = "tok"
    client._token_expiry = 1e12
    resp = mocker.Mock(status_code=200)
    resp.json.return_value = {"results": [1, 2, 3]}
    mocker.patch("requests.get", return_value=resp)
    assert client._get("/items/x") == {"results": [1, 2, 3]}


@pytest.mark.parametrize("exc", [requests.ConnectionError, requests.Timeout])
def test_get_network_error_vira_pluggy_error(mocker, exc):
    client = make_client()
    client._token = "tok"
    client._token_expiry = 1e12
    mocker.patch("requests.get", side_effect=exc("boom"))
    with pytest.raises(PluggyError, match="Falha de rede"):
        client._get("/items/x")


# def test_snapshot_includes_investments(monkeypatch, fake_repo, fake_client):
#     # client retorna 1 conta + 1 investimento; repo falso captura save_snapshot_row
#     sync_weekly(client=fake_client, repo=fake_repo)
#     rows = fake_repo.snapshot_rows
#     cats = {r.category for r in rows}
#     assert "SECURITY" in cats  # falha ruidosamente se investimentos sumirem


# def test_snapshot_includes_investments(fake_client, fake_repo):
#     sync_weekly(client=fake_client, repo=fake_repo)
#     rows = fake_repo.snapshot_rows
#     cats = {r.category for r in rows}
#     assert "SECURITY" in cats, "investimentos sumiram do snapshot"
#     inv_row = next(r for r in rows if r.category == "SECURITY")
#     assert inv_row.acc_type == "investment"
#     assert inv_row.amount == 11720.42   # balance, não value/cotas


def test_snapshot_includes_investments():
    client = FakeClient(
        investments=[
            {
                "id": "i1",
                "name": "PGBL",
                "type": "SECURITY",
                "balance": 11720.42,
                "quantity": None,
                "price": None,
                "value": 3.6,
            },
        ],
    )
    repo = SnapshotRepository()
    sync_weekly(client=client, repo=repo)

    rows = repo._conn.execute("SELECT * FROM snapshots WHERE category = 'SECURITY'").fetchall()
    assert len(rows) == 1
    assert rows[0]["amount"] == 11720.42  # balance, não cotas
    assert rows[0]["account_type"] == "investment"
    investment = repo._conn.execute("SELECT value FROM investments WHERE id = 'i1'").fetchone()
    assert investment["value"] == 11720.42
