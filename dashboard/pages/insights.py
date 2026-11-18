import httpx
import streamlit as st

st.set_page_config(page_title="Open Wealth | Assistente IA", page_icon="💡", layout="wide")

st.title("💡 Assistente Patrimonial Inteligente")
st.caption("Insights executivos baseados no contexto consolidado do seu patrimônio.")

API_URL = "http://localhost:8000/api/v1/insights/chat"

# Inicializa estados na sessão
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Olá! Sou seu assistente de patrimônio do Open Wealth. Como posso ajudar com sua carteira hoje?"
            ),
        }
    ]

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None


def set_prompt(text: str):
    st.session_state.pending_prompt = text


# Sugestões rápidas de perguntas com callback
col1, col2, col3 = st.columns(3)
with col1:
    st.button(
        "📊 Como está minha carteira?",
        use_container_width=True,
        on_click=set_prompt,
        args=("Como está minha carteira?",),
    )
with col2:
    st.button(
        "⚠️ Análise de concentração",
        use_container_width=True,
        on_click=set_prompt,
        args=("Onde está minha maior concentração e qual o risco?",),
    )
with col3:
    st.button(
        "📈 Exposição a risco",
        use_container_width=True,
        on_click=set_prompt,
        args=("Qual é minha exposição atual a renda variável versus fixa?",),
    )

# Renderiza histórico de mensagens
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "context" in msg:
            with st.expander("🔍 Ver dados do contexto utilizado"):
                st.json(msg["context"])

# Entrada do chat
chat_input_val = st.chat_input("Pergunte sobre seus investimentos, passivos ou alocação...")

# Captura pergunta ativa (do input digitado ou do botão clicado)
user_query = chat_input_val or st.session_state.pending_prompt

if user_query:
    st.session_state.pending_prompt = None
    st.session_state.messages.append({"role": "user", "content": user_query})

    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        with st.spinner("Analisando métricas da carteira..."):
            try:
                response = httpx.post(API_URL, json={"query": user_query}, timeout=120.0)
                if response.status_code == 200:
                    data = response.json()
                    answer = data["answer"]
                    context_data = data.get("context_used", {})

                    st.markdown(answer)
                    with st.expander("🔍 Ver dados do contexto utilizado"):
                        st.json(context_data)

                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer, "context": context_data}
                    )
                else:
                    st.error(f"Erro na API ({response.status_code}): {response.text}")
            except Exception as e:
                st.error(f"Não foi possível conectar à API do Open Wealth: {e}")
    st.rerun()
