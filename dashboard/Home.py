import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import streamlit as st
import altair as alt

from app.core.database import get_connection
from dashboard.data import prepare_snapshot_data


st.set_page_config(page_title="OpenWealth", page_icon="📊", layout="wide")

with get_connection() as conn:
    rows = conn.execute(
        "SELECT * FROM snapshots ORDER BY snapshot_date"
    ).fetchall()
    summary = prepare_snapshot_data(rows)


if summary.snapshots.empty:
    st.warning("Nenhum snapshot ainda. Rode o sync: python main.py")
    st.stop()

st.title("📊 OpenWealth")
returns = summary.returns
col1, col2, col3 = st.columns(3)
col1.metric("Patrimônio", f"R$ {summary.total:,.2f}")
col2.metric(
    "Rentabilidade 30d",
    f"{returns['return_30d']:+.2%}" if returns["return_30d"] is not None else "—",
)
col3.metric(
    "Rentabilidade YTD",
    f"{returns['return_ytd']:+.2%}" if returns["return_ytd"] is not None else "—",
)

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Evolução Patrimonial")
    evolucao_chart = (
        alt.Chart(summary.evolution)
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
    st.altair_chart(evolucao_chart, width="stretch")

with chart_col2:
    st.subheader("Concentração por instituição")
    institutions_pct = summary.institutions_pct
    pct_fmt = institutions_pct["pct"].map("{:.1%}".format)
    st.dataframe(
        institutions_pct.assign(pct=pct_fmt),
        hide_index=True,
        width="stretch",
    )

    top_col, hhi_col = st.columns(2)
    if institutions_pct.empty:
        top_col.metric("Top instituição", "—")
    else:
        top_institution = institutions_pct.iloc[0]
        top_col.metric(
            "Top instituição",
            top_institution["institution"],
            f"{top_institution['pct']:.1%}",
        )
    hhi_col.metric(
        "Concentração (HHI)",
        f"{summary.hhi:.3f}" if summary.hhi is not None else "—",
    )

    if not institutions_pct.empty:
        st.bar_chart(
            institutions_pct,
            x="institution",
            y="pct",
            width="stretch",
        )
