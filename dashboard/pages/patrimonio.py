import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.core.database import get_connection
from dashboard.data import prepare_snapshot_data
from dashboard.privacy import render_privacy_toggle


def render():
    st.header("💰 Patrimônio Consolidado")

    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM snapshots ORDER BY snapshot_date").fetchall()
    summary = prepare_snapshot_data(rows)

    if summary.snapshots.empty:
        st.warning("Nenhum snapshot ainda. Rode o sync: python main.py")
        st.stop()

    st.metric("Patrimônio Total", f"R$ {summary.total:,.2f}")

    st.subheader("Por Instituição")
    st.bar_chart(summary.institutions_pct, x="institution", y="amount",
                 width="stretch")
    st.dataframe(summary.institutions, hide_index=True, width="stretch")

    render_privacy_toggle()

render()
