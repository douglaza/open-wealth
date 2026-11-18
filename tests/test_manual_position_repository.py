"""Testes unitários para o repositório de posições manuais."""

from app.domain.models import ManualPosition
from app.repositories.manual_position_repository import ManualPositionRepository


def test_repository_lifecycle_e_totais(db_conn):
    # Cobre instanciação padrão (sem conn) usando get_connection()
    repo_default = ManualPositionRepository()
    assert repo_default._conn is not None

    repo = ManualPositionRepository(db_conn)

    # Estado inicial vazio
    assert repo.list_all() == []
    assert repo.get_by_id(999) is None
    assert repo.delete(999) is False
    assert repo.get_totals() == {"assets": 0.0, "liabilities": 0.0, "net": 0.0}

    # 1. Criação de Ativo (ASSET)
    imovel = repo.save(
        ManualPosition(
            name="Apartamento Jardins",
            type="asset",
            institution="Bens Próprios",
            category="IMOBILIZADO",
            amount=650000.0,
        )
    )
    assert imovel.id is not None
    assert imovel.type == "ASSET"
    assert imovel.updated_at is not None

    # 2. Criação de Passivo (LIABILITY) com data explícita
    financiamento = repo.save(
        ManualPosition(
            name="Financiamento Caixa",
            type="liability",
            institution="Caixa",
            category="FINANCIAMENTO",
            amount=320000.0,
            updated_at="2026-11-17 10:00:00",
        )
    )
    assert financiamento.id is not None
    assert financiamento.type == "LIABILITY"
    assert financiamento.updated_at == "2026-11-17 10:00:00"

    # 3. Listagens e filtros
    todas = repo.list_all()
    assert len(todas) == 2

    ativos = repo.list_by_type("ASSET")
    assert len(ativos) == 1
    assert ativos[0].name == "Apartamento Jardins"

    passivos = repo.list_by_type("liability")
    assert len(passivos) == 1
    assert passivos[0].name == "Financiamento Caixa"

    # 4. Totais
    totais = repo.get_totals()
    assert totais["assets"] == 650000.0
    assert totais["liabilities"] == 320000.0
    assert totais["net"] == 330000.0

    # 5. Atualização
    assert imovel.id is not None
    imovel.amount = 700000.0
    atualizado = repo.save(imovel)
    assert atualizado.amount == 700000.0

    consultado = repo.get_by_id(imovel.id)
    assert consultado is not None
    assert consultado.amount == 700000.0

    # 6. Exclusão
    assert repo.delete(imovel.id) is True
    assert repo.get_by_id(imovel.id) is None
    assert len(repo.list_all()) == 1

    totais_apos_delete = repo.get_totals()
    assert totais_apos_delete["assets"] == 0.0
    assert totais_apos_delete["liabilities"] == 320000.0
    assert totais_apos_delete["net"] == -320000.0
