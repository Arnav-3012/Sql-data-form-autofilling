import pandas as pd
import streamlit as st
from logo import show_page_header
from queries import get_b2c_page

_PAGE_SIZE = 25

# Column order matches the office DB: ALTER TABLE columns (sKOLName,
# dCommissionUpdateTime, dLastUpdatedTime) were added last, so they appear at the end.
_DB_COLS = [
    "nBDMId", "sBDMEmail", "nBDId", "sBDEmail",
    "nKOLId", "sKOLEmail", "sGroupName",
    "nUpFrontCost", "nCommission", "sRemarks",
    "sKOLName", "dCommissionUpdateTime", "dLastUpdatedTime",
]
_RENAME = {
    "nBDMId":                "BDM ID",
    "sBDMEmail":             "BDM Email",
    "nBDId":                 "BD ID",
    "sBDEmail":              "BD Email",
    "nKOLId":                "KOL ID",
    "sKOLEmail":             "KOL Email",
    "sGroupName":            "Group",
    "nUpFrontCost":          "Cost",
    "nCommission":           "Commission",
    "sRemarks":              "Remarks",
    "sKOLName":              "KOL Name",
    "dCommissionUpdateTime": "Commission Updated",
    "dLastUpdatedTime":      "Last Updated",
}

# Zebra stripe colors — two close dark tones within the dark theme palette.
_STRIPE_EVEN = "background-color: #0d1117"  # base dark
_STRIPE_ODD  = "background-color: #161b22"  # subtle step lighter


def _zebra(df):
    """Return a Styler with alternating row backgrounds."""
    styles = [
        [_STRIPE_EVEN if i % 2 == 0 else _STRIPE_ODD] * len(df.columns)
        for i in range(len(df))
    ]
    return pd.DataFrame(styles, index=df.index, columns=df.columns)


@st.dialog("Confirm Update")
def _confirm_update_dialog(kol_id, kol_name):
    st.write(f"Update KOL **{kol_name}** (ID: `{kol_id}`)?")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("Yes, Update", type="primary", use_container_width=True):
            st.session_state["current_page"] = "manage_form"
            st.session_state["preselected_kol_id"] = kol_id
            st.rerun()
    with col_no:
        if st.button("Cancel", use_container_width=True):
            # Clear the dataframe selection so the dialog won't reopen.
            st.session_state.pop("b2c_table_select", None)
            st.rerun()


def render_b2c_table(engine, cfg):
    show_page_header("back_b2c", "menu")

    st.subheader("tbl_B2CDetails")

    # ── Add button ────────────────────────────────────────────────────────────
    if st.button("+ Add KOL Mapping", key="b2c_add_btn", type="primary"):
        st.session_state["current_page"] = "insert_form"
        st.rerun()

    # ── Search ────────────────────────────────────────────────────────────────
    def _on_search_change():
        st.session_state["b2c_page_num"] = 1
        st.session_state.pop("b2c_table_select", None)

    st.text_input(
        "Search by KOL ID, email, name, BD, or BD Manager email",
        key="b2c_search",
        on_change=_on_search_change,
        placeholder="Type to filter…",
    )
    raw_search = st.session_state.get("b2c_search", "").strip()
    search_term = raw_search if raw_search else None

    # ── Page state ────────────────────────────────────────────────────────────
    if "b2c_page_num" not in st.session_state:
        st.session_state["b2c_page_num"] = 1
    page_num = st.session_state["b2c_page_num"]

    # ── Query ─────────────────────────────────────────────────────────────────
    rows, total = get_b2c_page(engine, cfg, page_num, _PAGE_SIZE, search_term)
    total_pages = max(1, -(-total // _PAGE_SIZE))

    if page_num > total_pages:
        st.session_state["b2c_page_num"] = total_pages
        page_num = total_pages
        rows, total = get_b2c_page(engine, cfg, page_num, _PAGE_SIZE, search_term)

    # ── Build DataFrame ───────────────────────────────────────────────────────
    if not rows:
        st.info("No records found.")
    else:
        df = pd.DataFrame(rows, columns=_DB_COLS).rename(columns=_RENAME)

        # Pre-round numeric columns so formatting is correct even when
        # column_config doesn't apply to a Styler object (known Streamlit limitation).
        df["Cost"] = pd.to_numeric(df["Cost"], errors="coerce").round(0).astype("Int64")
        df["Commission"] = pd.to_numeric(df["Commission"], errors="coerce").round(2)

        styled = df.style.apply(_zebra, axis=None)

        st.caption("Check a row's checkbox to select it, then confirm to open the Update form.")

        selection = st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="b2c_table_select",
            column_config={
                "Cost": st.column_config.NumberColumn(format="%.0f"),
                "Commission": st.column_config.NumberColumn(format="%.2f"),
            }
        )

        # ── Row selected → open confirmation dialog ───────────────────────────
        # selection.selection.rows is a list of integer indices into df
        # (the current page's DataFrame), so df.iloc[idx] always maps to
        # the exact row the user checked regardless of pagination offset.
        selected_rows = selection.selection.rows
        if selected_rows:
            idx = selected_rows[0]
            selected  = df.iloc[idx]
            kol_id    = int(selected["KOL ID"])
            kol_name  = str(selected["KOL Name"]) if pd.notna(selected["KOL Name"]) else ""
            _confirm_update_dialog(kol_id, kol_name)

    # ── Pagination controls ───────────────────────────────────────────────────
    col_prev, col_info, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("← Prev", key="b2c_prev", disabled=(page_num <= 1), use_container_width=True):
            st.session_state["b2c_page_num"] = page_num - 1
            st.session_state.pop("b2c_table_select", None)
            st.rerun()
    with col_info:
        st.markdown(
            f'<div style="text-align:center;color:#8b949e;font-size:0.84rem;padding:6px 0">'
            f'Page <strong>{page_num}</strong> of <strong>{total_pages}</strong>'
            f'&nbsp;·&nbsp;{total} record{"s" if total != 1 else ""}'
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("Next →", key="b2c_next", disabled=(page_num >= total_pages), use_container_width=True):
            st.session_state["b2c_page_num"] = page_num + 1
            st.session_state.pop("b2c_table_select", None)
            st.rerun()

    st.divider()

    # ── Bottom Update button (no preselected KOL — normal search flow) ────────
    if st.button("Update a KOL Mapping", key="b2c_update_btn"):
        st.session_state["current_page"] = "manage_form"
        st.rerun()
