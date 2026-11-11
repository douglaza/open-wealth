import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
from app.core.database import get_connection


st.set_page_config(page_title="OpenWealth", page_icon="📊", layout="wide")

with get_connection() as conn:
    df = pd.read_sql("SELECT * FROM snapshots ORDER BY snapshot_date", conn)

if df.empty:
    st.warning("Nenhum snapshot ainda. Rode o sync: python main.py")
    st.stop()

st.title("📊 OpenWealth")
st.metric("Patrimônio Total", f"R$ {df['amount'].sum():,.2f}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Evolução Patrimonial")
    evolucao = df.groupby("snapshot_date")["amount"].sum()
    st.line_chart(evolucao)

with col2:
    st.subheader("Por Instituição")
    st.bar_chart(df.groupby("institution")["amount"].sum())
