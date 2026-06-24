import html
import json
import streamlit as st
from db import get_engine, load_config
from health_check import run_health_check_once
from logo import show_page_header
from queries import get_recent_audit_log
from pages.insert_form import render_insert
from pages.manage_form import render_manage
from pages.b2c_table_view import render_b2c_table

# ── Audit log field labels ─────────────────────────────────────────────────────
_FIELD_LABELS = {
    "nBDMId":        "BD Manager ID",
    "sBDMEmail":     "BD Manager Email",
    "nBDId":         "BD ID",
    "sBDEmail":      "BD Email",
    "nKOLId":        "KOL ID",
    "sKOLName":      "KOL Name",
    "sKOLEmail":     "KOL Email",
    "sGroupName":    "Group Name",
    "nUpFrontCost":  "Upfront Cost",
    "nCommission":   "Commission",
    "sRemarks":      "Remarks",
}

_ACTION_STYLE = {
    "INSERT": ("al-insert", "badge-insert"),
    "UPDATE": ("al-update", "badge-update"),
    "UNMAP":  ("al-unmap",  "badge-unmap"),
}

# ── Global + Audit CSS ─────────────────────────────────────────────────────────
_GLOBAL_CSS = """<style>
/* ═══ Hide Streamlit's auto multi-page sidebar navigation ═══ */
[data-testid="stSidebarNav"],
[data-testid="stSidebarNavItems"],
[data-testid="stSidebarNavSeparator"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }

/* ═══ Typography ═══ */
.stApp {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Helvetica Neue', Arial, sans-serif;
}
h1 { letter-spacing: -0.025em !important; }
h2, h3 { letter-spacing: -0.015em !important; }

/* ═══ Buttons — base ═══ */
div[data-testid="stButton"] > button {
    border-radius: 8px;
    font-weight: 500;
    letter-spacing: 0.01em;
    transition: background-color 0.15s ease, border-color 0.15s ease,
                box-shadow 0.15s ease;
    border: 1px solid rgba(139, 148, 158, 0.25);
}
div[data-testid="stButton"] > button:hover:not([disabled]) {
    border-color: rgba(88, 166, 255, 0.55);
    box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.12);
}

/* ═══ Primary button ═══ */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #1a5fbd 0%, #2d7cf4 100%);
    border-color: transparent;
    box-shadow: 0 2px 6px rgba(26, 95, 189, 0.4);
}
div[data-testid="stButton"] > button[kind="primary"]:hover:not([disabled]) {
    background: linear-gradient(135deg, #2368d4 0%, #4a8ff6 100%);
    box-shadow: 0 3px 10px rgba(26, 95, 189, 0.55);
    border-color: transparent;
}

/* ═══ Disabled button ═══ */
div[data-testid="stButton"] > button[disabled] {
    opacity: 0.38;
    cursor: not-allowed;
}

/* ═══ Menu buttons (full-width) ═══ */
.menu-btn-wrap div[data-testid="stButton"] > button {
    font-size: 1rem;
    padding: 0.65rem 1.2rem;
    text-align: left;
}

/* ═══ Dividers ═══ */
hr { border-color: #21262d !important; margin: 1rem 0 !important; }

/* ═══ Alerts ═══ */
div[data-testid="stAlert"] { border-radius: 8px; }

/* ═══ Inputs & selects ═══ */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
    border-radius: 6px;
}

/* ══════════════════════════════════════════════════
   Audit log table
══════════════════════════════════════════════════ */
.al-wrap { overflow-x: auto; margin-top: 0.5rem; border-radius: 6px; }
.al-tbl {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    font-family: inherit;
    table-layout: fixed;
}
.al-tbl th {
    text-align: left;
    padding: 8px 12px;
    color: #8b949e;
    font-weight: 600;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 2px solid #30363d;
    white-space: nowrap;
}
.al-tbl td {
    padding: 10px 12px;
    vertical-align: top;
    border-bottom: 1px solid #21262d;
    color: #e6edf3;
    line-height: 1.65;
    word-break: break-word;
    overflow-wrap: break-word;
}
.al-tbl tr:hover td { background: rgba(255,255,255,0.025); }
.al-col-time   { width: 165px; }
.al-col-action { width: 90px; }
.al-col-kol    { width: 75px; }
.al-time { color: #8b949e; white-space: nowrap; }
.al-badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 10px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    white-space: nowrap;
}
.badge-insert { background: rgba(46,160,67,0.18);  color: #3fb950; }
.badge-update { background: rgba(56,139,253,0.18); color: #79c0ff; }
.badge-unmap  { background: rgba(248,81,73,0.18);  color: #ff7b72; }
.al-insert td:first-child { border-left: 3px solid rgba(46,160,67,0.7); }
.al-update td:first-child { border-left: 3px solid rgba(56,139,253,0.7); }
.al-unmap  td:first-child { border-left: 3px solid rgba(248,81,73,0.7); }
.al-field { display: block; }
.al-lbl   { color: #6e7681; }
.al-none  { color: #484f58; font-style: italic; }
.al-dash  { color: #484f58; }
</style>"""


