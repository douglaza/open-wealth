from datetime import date

# from app.models.snapshot import Snapshot, Position
from app.domain.models import Snapshot, Position


INVESTMENT_TYPES = {"SECURITY", "MUTUAL_FUND", "FIXED_INCOME", "ETF", "EQUITY"}
CAIXA_TYPES = {"BANK"}


def _map_category(acc: dict) -> str:
    """Classifica uma conta Pluggy contra o contrato real do sandbox."""
    t = (acc.get("type") or "").upper()
    if t == "CREDIT":
        return "cartao"
    if t in INVESTMENT_TYPES:
        return "investimento"
    if t in CAIXA_TYPES:
        return "banco"
    return "outros"   # type desconhecido NUNCA vira caixa silenciosamente


def _connector_name(item: dict) -> str:
    connector = item.get("connector") or {}
    return connector.get("name") or "Desconhecido"


def _build_positions(accounts: list, investments: list, institution: str) -> list:
    """Monta positions a partir de contas (balance) e investimentos (value)."""
    positions = []

    # for acc in accounts or []:
    #     balance = acc.get("balance")
    #     positions.append(
    #         Position(
    #             institution=institution,
    #             account_type=acc.get("type") or "account",
    #             asset_name=acc.get("name") or "Conta sem nome",
    #             category=acc.get("subtype") or "cash",
    #             amount=float(balance) if balance is not None else 0.0,
    #         )
    #     )

    for acc in accounts or []:
        category = _map_category(acc)
        if category == "investimento":
            continue  # posição de investimento entra só via get_investments
        balance = acc.get("balance")
        positions.append(Position(
            institution=institution,
            account_type=acc.get("type") or "account",
            asset_name=acc.get("name") or "Conta sem nome",
            category=category,
            amount=float(balance) if balance is not None else 0.0,
        ))

    for inv in investments or []:
        positions.append(
            Position(
                institution=institution,
                account_type="investment",
                asset_name=inv.get("name") or "Investimento sem nome",
                category=inv.get("type") or "investment",
                amount=_investment_amount(inv),
            )
        )


    return positions


def sync_all(client) -> Snapshot:
    """
    Monta o Snapshot de posições.

    Modo Development (sandbox): usa get_item() com o item fixo do .env.
    Modo produção: reativar get_items() no cliente e iterar.
    """
    item = client.get_item()
    institution = _connector_name(item)

    accounts = client.get_accounts(item["id"])
    investments = client.get_investments(item["id"])

    return Snapshot(
        snapshot_date=date.today(),
        positions=_build_positions(accounts, investments, institution),
    )


def get_totals(snapshot: Snapshot) -> dict:
    """Total geral + agregação por instituição."""
    by_institution: dict[str, float] = {}
    for p in snapshot.positions:
        by_institution[p.institution] = (
            by_institution.get(p.institution, 0.0) + p.amount
        )

    return {
        "total": sum(by_institution.values()),
        "by_institution": by_institution,
    }


def _investment_amount(inv: dict) -> float:
    """'balance' é a fonte da verdade. 'value' é QUANTIDADE de cotas — nunca usar.
    'amount' é o valor aplicado; serve como fallback conservador."""
    for k in ("balance", "amount"):
        v = inv.get(k)
        if v is not None:
            return float(v)
    return 0.0


# def _investment_amount(inv: dict) -> float:
#     """Valor de mercado da posição. 'balance' é a fonte da verdade —
#     'value' vem null em vários conectores e 'amount' pode divergir do
#     valor exibido no dashboard (ex.: CDR do sandbox: amount=2500, balance=2000)."""
#     balance = inv.get("balance")
#     if balance is not None:
#         return float(balance)
#     value = inv.get("value")
#     if value is not None:
#         return float(value)
#     qty, price = inv.get("quantity"), inv.get("price")
#     if qty is not None and price is not None:
#         return float(qty) * float(price)
#     return 0.0

