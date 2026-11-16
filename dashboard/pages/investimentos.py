import streamlit as st

from app.core.database import get_connection


def render():
    st.header("📈 Investimentos")

    with get_connection() as conn:
        investments = conn.execute(
            "SELECT name, type, quantity, price, value, updated_at "
            "FROM investments ORDER BY value DESC"
        ).fetchall()

    if not investments:
        st.info("Nenhum investimento registrado ainda.")
        return

    total = sum(r["value"] or 0 for r in investments)
    st.metric("Total Investido", f"R$ {total:,.2f}")

    por_tipo: dict[str, float] = {}
    for r in investments:
        tipo = r["type"] or "outros"
        por_tipo[tipo] = por_tipo.get(tipo, 0) + (r["value"] or 0)

    st.subheader("Alocação por Tipo")
    st.bar_chart(por_tipo, width="stretch")

    st.dataframe([dict(r) for r in investments], hide_index=True, width="stretch")

render()