# ── Audit log helpers ──────────────────────────────────────────────────────────
def _parse_json(raw):
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _fmt_dict_html(data, keys=None):
    if keys is not None:
        data = {k: v for k, v in data.items() if k in keys}
    if not data:
        return '<span class="al-dash">—</span>'
    parts = []
    for k, v in data.items():
        label = html.escape(_FIELD_LABELS.get(k, k))
        if v is None:
            val_html = '<span class="al-none">(none)</span>'
        else:
            val_html = html.escape(str(v))
        parts.append(
            f'<span class="al-field"><span class="al-lbl">{label}:</span> {val_html}</span>'
        )
    return "".join(parts)


def _fmt_cols_html(r):
    old_data = _parse_json(r.old_values)
    new_data = _parse_json(r.new_values)
    if r.action == "UPDATE" and old_data is not None and new_data is not None:
        changed = [k for k in old_data if old_data.get(k) != new_data.get(k)]
        keys = changed if changed else None
        return _fmt_dict_html(old_data, keys), _fmt_dict_html(new_data, keys)
    old_html = _fmt_dict_html(old_data) if old_data is not None else '<span class="al-dash">—</span>'
    new_html = _fmt_dict_html(new_data) if new_data is not None else '<span class="al-dash">—</span>'
    return old_html, new_html


def _build_audit_html(rows):
    tbody_parts = []
    for r in rows:
        old_html, new_html = _fmt_cols_html(r)
        row_cls, badge_cls = _ACTION_STYLE.get(r.action, ("", ""))
        time_str = html.escape(str(r.performed_at)[:19])
        kol_id   = html.escape(str(r.kol_id))
        action   = html.escape(r.action)
        tbody_parts.append(
            f'<tr class="{row_cls}">'
            f'<td class="al-time">{time_str}</td>'
            f'<td><span class="al-badge {badge_cls}">{action}</span></td>'
            f'<td>{kol_id}</td>'
            f'<td>{old_html}</td>'
            f'<td>{new_html}</td>'
            f'</tr>'
        )
    tbody = "\n".join(tbody_parts)
    return (
        f'<div class="al-wrap"><table class="al-tbl">'
        f"<thead><tr>"
        f'<th class="al-col-time">Time</th>'
        f'<th class="al-col-action">Action</th>'
        f'<th class="al-col-kol">KOL ID</th>'
        f"<th>Old Values</th>"
        f"<th>New Values</th>"
        f"</tr></thead>"
        f"<tbody>{tbody}</tbody>"
        f"</table></div>"
    )


# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="KOL Mapping Tool",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)

# ── Health check (once per session) ───────────────────────────────────────────
run_health_check_once()

engine = get_engine()
cfg    = load_config()

# ── Page routing ──────────────────────────────────────────────────────────────
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "menu"

page = st.session_state["current_page"]


