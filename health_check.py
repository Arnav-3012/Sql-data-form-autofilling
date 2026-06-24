import streamlit as st
from db import get_engine, load_config
from queries import (
    check_connection,
    check_table_exists,
    check_procedure_exists,
    ensure_audit_log,
    STORED_PROC,
)
from logger import logger


def run_health_check_once():
    """Runs DB health check once per session; uses session_state as guard so it's a no-op on subsequent pages."""
    if "health_checked" in st.session_state:
        return

    engine = get_engine()
    cfg = load_config()
    db_name = cfg["db_name"]

    try:
        check_connection(engine)
        logger.debug("DB connection check passed.")
    except Exception as e:
        logger.error(f"DB connection check FAILED. Detail: {e}", exc_info=True)
        st.error(
            "Could not connect to the database. "
            "Check config.json (host/port/user/password) and confirm the DB server is reachable.\n\n"
            f"Detail: {e}"
        )
        st.stop()

    missing_tables = []
    for key in ("b2c_table", "userinfo_table"):
        tbl = cfg[key]
        if not check_table_exists(engine, db_name, tbl):
            missing_tables.append(tbl)

    if missing_tables:
        logger.error(
            f"Table check FAILED — missing in `{db_name}`: {', '.join(missing_tables)}"
        )
        st.error(
            f"Required table(s) not found in database `{db_name}`: "
            f"{', '.join(f'`{t}`' for t in missing_tables)}. "
            "These must already exist — this tool does not create them."
        )
        st.stop()

    logger.debug(f"Table check passed for: {cfg['b2c_table']}, {cfg['userinfo_table']}")

    if not check_procedure_exists(engine, db_name):
        logger.error(
            f"Procedure check FAILED — `{STORED_PROC}` not found in `{db_name}`."
        )
        st.error(
            f"Stored procedure `{STORED_PROC}` not found in database `{db_name}`. "
            "Please create it before using this tool."
        )
        st.stop()

    logger.debug(f"Procedure check passed for: {STORED_PROC}")
    ensure_audit_log(engine, cfg)
    st.session_state["health_checked"] = True
