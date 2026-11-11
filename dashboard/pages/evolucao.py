import streamlit as st
from app.core.database import get_connection
from app.services.rentabilidade import rentabilidade_total, rentabilidade_por_instituicao


def render():
    st.header("📊 Evolução do Patrimônio")

    r = rentabilidade_total()
    if "msg" in r:
        st.warning(r["msg"])
    else:
        c1, c2 = st.columns(2)
        c1.metric("Patrimônio Atual", f"R$ {r['valor_atual']:,.2f}")
        c2.metric("Variação", f"{r['variacao_pct']}%",
                  delta=f"R$ {r['variacao_abs']:,.2f}")

    conn = get_connection()
    serie = conn.execute("SELECT * FROM v_evolucao ORDER BY snapshot_date").fetchall()
    if serie:
        st.line_chart({str(row["snapshot_date"]): row["patrimonio_total"] for row in serie})

    st.subheader("Variação por Instituição")
    st.dataframe(rentabilidade_por_instituicao(), use_container_width=True)
