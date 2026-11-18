import inspect
from datetime import datetime, timedelta, timezone

from app.domain.insights import PortfolioContext


async def _resolve(val_or_coro):
    if inspect.isawaitable(val_or_coro):
        return await val_or_coro
    return val_or_coro


class ContextBuilder:
    def __init__(self, snapshot_repo, manual_position_repo):
        self.snapshot_repo = snapshot_repo
        self.manual_repo = manual_position_repo

    async def build_context(self) -> PortfolioContext:
        agora = datetime.now(timezone.utc)
        data_90d = (agora - timedelta(days=90)).strftime("%Y-%m-%d")

        # 1. Recupera snapshots e posições (compatível com sync e async)
        ultimo_snapshot = await _resolve(self.snapshot_repo.get_latest())

        # Histórico de 90 dias
        snapshot_antigo = None
        if hasattr(self.snapshot_repo, "get_closest_to"):
            snapshot_antigo = await _resolve(self.snapshot_repo.get_closest_to(data_90d))
        elif hasattr(self.snapshot_repo, "get_between"):
            anteriores = await _resolve(self.snapshot_repo.get_between(data_90d, None))
            if anteriores:
                snapshot_antigo = anteriores[0]

        total_atual = (
            float(getattr(ultimo_snapshot, "total", getattr(ultimo_snapshot, "total_value", 0.0)))
            if ultimo_snapshot
            else 0.0
        )
        total_antigo = (
            float(
                getattr(
                    snapshot_antigo, "total", getattr(snapshot_antigo, "total_value", total_atual)
                )
            )
            if snapshot_antigo
            else total_atual
        )

        # 2. Variação patrimonial dos últimos 90 dias
        if total_antigo > 0:
            variacao_90d = round(((total_atual - total_antigo) / total_antigo) * 100, 2)
        else:
            variacao_90d = 0.0

        # 3. Posições e classes
        posicoes = getattr(ultimo_snapshot, "positions", []) if ultimo_snapshot else []
        if hasattr(self.snapshot_repo, "get_current_positions"):
            posicoes = await _resolve(self.snapshot_repo.get_current_positions()) or posicoes

        por_custodiante: dict[str, float] = {}
        total_investido = 0.0
        total_rv = 0.0
        total_rf = 0.0

        termos_rv = [
            "ação",
            "ações",
            "acao",
            "acoes",
            "stock",
            "fii",
            "etf",
            "variável",
            "variavel",
        ]

        for pos in posicoes:
            valor = float(getattr(pos, "value", 0.0) or getattr(pos, "amount", 0.0))
            custodiante = getattr(pos, "institution", None) or "Outros"
            por_custodiante[custodiante] = por_custodiante.get(custodiante, 0.0) + valor
            total_investido += valor

            # Detecção robusta por tipo, categoria e nome
            tipo = str(getattr(pos, "type", "") or "").lower()
            categoria = str(getattr(pos, "category", "") or "").lower()
            nome = str(getattr(pos, "name", "") or "").lower()

            termos_rv = [
                "equity",
                "stock",
                "ação",
                "acoes",
                "acao",
                "fii",
                "etf",
                "variável",
                "variavel",
            ]
            is_rv = any(t in tipo or t in categoria for t in termos_rv) or (
                "ações" in nome or "fia" in nome
            )

            if is_rv:
                total_rv += valor
            else:
                total_rf += valor

        maior_custodiante = "Nenhum"
        concentracao_pct = 0.0
        if por_custodiante and total_investido > 0:
            maior_custodiante, maior_valor = max(por_custodiante.items(), key=lambda x: x[1])
            concentracao_pct = round((maior_valor / total_investido) * 100, 1)

        exp_rv = round((total_rv / total_investido) * 100, 1) if total_investido > 0 else 0.0
        exp_rf = round((total_rf / total_investido) * 100, 1) if total_investido > 0 else 0.0

        # 4. Passivos
        total_passivo = 0.0
        if hasattr(self.manual_repo, "get_totals"):
            totals = await _resolve(self.manual_repo.get_totals())
            total_passivo = float(totals.get("liabilities", 0.0))
        elif hasattr(self.manual_repo, "get_active_liabilities"):
            passivos = await _resolve(self.manual_repo.get_active_liabilities())
            total_passivo = sum(
                float(getattr(p, "amount", getattr(p, "value", 0.0))) for p in passivos
            )

        return PortfolioContext(
            total_patrimonio=total_atual,
            variacao_90d_pct=variacao_90d,
            maior_custodiante=maior_custodiante,
            concentracao_maior_custodiante_pct=concentracao_pct,
            exposicao_renda_variavel_pct=exp_rv,
            exposicao_renda_fixa_pct=exp_rf,
            passivo_total=total_passivo,
        )
