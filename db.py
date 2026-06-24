import pymysql
pymysql.install_as_MySQLdb()

import json
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from logger import logger


def load_config():
    try:
        with open("config.json") as f:
            cfg = json.load(f)
        safe_cfg = {k: v for k, v in cfg.items() if k != "db_password"}
        logger.debug(f"Loaded config.json: {safe_cfg}")
        return cfg
    except FileNotFoundError as e:
        logger.error(f"config.json not found. Detail: {e}", exc_info=True)
        st.error(
            "config.json not found. Copy config.example.json to config.json "
            "and fill in your database connection details."
        )
        st.stop()
    except json.JSONDecodeError as e:
        logger.error(f"config.json contains invalid JSON. Detail: {e}", exc_info=True)
        st.error(
            f"config.json contains invalid JSON and could not be read. "
            f"Detail: {e}"
        )
        st.stop()


@st.cache_resource
def get_engine():
    logger.debug("Creating new SQLAlchemy engine (should only log once per session).")
    cfg = load_config()
    connection_url = URL.create(
        drivername="mysql",
        username=cfg["db_user"],
        password=cfg["db_password"],
        host=cfg["db_host"],
        port=cfg["db_port"],
        database=cfg["db_name"]
    )
    return create_engine(connection_url, pool_recycle=3600)
