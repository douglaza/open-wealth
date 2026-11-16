import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from app.core.database import get_connection
from dashboard.data import prepare_snapshot_data


def render():
    st.header("📊 Evolução do Patrimônio")

    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM snapshots ORDER BY snapshot_date").fetchall()
    summary = prepare_snapshot_data(rows)

    if summary.snapshots.empty:
        st.warning("Nenhum snapshot ainda. Rode o sync: python main.py")
        st.stop()

    returns = summary.returns
    c1, c2, c3 = st.columns(3)
    c1.metric("Patrimônio Atual", f"R$ {summary.total:,.2f}")
    c2.metric(
        "Rentabilidade 30d",
        f"{returns['return_30d']:+.2%}" if returns["return_30d"] is not None else "—",
    )
    c3.metric(
        "Rentabilidade YTD",
        f"{returns['return_ytd']:+.2%}" if returns["return_ytd"] is not None else "—",
    )

    st.subheader("Evolução do Patrimônio Total")
    st.line_chart(
        summary.evolution,
        x="snapshot_date",
        y="amount",
        width="stretch",
    )

    st.subheader("Variação por Instituição")
    st.dataframe(summary.institutions_pct, hide_index=True, width="stretch")

render()
