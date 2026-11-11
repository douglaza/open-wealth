import streamlit as st
from app.core.database import get_connection


def render():
    st.header("💰 Patrimônio Consolidado")
    conn = get_connection()

    total = conn.execute(
        "SELECT SUM(amount) FROM snapshots WHERE snapshot_date = "
        "(SELECT MAX(snapshot_date) FROM snapshots)"
    ).fetchone()[0] or 0
    st.metric("Patrimônio Total", f"R$ {total:,.2f}")

    por_inst = conn.execute("""
        SELECT institution, SUM(amount) AS total FROM snapshots
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM snapshots)
        GROUP BY institution ORDER BY total DESC
    """).fetchall()

    st.subheader("Por Instituição")
    if por_inst:
        st.bar_chart({r["institution"]: r["total"] for r in por_inst})
        st.dataframe([dict(r) for r in por_inst], use_container_width=True)
    else:
        st.info("Nenhum snapshot ainda. Execute um sync para popular os dados.")
