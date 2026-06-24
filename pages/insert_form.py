import streamlit as st
from logger import logger
from logo import show_page_header
from queries import (
    get_bdm_options,
    get_bd_options,
    get_group_name_options,
    search_unmapped_kols,
    check_kol_exists,
    call_set_b2c,
    humanize_db_error,
)

_NEW_GROUP_SENTINEL = "+ Enter a new group name"


def render_insert(engine, cfg):
    show_page_header("back_insert", "b2c_table")

    st.subheader("Add KOL Mapping")

    if "ins_success" in st.session_state:
        st.success(st.session_state.pop("ins_success"))

    # ── Row 1: BD Manager | BD ────────────────────────────────────────────────
    def on_bdm_change():
        for k in ("ins_bd", "ins_kol", "ins_kol_name", "ins_kol_search"):
            st.session_state.pop(k, None)

    bdm_rows = get_bdm_options(engine, cfg)
    if not bdm_rows:
        st.info("No BD Managers found in the database. Please add initial data to tbl_B2CDetails first.")
        return

    bdm_map = {row.nBDMId: row.sBDMEmail for row in bdm_rows}

    col_bdm, col_bd = st.columns(2)
    with col_bdm:
        bdm_id = st.selectbox(
            "BD Manager",
            options=[None] + list(bdm_map.keys()),
            format_func=lambda x: "— select —" if x is None else f"{x} — {bdm_map[x]}",
            key="ins_bdm",
            on_change=on_bdm_change,
        )

    # BD — always visible, disabled when no BD Manager selected
    def on_bd_change():
        for k in ("ins_kol", "ins_kol_name", "ins_kol_search"):
            st.session_state.pop(k, None)

    bd_map = {}
    if bdm_id is None:
        with col_bd:
            st.selectbox(
                "BD",
                options=["Select a BD Manager first"],
                disabled=True,
                key="ins_bd_placeholder",
            )
        bd_id = None
    else:
        bdm_email = bdm_map[bdm_id]
        bd_rows = get_bd_options(engine, cfg, bdm_id)
        if not bd_rows:
            with col_bd:
                st.warning(f"No BDs found under BD Manager {bdm_id}.")
            bd_id = None
        else:
            bd_map = {row.nBDId: row.sBDEmail for row in bd_rows}
            with col_bd:
                bd_id = st.selectbox(
                    "BD",
                    options=[None] + list(bd_map.keys()),
                    format_func=lambda x: "— select —" if x is None else f"{x} — {bd_map[x]}",
                    key="ins_bd",
                    on_change=on_bd_change,
                )

    # ── KOL Search — always visible, disabled until BD Manager and BD selected ─
    kol_search_disabled = bdm_id is None or bd_id is None
    kol_map = {}
    kol_id = None

    if kol_search_disabled:
        st.text_input(
            "Search KOL by ID, email, or name",
            placeholder="Select BD Manager and BD first",
            disabled=True,
            key="ins_kol_search_dis",
        )
    else:
        kol_search = st.text_input(
            "Search KOL by ID, email, or name",
            key="ins_kol_search",
            placeholder="Browse available KOLs, or type to narrow…",
        )
        search_term = kol_search.strip()

        logger.debug(f"KOL search: term={search_term!r}")
        kol_rows = search_unmapped_kols(engine, cfg, search_term)
        logger.debug(f"KOL search returned {len(kol_rows)} row(s)")

        if not kol_rows:
            no_match_label = f"No matches for '{search_term}'" if search_term else "No unmapped KOLs found"
            st.selectbox("Select KOL", options=[no_match_label], disabled=True, key="ins_kol_empty")
        else:
            kol_map = {row.id: (row.email, row.real_name) for row in kol_rows}

            if st.session_state.get("ins_kol") not in kol_map:
                st.session_state.pop("ins_kol", None)
                st.session_state.pop("ins_kol_name", None)

            def on_kol_change():
                st.session_state.pop("ins_kol_name", None)

            kol_id = st.selectbox(
                "Select KOL",
                options=[None] + list(kol_map.keys()),
                format_func=lambda x: "— select —" if x is None else f"{x} — {kol_map[x][0]}",
                key="ins_kol",
                on_change=on_kol_change,
            )

    # ── Row 2: KOL Email (read-only) | KOL Name (editable) — always visible ──
    kol_email = kol_map[kol_id][0] if kol_id and kol_id in kol_map else ""
    kol_name_default = kol_map[kol_id][1] if kol_id and kol_id in kol_map else ""

    col_email, col_name = st.columns(2)
    with col_email:
        st.text_input(
            "KOL Email (from user_info)",
            value=kol_email,
            disabled=True,
            key="ins_kol_email_ro",
        )
    with col_name:
        kol_name = st.text_input(
            "KOL Name",
            value=st.session_state.get("ins_kol_name", kol_name_default),
            key="ins_kol_name",
        )

    # ── Row 3: Group Name (full width) — always visible ───────────────────────
    group_names = get_group_name_options(engine, cfg)
    group_options = [_NEW_GROUP_SENTINEL] + sorted(group_names)

    selected_group = st.selectbox("Group Name", options=group_options, key="ins_group")

    if selected_group == _NEW_GROUP_SENTINEL:
        new_group_input = st.text_input(
            "Enter new group name",
            key="ins_group_new",
            placeholder="e.g. TeamAlpha",
        )
        group_name = new_group_input.strip()
    else:
        group_name = selected_group

    # ── Row 4: Upfront Cost | Commission — always visible ─────────────────────
    col_cost, col_comm = st.columns(2)
    with col_cost:
        upfront_cost = st.number_input(
            "Upfront Cost *",
            min_value=0.0, step=0.01, format="%.2f",
            key="ins_upfront",
        )
    with col_comm:
        commission = st.number_input(
            "Commission (%) *",
            min_value=0.0, step=0.01, format="%.2f",
            key="ins_commission",
        )

    # ── Row 5: Remarks (full width) — always visible ──────────────────────────
    remarks = st.text_input("Remarks", key="ins_remarks")

    # ── Duplicate check, preview, Confirm Add — only after all three selected ─
    all_selected = bdm_id is not None and bd_id is not None and kol_id is not None

    if all_selected:
        bdm_email = bdm_map[bdm_id]
        bd_email = bd_map[bd_id]

        existing = check_kol_exists(engine, cfg, kol_id)
        if existing:
            st.error(
                f"KOL {kol_id} is already mapped to "
                f"BD Manager {existing.nBDMId} ({existing.sBDMEmail}) / "
                f"BD {existing.nBDId} ({existing.sBDEmail}). "
                "A KOL can only have one active mapping. "
                "To reassign, first unmap from the Update / Unmap page."
            )
        else:
            # ── Preview ───────────────────────────────────────────────────────
            st.divider()
            st.markdown("**Preview — record about to be inserted:**")
            st.markdown(
                f"- **KOL ID:** {kol_id}\n"
                f"- **KOL Email:** {kol_email}\n"
                f"- **KOL Name:** {kol_name or '(none)'}\n"
                f"- **BD Manager:** {bdm_id} ({bdm_email})\n"
                f"- **BD:** {bd_id} ({bd_email})\n"
                f"- **Group Name:** {group_name or '(none)'}\n"
                f"- **Upfront Cost:** {upfront_cost:.2f}\n"
                f"- **Commission:** {commission:.2f}%\n"
                f"- **Remarks:** {remarks or '(none)'}"
            )
            st.divider()

            # ── Validation ────────────────────────────────────────────────────
            form_errors = []
            if selected_group == _NEW_GROUP_SENTINEL and not group_name:
                form_errors.append("Please enter a group name.")
            if upfront_cost < 0:
                form_errors.append("Upfront Cost cannot be negative.")
            if commission <= 0:
                form_errors.append("Commission is required and must be greater than 0.")

            if form_errors:
                for msg in form_errors:
                    st.error(msg)
            else:
                if st.button("Confirm Add", type="primary", key="ins_confirm"):
                    new_vals = {
                        "nBDMId": bdm_id, "sBDMEmail": bdm_email,
                        "nBDId": bd_id, "sBDEmail": bd_email,
                        "nKOLId": kol_id, "sKOLName": kol_name, "sKOLEmail": kol_email,
                        "sGroupName": group_name,
                        "nUpFrontCost": upfront_cost, "nCommission": commission,
                        "sRemarks": remarks,
                    }
                    success, err = call_set_b2c(
                        engine, cfg, filter_type=1,
                        bdm_id=bdm_id, bdm_email=bdm_email,
                        bd_id=bd_id, bd_email=bd_email,
                        kol_id=kol_id, kol_name=kol_name, kol_email=kol_email,
                        group_name=group_name, upfront_cost=upfront_cost,
                        commission=commission, remarks=remarks,
                        old_values=None, new_values=new_vals,
                    )
                    if success:
                        st.session_state["ins_success"] = (
                            f"KOL {kol_id} ({kol_name or 'unnamed'}) successfully added under "
                            f"BD {bd_id} ({bd_email}) / BD Manager {bdm_id} ({bdm_email})."
                        )
                        for k in (
                            "ins_bdm", "ins_bd", "ins_kol", "ins_kol_name", "ins_kol_email_ro",
                            "ins_kol_search", "ins_group", "ins_group_new",
                            "ins_upfront", "ins_commission", "ins_remarks",
                        ):
                            st.session_state.pop(k, None)
                        st.rerun()
                    else:
                        st.error(f"Failed to add KOL mapping. {humanize_db_error(err)}")
