from datetime import date, timedelta

import pytest

from app.core.database import init_db
# from app.models.snapshot import Position, Snapshot
from app.domain.models import Position, Snapshot
from app.repositories.snapshot_repository import SnapshotRepository


@pytest.fixture()
def repo() -> SnapshotRepository:
    return SnapshotRepository()


def _snapshot(d: date, amounts: list[float]) -> Snapshot:
    return Snapshot(snapshot_date=d, positions=[
        Position(institution="Banco X", account_type="conta",
                 asset_name=f"Ativo {i}", category="Conta", amount=a)
        for i, a in enumerate(amounts)
    ])


def test_save_and_get_latest(banco_limpo, repo):
    snap = _snapshot(date.today(), [1000.0, 500.0])
    repo.save(snap)

    loaded = repo.get_latest()
    assert loaded.snapshot_date == snap.snapshot_date
    assert loaded.total == 1500.0
    assert len(loaded.positions) == 2


def test_save_same_day_twice_does_not_duplicate(banco_limpo, repo):
    d = date.today()
    repo.save(_snapshot(d, [100.0]))
    repo.save(_snapshot(d, [200.0, 300.0]))  # upsert

    loaded = repo.get_latest()
    assert loaded.total == 500.0          # não 100+200+300
    assert len(loaded.positions) == 2


def test_get_between_filters_by_period(banco_limpo, repo):
    d1 = date.today() - timedelta(days=10)
    d2 = date.today()
    repo.save(_snapshot(d1, [100.0]))
    repo.save(_snapshot(d2, [200.0]))

    result = repo.get_between(d1, d2)
    assert len(result) == 2
    assert result[0].snapshot_date == d1  # ordenado

    only_recent = repo.get_between(d2, d2)
    assert len(only_recent) == 1 and only_recent[0].total == 200.0


def test_get_latest_sem_dados_retorna_none(repo):  # use a fixture que você já tem
    assert repo.get_latest() is None


def test_main_historico_integrado(repo_com_dados, monkeypatch, capsys):
    """Cobre o parser, subcomandos e dispatch do main()."""
    import app.cli as cli
    monkeypatch.setattr(cli, "get_connection", lambda *a, **kw: repo_com_dados._conn)
    monkeypatch.setattr("sys.argv", ["open-wealth", "historico", "-g", "diaria"])
    cli.main()
    out = capsys.readouterr().out
    assert "Evolução do patrimônio" in out


def test_main_granularidade_default(repo, monkeypatch, capsys):
    """Sem -g, cai em 'mensal' (default) e o parser roda."""
    import app.cli as cli
    monkeypatch.setattr(cli, "get_connection", lambda *a, **kw: repo._conn)
    monkeypatch.setattr("sys.argv", ["open-wealth", "historico"])
    cli.main()
    out = capsys.readouterr().out
    assert "Evolução mensal" in out


def test_save_all_rollback_em_erro(banco_limpo, repo, monkeypatch):
    snap = _snapshot(date.today(), [100.0])

    class _ConnProxy:
        """Delega tudo ao conn real, mas explode no executemany."""
        def __init__(self, conn):
            self._conn = conn

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def executemany(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(repo, "_conn", _ConnProxy(repo._conn))

    with pytest.raises(RuntimeError):
        repo.save_all([snap])

    # garante que o DELETE foi revertido
    assert repo.get_all() == []

def test_upsert_snapshot_rollback_em_erro(banco_limpo, repo):
    repo.upsert_item({"id": "1", "connector": {"name": "Banco X"}}, date(2025, 1, 1))
    repo._conn.commit()

    with pytest.raises(KeyError):
        repo.upsert_snapshot(
            [
                {"id": "1", "connector": {"name": "Banco atualizado"}},
                {},
            ],
            date(2025, 1, 2),
        )

    row = repo._conn.execute(
        "SELECT institution, updated_at FROM items WHERE id = '1'"
    ).fetchone()
    assert row["institution"] == "Banco X"
    assert row["updated_at"] == "2025-01-01"


def test_upsert_account_aceita_date(banco_limpo, repo):
    repo.upsert_snapshot([], date.today())          # garante item de contexto
    repo.upsert_item({"id": "it1"}, date.today())
    repo.upsert_account(
        {"id": "acc1", "balance": 250.0}, item_id="it1",
        snapshot_date=date.today(),                  # <-- date, não str
    )
    row = repo._conn.execute(
        "SELECT balance FROM accounts WHERE id = 'acc1'").fetchone()
    assert row[0] == 250.0


def test_upsert_investment_aceita_date(banco_limpo, repo):
    repo.upsert_item({"id": "it1"}, date.today())
    repo.upsert_investment(
        {"id": "inv1", "quantity": 10, "price": 5.0}, item_id="it1",
        snapshot_date=date.today(),                  # <-- date, não str
    )
    row = repo._conn.execute(
        "SELECT quantity, value FROM investments WHERE id = 'inv1'").fetchone()
    assert row["quantity"] == 10
    assert row["value"] == 50.0
