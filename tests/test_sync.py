import pytest
import requests

from app.core.config import Settings
from app.core.exceptions import PluggyError
from app.integrations.pluggy_client import PluggyClient
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.sync import (
    _get_configured_item_ids,
    _infer_institution,
    sync_weekly,
)


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

    def get_item(self, target_id=None):
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
    def get_item(self, target_id=None):
        raise RuntimeError("API fora do ar")


class PluggyErrorClient(FakeClient):
    def get_item(self, target_id=None):
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


# --- Cobertura de múltiplos itens e inferência de instituição ---


def test_get_configured_item_ids_com_pluggy_item_ids(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "pluggy_item_ids", "id-1, id-2")
    assert _get_configured_item_ids() == ["id-1", "id-2"]


def test_get_configured_item_ids_com_env_item_ids(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "pluggy_item_ids", None)
    monkeypatch.setenv("PLUGGY_ITEM_IDS", "id-a, id-b ")
    assert _get_configured_item_ids() == ["id-a", "id-b"]


def test_get_configured_item_ids_com_pluggy_item_id_singular(monkeypatch):
    mock_settings = type("MockSettings", (), {"pluggy_item_id": "id-single"})()
    monkeypatch.setattr("app.services.sync.settings", mock_settings)
    monkeypatch.delenv("PLUGGY_ITEM_IDS", raising=False)
    assert _get_configured_item_ids() == ["id-single"]


def test_get_configured_item_ids_com_env_item_id_singular(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "pluggy_item_ids", None)
    monkeypatch.delenv("PLUGGY_ITEM_IDS", raising=False)
    monkeypatch.setenv("PLUGGY_ITEM_ID", "id-env-single")
    assert _get_configured_item_ids() == ["id-env-single"]


def test_get_configured_item_ids_vazio(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "pluggy_item_ids", None)
    monkeypatch.delenv("PLUGGY_ITEM_IDS", raising=False)
    monkeypatch.delenv("PLUGGY_ITEM_ID", raising=False)
    assert _get_configured_item_ids() == []


def test_sync_com_client_pluggy_instance(monkeypatch, mocker):
    mocker.patch.object(
        PluggyClient, "get_item", return_value={"id": "id-1", "connector": {"name": "Banco Teste"}}
    )
    mocker.patch.object(PluggyClient, "get_accounts", return_value=[])
    mocker.patch.object(PluggyClient, "get_investments", return_value=[])
    repo = FakeRepo()
    monkeypatch.setattr("app.services.sync._get_configured_item_ids", lambda: ["id-1"])
    sync_weekly(client=PluggyClient(), repo=repo)
    assert ("commit",) in repo.calls


@pytest.mark.parametrize(
    ("acc_name", "expected"),
    [
        ("Conta Itau Unibanco", "Itaú"),
        ("Cartão Personnalite Black", "Itaú"),
        ("Conta C6 Bank", "C6 Bank"),
        ("Conta Nubank", "Nubank"),
        ("Nu Pagamentos", "Nubank"),
        ("BTG Pactual Digital", "BTG Pactual"),
        ("Bradesco Prime", "Bradesco"),
        ("Santander Select", "Santander"),
        ("Banco Inter", "Banco Inter"),
        ("XP Investimentos", "XP Investimentos"),
    ],
)
def test_infer_institution_por_contas(acc_name, expected):
    accs = [{"name": acc_name}]
    assert _infer_institution(accs) == expected


@pytest.mark.parametrize(
    ("inv_name", "expected"),
    [
        ("CDB Itau 100%", "Itaú"),
        ("CDB Banco C6", "C6 Bank"),
        ("Fundo BTG Debentures", "BTG Pactual"),
        ("LCA Bradesco", "Bradesco"),
        ("CDB Santander", "Santander"),
    ],
)
def test_infer_institution_por_investimentos(inv_name, expected):
    accs = [{"name": "Conta Desconhecida"}]
    invs = [{"name": inv_name}]
    assert _infer_institution(accs, invs) == expected


def test_infer_institution_fallback():
    accs = [{"name": "Conta Genérica"}]
    invs = [{"name": "Ativo Genérico"}]
    assert _infer_institution(accs, invs, fallback="FallbackInst") == "FallbackInst"
    assert _infer_institution([]) == "MeuPluggy"


def test_sync_com_item_ids_explicito():
    client = FakeClient()
    repo = FakeRepo()
    sync_weekly(client=client, repo=repo, item_ids=["item-a", "item-b"])
    assert ("commit",) in repo.calls


def test_sync_com_conector_meupluggy_infere_instituicao():
    item = {"id": "item-pluggy", "connector": {"name": "MeuPluggy"}}
    accs = [{"id": "a1", "name": "Conta C6 Bank", "type": "CHECKING", "balance": 200.0}]
    invs = [{"id": "i1", "name": "CDB C6", "type": "FIXED_INCOME", "balance": 300.0}]
    client = FakeClient(item=item, accounts=accs, investments=invs)
    repo = FakeRepo()
    sync_weekly(client=client, repo=repo)
    rows = [call[1] for call in repo.calls if call[0] == "save_snapshot_row"]
    assert len(rows) == 2
    assert all(r[1] == "C6 Bank" for r in rows)


def test_sync_com_instituicao_desconhecida():
    item = {"id": "item-pluggy", "connector": {"name": ""}}
    accs = [{"id": "a1", "name": "Itau", "type": "CHECKING", "balance": 100.0}]
    client = FakeClient(item=item, accounts=accs, investments=[])
    repo = FakeRepo()
    sync_weekly(client=client, repo=repo)
    rows = [call[1] for call in repo.calls if call[0] == "save_snapshot_row"]
    assert rows[0][1] == "Itaú"


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
