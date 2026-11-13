import sqlite3
from datetime import date

import pytest

from app.domain.models import Position, Snapshot
from app.repositories.snapshot_repository import SnapshotRepository


def _snap(d: date, inst: str = "XP", amount: float = 100.0) -> Snapshot:
    return Snapshot(
        snapshot_date=d,
        positions=[Position(
            institution=inst, account_type="broker",
            asset_name="ITSA4", category="Ações", amount=amount,
        )],
    )


class TestSaveAll:
    def test_insere_e_ler_de_volta(self, repo):
        repo.save_all([_snap(date(2025, 1, 1))])
        snaps = repo.get_all()
        assert len(snaps) == 1
        assert snaps[0].snapshot_date == date(2025, 1, 1)
        assert snaps[0].positions[0].amount == 100.0

    def test_upsert_mesma_data_nao_duplica(self, repo):
        """Linhas 40-50: save_all apaga posições da data antes de inserir."""
        repo.save_all([_snap(date(2025, 1, 1), amount=100.0)])
        repo.save_all([_snap(date(2025, 1, 1), amount=250.0)])

        snaps = repo.get_all()
        assert len(snaps) == 1  # não criou segundo snapshot
        assert snaps[0].positions[0].amount == 250.0  # sobrescreveu

    def test_upsert_nao_apaga_outras_datas(self, repo):
        repo.save_all([_snap(date(2025, 1, 1))])
        repo.save_all([_snap(date(2025, 1, 2))])
        assert len(repo.get_all()) == 2

    def test_rollback_em_erro(self, repo):
        original = _snap(date(2025, 1, 1), amount=100.0)
        repo.save_all([original])
        antes = repo._conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]

        # Simula dados inválidos na fronteira do banco para falhar após o DELETE.
        invalid = Snapshot.model_construct(
            snapshot_date=date(2025, 1, 1),
            positions=[
                Position.model_construct(
                    institution="XP",
                    account_type="broker",
                    asset_name="ITSA4",
                    category="Ações",
                    amount=None,
                ),
            ],
        )
        with pytest.raises(sqlite3.IntegrityError):
            repo.save_all([invalid])

        # O rollback restaura a linha apagada antes da falha de inserção.
        snapshots = repo.get_all()
        assert len(snapshots) == antes == 1
        assert snapshots[0].snapshot_date == original.snapshot_date
        assert snapshots[0].positions[0].amount == 100.0


class TestUpsertsDadosCruos:
    """Linhas ~170-210: upsert_item / account / investment."""

    def test_upsert_item_insere_e_atualiza(self, repo):
        d = date(2025, 1, 1)
        repo.upsert_item({"id": "i1", "connector": {"name": "XP"}}, d)
        repo.upsert_item({"id": "i1", "connector": {"name": "XP"}}, date(2025, 1, 2))

        row = repo._conn.execute("SELECT * FROM items WHERE id='i1'").fetchone()
        assert dict(row)["updated_at"] == "2025-01-02"  # atualizou, não duplicou

    def test_upsert_account(self, repo):
        repo.upsert_item({"id": "i1", "connector": {"name": "XP"}}, "2025-01-01")
        repo.upsert_account(
            {"id": "a1", "name": "Conta XP", "type": "broker", "balance": 500},
            item_id="i1", snapshot_date="2025-01-01",
        )
        # atualização de saldo
        repo.upsert_account(
            {"id": "a1", "balance": 750},
            item_id="i1", snapshot_date="2025-01-02",
        )
        row = dict(repo._conn.execute("SELECT * FROM accounts WHERE id='a1'").fetchone())
        assert row["balance"] == 750
        assert row["name"] == "Conta XP"  # ON CONFLICT só sobrescreve o que veio

    def test_upsert_investment_calcula_value(self, repo):
        repo.upsert_item({"id": "i1", "connector": {"name": "XP"}}, "2025-01-01")
        repo.upsert_investment(
            {"id": "v1", "name": "HGLG11", "quantity": 10, "price": 160.0},
            item_id="i1", snapshot_date="2025-01-01",
        )
        row = dict(repo._conn.execute("SELECT * FROM investments WHERE id='v1'").fetchone())
        assert row["value"] == 1600.0

    def test_upsert_investment_none_vira_zero(self, repo):
        """quantity/price ausentes ou None não podem quebrar nem gerar None em value."""
        repo.upsert_item({"id": "i1", "connector": {"name": "XP"}}, "2025-01-01")
        repo.upsert_investment(
            {"id": "v2", "quantity": None, "price": None},
            item_id="i1", snapshot_date="2025-01-01",
        )
        row = dict(repo._conn.execute("SELECT * FROM investments WHERE id='v2'").fetchone())
        assert row["value"] == 0

    def test_upsert_snapshot_comita_tudo_ou_nada(self, repo):
        repo.upsert_item({"id": "i1", "connector": {"name": "X"}}, date(2025, 1, 1))
        repo._conn.commit()
        with pytest.raises(KeyError):
            repo.upsert_snapshot(
                [
                    {"id": "i1", "connector": {"name": "Atualizado"}},
                    {},
                ],
                date(2025, 1, 2),
            )

        # rollback: updated_at do item NÃO mudou para 2025-01-02
        row = dict(repo._conn.execute("SELECT * FROM items WHERE id='i1'").fetchone())
        assert row["updated_at"] == "2025-01-01"


class TestMigrateSchema:
    """Linhas ~265-275: migração idempotente para bancos antigos."""

    def test_banco_sem_updated_at_recebe_coluna(self, tmp_path):
        # simula banco "antigo": schema de items sem updated_at
        conn = sqlite3.connect(tmp_path / "legacy.db")
        conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, institution TEXT)")
        conn.execute("INSERT INTO items VALUES ('i1', 'XP')")
        conn.commit()
        conn.close()

        # instanciar o repo sobre esse banco dispara _migrate_schema
        repo = SnapshotRepository(sqlite3.connect(tmp_path / "legacy.db"))
        cols = {r[1] for r in repo._conn.execute("PRAGMA table_info(items)")}
        assert "updated_at" in cols
        # dado pré-existente preservado
        assert repo._conn.execute("SELECT institution FROM items").fetchone()[0] == "XP"

    def test_rodar_migracaoDuasVezes_nao_quebra(self, repo):
        cols1 = {r[1] for r in repo._conn.execute("PRAGMA table_info(items)")}
        repo._migrate_schema()
        cols2 = {r[1] for r in repo._conn.execute("PRAGMA table_info(items)")}
        assert cols1 == cols2  # idempotente
