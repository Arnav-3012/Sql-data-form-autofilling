import streamlit as st
from logo import show_page_header
from queries import get_all_kol_ids, get_kol_row, call_set_b2c, humanize_db_error


def _render_update(engine, cfg, row):
    st.markdown(
        "Edit the fields below. BD Manager and BD cannot be changed here — "
        "to reassign a KOL to a different BD/BD Manager, unmap first then re-add."
    )

    # Row 1: Upfront Cost | Commission
    col_cost, col_comm = st.columns(2)
    with col_cost:
        upfront_cost = st.number_input(
            "Upfront Cost *",
            value=float(row.nUpFrontCost or 0),
            min_value=0.0, step=0.01, format="%.2f",
            key="upd_upfront",
        )
    with col_comm:
        commission = st.number_input(
            "Commission (%) *",
            value=float(row.nCommission or 0),
            min_value=0.0, step=0.01, format="%.2f",
            key="upd_commission",
        )

    # Row 2: Remarks (full width)
    remarks = st.text_input("Remarks", value=row.sRemarks or "", key="upd_remarks")

    changed = {}
    if upfront_cost != float(row.nUpFrontCost or 0):
        changed["Upfront Cost"] = (row.nUpFrontCost, upfront_cost)
    if commission != float(row.nCommission or 0):
        changed["Commission"] = (row.nCommission, commission)
    if remarks != (row.sRemarks or ""):
        changed["Remarks"] = (row.sRemarks or "(none)", remarks or "(none)")

    if not changed:
        st.info("No changes made yet.")
        return

    form_errors = []
    if "Upfront Cost" in changed and upfront_cost <= 0:
        form_errors.append("Upfront Cost must be greater than 0.")
    if "Commission" in changed and commission <= 0:
        form_errors.append("Commission must be greater than 0.")

    _NUMERIC_PREVIEW = {"Upfront Cost", "Commission"}

    st.divider()
    st.markdown("**Changes preview:**")
    for field, (old, new) in changed.items():
        if field in _NUMERIC_PREVIEW:
            old_fmt = f"{float(old):.2f}" if old is not None else "(none)"
            new_fmt = f"{float(new):.2f}"
            st.markdown(f"- **{field}:** {old_fmt} → {new_fmt}")
        else:
            st.markdown(f"- **{field}:** {old} → {new}")

    if form_errors:
        for msg in form_errors:
            st.error(msg)
        return

    if st.button("Confirm Update", type="primary", key="upd_confirm"):
        old_vals = {
            "nUpFrontCost": row.nUpFrontCost,
            "nCommission": row.nCommission,
            "sRemarks": row.sRemarks,
        }
        new_vals = {
            "nUpFrontCost": upfront_cost,
            "nCommission": commission,
            "sRemarks": remarks,
        }
        success, err = call_set_b2c(
            engine, cfg, filter_type=2,
            bdm_id=row.nBDMId, bdm_email=row.sBDMEmail,
            bd_id=row.nBDId, bd_email=row.sBDEmail,
            kol_id=row.nKOLId, kol_name=row.sKOLName, kol_email=row.sKOLEmail,
            group_name=row.sGroupName,
            upfront_cost=upfront_cost, commission=commission, remarks=remarks,
            old_values=old_vals, new_values=new_vals,
        )
        if success:
            st.session_state["mgmt_success"] = f"KOL {row.nKOLId} updated successfully."
            for k in ("upd_upfront", "upd_commission", "upd_remarks", "mgmt_kol"):
                st.session_state.pop(k, None)
            st.rerun()
        else:
            st.error(f"Failed to update. {humanize_db_error(err)}")


