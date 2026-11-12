from app.services.sync import sync_weekly


class FakeClient:
    def get_items(self):
        return [{"id": "item1", "institution": "Banco X"}]

    def get_accounts(self, item_id):
        return [{"id": "a1", "name": "Corrente", "type": "CHECKING", "balance": 100.0}]

    def get_investments(self, item_id):
        return [{"id": "i1", "name": "PETR4", "type": "stock", "quantity": 10, "price": 30.0}]


class FakeRepo:
    def __init__(self):
        self.rows, self.accounts, self.investments, self.committed = [], [], [], False

    def snapshot_exists(self, d, inst): return False
    def save_snapshot_row(self, *a): self.rows.append(a)
    def upsert_account(self, acc, item_id, d): self.accounts.append((acc, item_id))
    def upsert_investment(self, inv, item_id, d): self.investments.append((inv, item_id))
    def commit(self): self.committed = True


def test_sync_flows_through_dependencies():
    repo = FakeRepo()
    sync_weekly(client=FakeClient(), repo=repo)

    assert len(repo.rows) == 1
    assert repo.rows[0][4] == "banco"          # categoria mapeada
    assert repo.investments[0][0]["id"] == "i1"
    assert repo.committed


def test_sync_skips_existing_snapshot():
    repo = FakeRepo()
    repo.snapshot_exists = lambda d, inst: True
    sync_weekly(client=FakeClient(), repo=repo)
    assert repo.rows == []
    assert repo.accounts == [] and repo.investments == []
