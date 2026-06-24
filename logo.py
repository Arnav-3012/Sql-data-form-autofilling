import os
import streamlit as st

LOGO_PATH = "assets/logo.png"


def show_page_header(back_key: str, back_dest: str):
    """
    Persistent header for every non-landing page.
    Renders: logo, then left-aligned Back button.
    Handles navigation on Back click internally.
    """
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=130)

    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("< Back", key=back_key):
            st.session_state["current_page"] = back_dest
            st.rerun()