def _render_unmap(engine, cfg, row):
    st.markdown("**This will permanently remove this KOL mapping from the database.**")
    st.markdown(
        f"- **KOL ID:** {row.nKOLId}\n"
        f"- **KOL Name:** {row.sKOLName or '(none)'}\n"
        f"- **BD Manager:** {row.nBDMId} ({row.sBDMEmail})\n"
        f"- **BD:** {row.nBDId} ({row.sBDEmail})\n"
        f"- **Group Name:** {row.sGroupName}\n"
        f"- **Upfront Cost:** {row.nUpFrontCost}\n"
        f"- **Commission:** {row.nCommission}"
    )
    st.warning("This cannot be undone. The row will be permanently deleted from tbl_B2CDetails.")

    if st.button("Confirm Unmap", type="primary", key="unmap_confirm"):
        old_vals = {
            "nBDMId": row.nBDMId, "sBDMEmail": row.sBDMEmail,
            "nBDId": row.nBDId, "sBDEmail": row.sBDEmail,
            "nKOLId": row.nKOLId, "sKOLName": row.sKOLName, "sKOLEmail": row.sKOLEmail,
            "sGroupName": row.sGroupName,
            "nUpFrontCost": row.nUpFrontCost, "nCommission": row.nCommission,
            "sRemarks": row.sRemarks,
        }
        success, err = call_set_b2c(
            engine, cfg, filter_type=3,
            bdm_id=row.nBDMId, bdm_email=row.sBDMEmail,
            bd_id=row.nBDId, bd_email=row.sBDEmail,
            kol_id=row.nKOLId, kol_name=row.sKOLName, kol_email=row.sKOLEmail,
            group_name=row.sGroupName,
            upfront_cost=row.nUpFrontCost, commission=row.nCommission, remarks=row.sRemarks,
            old_values=old_vals, new_values=None,
        )
        if success:
            st.session_state["mgmt_success"] = (
                f"KOL {row.nKOLId} ({row.sKOLName or 'unnamed'}) has been unmapped and permanently removed."
            )
            st.session_state.pop("mgmt_kol", None)
            st.rerun()
        else:
            st.error(f"Failed to unmap. {humanize_db_error(err)}")


def render_manage(engine, cfg):
    show_page_header("back_manage", "b2c_table")

    st.subheader("Update / Unmap KOL")

    if "mgmt_success" in st.session_state:
        st.success(st.session_state.pop("mgmt_success"))

    # Transfer preselected_kol_id → mgmt_kol when arriving from a per-row Update button
    if "preselected_kol_id" in st.session_state:
        for k in ("upd_upfront", "upd_commission", "upd_remarks"):
            st.session_state.pop(k, None)
        st.session_state["mgmt_kol"] = st.session_state.pop("preselected_kol_id")

    kol_ids = get_all_kol_ids(engine, cfg)
    if not kol_ids:
        st.info("No KOL mappings exist yet. Use the Add KOL Mapping page to add one.")
        return

    def on_kol_change():
        for k in ("upd_upfront", "upd_commission", "upd_remarks"):
            st.session_state.pop(k, None)

    kol_id = st.selectbox(
        "Select KOL ID",
        options=[None] + kol_ids,
        format_func=lambda x: "— select —" if x is None else str(x),
        key="mgmt_kol",
        on_change=on_kol_change,
    )
    if kol_id is None:
        st.stop()

    row = get_kol_row(engine, cfg, kol_id)
    if row is None:
        st.error(f"KOL {kol_id} not found. Try refreshing the page.")
        st.stop()

    st.markdown("**Current record:**")
    st.markdown(
        f"- **BD Manager:** {row.nBDMId} ({row.sBDMEmail})\n"
        f"- **BD:** {row.nBDId} ({row.sBDEmail})\n"
        f"- **KOL ID:** {row.nKOLId}\n"
        f"- **KOL Name:** {row.sKOLName or '(none)'}\n"
        f"- **KOL Email:** {row.sKOLEmail}\n"
        f"- **Group Name:** {row.sGroupName}\n"
        f"- **Upfront Cost:** {row.nUpFrontCost}\n"
        f"- **Commission:** {row.nCommission}\n"
        f"- **Remarks:** {row.sRemarks or '(none)'}"
    )

    st.divider()
    update_tab, unmap_tab = st.tabs(["Update", "Unmap"])

    with update_tab:
        _render_update(engine, cfg, row)

    with unmap_tab:
        _render_unmap(engine, cfg, row)
