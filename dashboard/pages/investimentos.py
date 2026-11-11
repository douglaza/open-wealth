import streamlit as st
from app.core.database import get_connection


def render():
    st.header("📈 Investimentos")
    conn = get_connection()

    investments = conn.execute(
        "SELECT name, type, quantity, price, value, updated_at "
        "FROM investments ORDER BY value DESC"
    ).fetchall()

    total = sum(r["value"] or 0 for r in investments)
    st.metric("Total Investido", f"R$ {total:,.2f}")

    if not investments:
        st.info("Nenhum investimento registrado ainda.")
        return

    por_tipo = {}
    for r in investments:
        por_tipo[r["type"] or "outros"] = por_tipo.get(r["type"] or "outros", 0) + (r["value"] or 0)
    st.subheader("Alocação por Tipo")
    st.bar_chart(por_tipo)

    st.dataframe([dict(r) for r in investments], use_container_width=True)
