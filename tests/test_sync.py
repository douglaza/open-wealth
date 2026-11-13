import pytest

from datetime import date
from app.services.sync import sync_weekly, _map_category
from app.repositories.snapshot_repository import SnapshotRepository


class FakeClient:
    """Imita a interface usada pelo sync_weekly."""

    DEFAULT_ITEM = {"id": "item-1", "connector": {"name": "Banco Falso"}}
    DEFAULT_ACCOUNTS = [
        {"id": "acc-1", "name": "Corrente", "type": "checking", "balance": 100.0, "currency": "BRL"},
    ]
    DEFAULT_INVESTMENTS = [
        {"id": "i1", "name": "CDB", "type": "banco", "quantity": 1.0, "price": 50.0},
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


class ExplodingClient(FakeClient):
    def get_item(self):
        raise RuntimeError("API fora do ar")



def test_sync_weekly_com_sqlite_real(tmp_db, mocker):
    mocker.patch(
        "app.services.sync._map_category",
        return_value="Conta",
    )
    client = FakeClient(
        item={"id": "item-1", "connector": {"name": "Banco X"}},
        accounts=[
            {"id": "acc-1", "name": "Corrente", "type": "CHECKING", "balance": 1000.0, "currency": "BRL"},
            {"id": "acc-2", "name": "Poupança", "type": "SAVINGS", "balance": 500.0, "currency": "BRL"},
        ],
        investments=[
            {"id": "inv-1", "name": "Tesouro IPCA", "type": "fixed_income", "quantity": 2.0, "price": 100.0},
        ],
    )
    repo = SnapshotRepository()

    sync_weekly(client=client, repo=repo)

    # snapshots gravados
    rows = repo._conn.execute("SELECT * FROM snapshots").fetchall()
    assert len(rows) == 2
    total = sum(r["amount"] for r in rows)
    assert total == 1500.0
    assert all(r["institution"] == "Banco X" for r in rows)

    # accounts upsertadas
    accs = repo._conn.execute("SELECT * FROM accounts").fetchall()
    assert len(accs) == 2
    assert {a["id"] for a in accs} == {"acc-1", "acc-2"}

    # investments com value calculado (qty * price)
    invs = repo._conn.execute("SELECT * FROM investments").fetchall()
    assert len(invs) == 1
    assert invs[0]["value"] == 200.0

    # rodar de novo no mesmo dia = idempotente (não duplica)
    sync_weekly(client=client, repo=repo)
    rows = repo._conn.execute("SELECT * FROM snapshots").fetchall()
    assert len(rows) == 2


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


def test_sync_client_error_propagates_sem_commit():
    repo = FakeRepo()
    with pytest.raises(RuntimeError):
        sync_weekly(client=ExplodingClient(), repo=repo)
    assert not repo.committed      # nada parcial foi persistido
    assert repo.rows == [] and repo.accounts == []


def test_sync_client_error_propagates_sem_commit():
    repo = FakeRepo()
    with pytest.raises(RuntimeError):
        sync_weekly(client=ExplodingClient(), repo=repo)
    assert ("commit",) not in repo.calls                      # nada parcial persistido
    assert all(op != "upsert_item" for op, *_ in repo.calls)  # nada foi gravado


def test_sync_flows_through_dependencies():
    repo = FakeRepo()
    sync_weekly(client=FakeClient(), repo=repo)

    ops = [op for op, *_ in repo.calls]
    # ordem correta: item primeiro, depois snapshots/accounts, investimentos, commit
    assert ops == [
        "upsert_item",
        "save_snapshot_row",
        "upsert_account",
        "upsert_investment",
        "commit",
    ]


def test_sync_skips_existing_snapshot():
    repo = FakeRepo()
    repo.snapshot_exists = lambda d, inst: True
    sync_weekly(client=FakeClient(), repo=repo)
    assert repo.calls == [("commit",)]  # só commit, nada gravado
