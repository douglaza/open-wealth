import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import altair as alt

from app.core.database import get_connection
from dashboard.data import prepare_snapshot_data


st.set_page_config(page_title="OpenWealth", page_icon="📊", layout="wide")

with get_connection() as conn:
    rows = conn.execute(
        "SELECT * FROM snapshots ORDER BY snapshot_date"
    ).fetchall()
    df, patrimonio_atual, evolucao, por_instituicao = prepare_snapshot_data(rows)


if df.empty:
    st.warning("Nenhum snapshot ainda. Rode o sync: python main.py")
    st.stop()

st.title("📊 OpenWealth")
st.metric("Patrimônio Total", f"R$ {patrimonio_atual:,.2f}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Evolução Patrimonial")
    evolucao_chart = (
        alt.Chart(evolucao)
        .mark_line(point=True)
        .encode(
            x=alt.X("snapshot_date:T", title="Data"),
            y=alt.Y("amount:Q", title="Patrimônio (R$)", axis=alt.Axis(format=",.0f")),
            tooltip=[
                alt.Tooltip("snapshot_date:T", title="Data"),
                alt.Tooltip("amount:Q", title="Patrimônio", format=",.2f"),
            ],
        )
    )
    st.altair_chart(
        evolucao_chart,
        alt="Evolução do patrimônio total por data",
    )

with col2:
    st.subheader("Por Instituição")
    instituicao_chart = (
        alt.Chart(por_instituicao)
        .mark_bar()
        .encode(
            x=alt.X("amount:Q", title="Patrimônio (R$)", axis=alt.Axis(format=",.0f")),
            y=alt.Y("account_type:N", title=None, sort="-x"),
            tooltip=[
                alt.Tooltip("institution:N", title="Instituição"),
                alt.Tooltip("amount:Q", title="Patrimônio", format=",.2f"),
            ],
        )
    )
    st.altair_chart(
        instituicao_chart,
        alt="Patrimônio por instituição na captura mais recente",
    )