# ── Menu ──────────────────────────────────────────────────────────────────────
_MENU_CSS = """<style>
/* Card-style menu buttons */
.menu-card-wrap div[data-testid="stButton"] > button {
    min-height: 86px;
    padding: 18px 22px;
    text-align: left;
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 12px !important;
    color: #e6edf3 !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    line-height: 1.5 !important;
    box-shadow: none !important;
    white-space: pre-line;
}
.menu-card-wrap div[data-testid="stButton"] > button:hover:not([disabled]) {
    border-color: rgba(88,166,255,0.6) !important;
    background: #1c2330 !important;
    box-shadow: 0 0 0 3px rgba(88,166,255,0.1) !important;
}
.menu-card-desc {
    font-size: 0.82rem;
    color: #6e7681;
    margin: 4px 2px 20px;
    line-height: 1.4;
}
</style>"""


_MENU_LOGO_PATH = "assets/logo.png"

_SPLASH_CSS = """<style>
@keyframes splashFadeOut {
    0%   { opacity: 1;  visibility: visible; pointer-events: auto; }
    60%  { opacity: 1;  visibility: visible; pointer-events: auto; }
    100% { opacity: 0;  visibility: hidden;  pointer-events: none; }
}
.kol-splash-overlay {
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    background: #0e1117;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    animation: splashFadeOut 1.8s ease-in-out forwards;
    pointer-events: none;
}
.kol-splash-overlay img {
    width: 300px;
    height: auto;
}
</style>"""


def _logo_b64() -> str:
    """Return a base64 data-URI for the logo, or empty string if file absent."""
    import os, base64
    if not os.path.exists(_MENU_LOGO_PATH):
        return ""
    with open(_MENU_LOGO_PATH, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{data}"


def render_menu():
    import os
    st.markdown(_MENU_CSS, unsafe_allow_html=True)

    # Overlay renders only on the very first visit to the menu in this session
    if not st.session_state.get("intro_played", False):
        st.session_state["intro_played"] = True
        logo_uri = _logo_b64()
        if logo_uri:
            # Single injected block: overlay div + CSS together, rendered before
            # any Streamlit widgets, so it visually covers everything beneath it.
            st.markdown(
                f'<div class="kol-splash-overlay">'
                f'<img src="{logo_uri}" />'
                f'</div>'
                + _SPLASH_CSS,
                unsafe_allow_html=True,
            )

    if os.path.exists(_MENU_LOGO_PATH):
        st.image(_MENU_LOGO_PATH, width=130)

    st.title("KOL Mapping Tool")
    st.success("Connected to database — all tables and procedure found.")
    st.divider()

    st.subheader("Main Menu")
    st.markdown("<br>", unsafe_allow_html=True)

    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.markdown('<div class="menu-card-wrap">', unsafe_allow_html=True)

        if st.button("🗂️  tbl_B2CDetails", key="menu_b2c", use_container_width=True):
            st.session_state["current_page"] = "b2c_table"
            st.rerun()
        st.markdown(
            '<p class="menu-card-desc">View, add, and update KOL mappings</p>',
            unsafe_allow_html=True,
        )

        if st.button("📋  View Change History", key="menu_history", use_container_width=True):
            st.session_state["current_page"] = "history"
            st.rerun()
        st.markdown(
            '<p class="menu-card-desc">See a log of every insert, update, and unmap action</p>',
            unsafe_allow_html=True,
        )

        st.markdown("</div>", unsafe_allow_html=True)


# ── History ───────────────────────────────────────────────────────────────────
def render_history(engine, cfg):
    show_page_header("back_history", "menu")

    st.subheader("Change History (last 50)")
    audit_rows = get_recent_audit_log(engine, cfg)
    if not audit_rows:
        st.info("No changes recorded yet. Add or update a KOL mapping to see activity here.")
    else:
        st.markdown(_build_audit_html(audit_rows), unsafe_allow_html=True)


# ── Dispatch ──────────────────────────────────────────────────────────────────
if page == "menu":
    render_menu()
elif page == "history":
    render_history(engine, cfg)
elif page == "b2c_table":
    render_b2c_table(engine, cfg)
elif page == "insert_form":
    render_insert(engine, cfg)
elif page == "manage_form":
    render_manage(engine, cfg)
