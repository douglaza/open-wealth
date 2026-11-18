import os
import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

st.set_page_config(
    page_title="Bens e Dívidas - Open Wealth",
    page_icon="🏛️",
    layout="wide",
)

st.title("🏛️ Gestão de Bens e Dívidas")
st.caption(
    "Cadastre manualmente bens (imóveis, veículos) e passivos "
    "(financiamentos, empréstimos) não integrados via Open Finance."
)


def fetch_positions(pos_type: str | None = None) -> list[dict]:
    params = {"type": pos_type} if pos_type else {}
    try:
        res = requests.get(f"{API_URL}/manual-positions", params=params, timeout=5)
        if res.status_code == 200:
            return res.json()
    except requests.RequestException:
        st.error("Não foi possível conectar à API FastAPI. Verifique se o servidor está rodando.")
    return []


def fetch_totals() -> dict:
    try:
        res = requests.get(f"{API_URL}/manual-positions/totals", timeout=5)
        if res.status_code == 200:
            return res.json()
    except requests.RequestException:
        pass
    return {"assets": 0.0, "liabilities": 0.0, "net": 0.0}


# --- Cards de Resumo ---
totals = fetch_totals()
col1, col2, col3 = st.columns(3)
col1.metric("Total de Ativos Manuais", f"R$ {totals['assets']:,.2f}")
col2.metric("Total de Dívidas / Passivos", f"R$ {totals['liabilities']:,.2f}")
col3.metric(
    "Patrimônio Líquido Manual",
    f"R$ {totals['net']:,.2f}",
    delta=f"R$ {totals['net']:,.2f}",
)

st.divider()

tab_list, tab_new = st.tabs(["📋 Posições Cadastradas", "➕ Novo Lançamento"])

with tab_list:
    filter_type = st.selectbox(
        "Filtrar por tipo:",
        ["Todos", "Apenas Ativos (ASSET)", "Apenas Passivos (LIABILITY)"],
    )

    type_param = None
    if filter_type == "Apenas Ativos (ASSET)":
        type_param = "ASSET"
    elif filter_type == "Apenas Passivos (LIABILITY)":
        type_param = "LIABILITY"

    positions = fetch_positions(type_param)

    if positions:
        df = pd.DataFrame(positions)
        df_display = df.rename(
            columns={
                "id": "ID",
                "name": "Nome",
                "type": "Tipo",
                "institution": "Instituição",
                "category": "Categoria",
                "amount": "Valor (R$)",
                "updated_at": "Última Atualização",
            }
        )
        df_display["Valor (R$)"] = df_display["Valor (R$)"].apply(lambda x: f"R$ {x:,.2f}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.subheader("Excluir Posição")
        col_del, col_btn = st.columns([3, 1])
        with col_del:
            selected_id = st.selectbox(
                "Selecione o item para remover:",
                options=[p["id"] for p in positions],
                format_func=lambda x: next(
                    (
                        f"ID {p['id']} - {p['name']} ({p['type']}: R$ {p['amount']:,.2f})"
                        for p in positions
                        if p["id"] == x
                    ),
                    str(x),
                ),
            )
        with col_btn:
            st.write("")
            st.write("")
            if st.button("🗑️ Excluir", type="secondary"):
                del_res = requests.delete(f"{API_URL}/manual-positions/{selected_id}", timeout=5)
                if del_res.status_code == 200:
                    st.success("Posição excluída com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao excluir posição.")
    else:
        st.info("Nenhuma posição manual cadastrada ainda.")

with tab_new:
    st.subheader("Cadastrar Ativo ou Passivo")
    with st.form("form_manual_position", clear_on_submit=True):
        f_name = st.text_input(
            "Nome do Ativo ou Dívida*",
            placeholder="Ex: Financiamento Imobiliário Caixa, Apartamento Moema",
        )
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            f_type = st.selectbox(
                "Tipo*",
                options=["ASSET", "LIABILITY"],
                format_func=lambda x: (
                    "Ativo / Bem (ASSET)" if x == "ASSET" else "Passivo / Dívida (LIABILITY)"
                ),
            )
            f_institution = st.text_input(
                "Instituição*",
                placeholder="Ex: Caixa Econômica, Próprio, Santander",
            )
        with col_f2:
            f_category = st.selectbox(
                "Categoria*",
                options=[
                    "IMÓVEL",
                    "VEÍCULO",
                    "FINANCIAMENTO",
                    "EMPRÉSTIMO",
                    "OUTROS",
                ],
            )
            f_amount = st.number_input(
                "Valor em R$*",
                min_value=0.0,
                step=1000.0,
                format="%.2f",
                help="Para passivos, insira o saldo devedor atual.",
            )

        submitted = st.form_submit_button("💾 Salvar Posição", type="primary")

        if submitted:
            if not f_name or not f_institution:
                st.error("Por favor, preencha os campos obrigatórios (*).")
            else:
                payload = {
                    "name": f_name.strip(),
                    "type": f_type,
                    "institution": f_institution.strip(),
                    "category": f_category,
                    "amount": float(f_amount),
                }
                res = requests.post(f"{API_URL}/manual-positions", json=payload, timeout=5)
                if res.status_code == 201:
                    st.success(f"'{f_name}' cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.error(f"Erro ao salvar: {res.text}")
