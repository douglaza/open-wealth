import argparse
from datetime import date, timedelta

from app.core.database import get_connection
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.historico import (
    evolucao_patrimonial,
    evolucao_mensal,
    crescimento_acumulado,
)


def _moeda(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _imprimir(titulo: str, datas: list[str], valores: list[float], fmt) -> None:
    print(f"\n{titulo}")
    print("-" * len(titulo))
    if not datas:
        print("(sem dados)")
        return
    for d, v in zip(datas, valores):
        print(f"  {d:<10} {fmt(v)}")


def _snapshots_todos() -> list:
    # intervalo aberto: pega tudo que existe
    with get_connection() as conn:
        repo = SnapshotRepository(conn)
        return repo.get_between(date.min, date.today() + timedelta(days=1))


def cmd_historico(args) -> None:
    snapshots = _snapshots_todos()

    if args.granularidade == "diaria":
        serie = evolucao_patrimonial(snapshots)
        _imprimir("Evolução do patrimônio", serie.datas, serie.valores, _moeda)
    elif args.granularidade == "mensal":
        serie = evolucao_mensal(snapshots)
        _imprimir("Evolução mensal do patrimônio", serie.datas, serie.valores, _moeda)
    else:
        serie = crescimento_acumulado(snapshots)
        _imprimir("Crescimento acumulado", serie.datas, serie.valores, lambda v: f"{v:+.2%}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="open-wealth")
    sub = parser.add_subparsers(dest="comando", required=True)

    hist = sub.add_parser("historico", help="Evolução do patrimônio ao longo do tempo")
    hist.add_argument("-g", "--granularidade",
                      choices=["diaria", "mensal", "acumulado"], default="mensal")
    hist.set_defaults(func=cmd_historico)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
