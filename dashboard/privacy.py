import streamlit as st


def _update_privacy_state() -> None:
    st.session_state["privacy_enabled"] = st.session_state["hide_values"]


def render_privacy_toggle() -> None:
    st.session_state.setdefault(
        "privacy_enabled",
        st.session_state.get("hide_values", False),
    )
    st.sidebar.toggle(
        "👁️ Modo Privacidade",
        key="hide_values",
        on_change=_update_privacy_state,
        persist_state="session",
    )
    if st.session_state["privacy_enabled"]:
        st.markdown(
            """
            <style>
            [data-testid="stMetricValue"],
            [data-testid="stDataFrame"] {
                filter: blur(8px);
                user-select: none;
                transition: filter 0.2s ease-in-out;
            }
            [data-testid="stMetricValue"]:hover,
            [data-testid="stDataFrame"]:hover {
                filter: blur(0px);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
