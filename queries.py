import json
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from logger import logger

STORED_PROC = "stp_SetB2CDetails"


# ---------- health checks ----------

def check_connection(engine):
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def check_table_exists(engine, db_name, table_name):
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = :db AND table_name = :tbl"
            ),
            {"db": db_name, "tbl": table_name},
        )
        return result.scalar() > 0


def check_procedure_exists(engine, db_name):
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.routines "
                "WHERE routine_schema = :db AND routine_name = :proc"
            ),
            {"db": db_name, "proc": STORED_PROC},
        )
        return result.scalar() > 0


def ensure_audit_log(engine, cfg):
    table = cfg["audit_log_table"]
    with engine.begin() as conn:
        conn.execute(
            text(f"""
                CREATE TABLE IF NOT EXISTS `{table}` (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    action VARCHAR(20),
                    kol_id VARCHAR(50),
                    old_values JSON,
                    new_values JSON,
                    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        )


# ---------- user_info reads ----------

def get_kol_options(engine, cfg):
    table = cfg["userinfo_table"]
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT id, email, real_name FROM `{table}` ORDER BY id")
        )
        return result.fetchall()


def get_unmapped_kol_options(engine, cfg):
    """Returns user_info rows for KOLs NOT already present in tbl_B2CDetails."""
    userinfo_table = cfg["userinfo_table"]
    b2c_table = cfg["b2c_table"]
    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"SELECT u.id, u.email, u.real_name FROM `{userinfo_table}` u "
                f"WHERE u.id NOT IN (SELECT nKOLId FROM `{b2c_table}`) "
                "ORDER BY u.id"
            )
        )
        rows = result.fetchall()
    logger.debug(f"get_unmapped_kol_options returned {len(rows)} rows")
    return rows


def search_unmapped_kols(engine, cfg, search_term, limit=20):
    """Search unmapped KOLs by id, email, or name (case-insensitive substring).
    When search_term is empty, returns the first `limit` unmapped KOLs by id."""
    userinfo_table = cfg["userinfo_table"]
    b2c_table = cfg["b2c_table"]
    pattern = f"%{search_term}%" if search_term else "%"
    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"SELECT u.id, u.email, u.real_name FROM `{userinfo_table}` u "
                f"WHERE u.id NOT IN (SELECT nKOLId FROM `{b2c_table}`) "
                "AND (CAST(u.id AS CHAR) LIKE :term "
                "OR LOWER(u.email) LIKE LOWER(:term) "
                "OR LOWER(u.real_name) LIKE LOWER(:term)) "
                "ORDER BY u.id LIMIT :limit"
            ),
            {"term": pattern, "limit": limit},
        )
        rows = result.fetchall()
    logger.debug(f"search_unmapped_kols term={search_term!r} returned {len(rows)} rows")
    return rows


def get_kol_by_id(engine, cfg, kol_id):
    table = cfg["userinfo_table"]
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT id, email, real_name FROM `{table}` WHERE id = :kol_id"),
            {"kol_id": kol_id},
        )
        return result.fetchone()


# ---------- tbl_B2CDetails reads ----------

def get_bdm_options(engine, cfg):
    table = cfg["b2c_table"]
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT DISTINCT nBDMId, sBDMEmail FROM `{table}` ORDER BY nBDMId")
        )
        rows = result.fetchall()
    logger.debug(f"get_bdm_options returned {len(rows)} rows")
    return rows


def get_bd_options(engine, cfg, bdm_id):
    table = cfg["b2c_table"]
    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"SELECT DISTINCT nBDId, sBDEmail FROM `{table}` "
                "WHERE nBDMId = :bdm_id ORDER BY nBDId"
            ),
            {"bdm_id": bdm_id},
        )
        rows = result.fetchall()
    logger.debug(f"get_bd_options returned {len(rows)} rows for bdm_id={bdm_id}")
    return rows


def get_group_name_options(engine, cfg):
    table = cfg["b2c_table"]
    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"SELECT DISTINCT sGroupName FROM `{table}` "
                "WHERE sGroupName IS NOT NULL ORDER BY sGroupName"
            )
        )
        rows = [row[0] for row in result.fetchall()]
    logger.debug(f"get_group_name_options returned {len(rows)} rows")
    return rows


def check_kol_exists(engine, cfg, kol_id):
    """Returns the existing b2c row if kol_id is already mapped anywhere, else None."""
    table = cfg["b2c_table"]
    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"SELECT nBDMId, sBDMEmail, nBDId, sBDEmail "
                f"FROM `{table}` WHERE nKOLId = :kol_id"
            ),
            {"kol_id": kol_id},
        )
        row = result.fetchone()
    logger.debug(f"check_kol_exists for kol_id={kol_id}: {'found' if row else 'not found'}")
    return row


def get_kol_row(engine, cfg, kol_id):
    """Returns the full b2c row for a given KOL ID."""
    table = cfg["b2c_table"]
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT * FROM `{table}` WHERE nKOLId = :kol_id"),
            {"kol_id": kol_id},
        )
        row = result.fetchone()
    logger.debug(f"get_kol_row for kol_id={kol_id}: {'found' if row else 'not found'}")
    return row


def get_all_kol_ids(engine, cfg):
    """Returns all nKOLId values currently mapped in b2c."""
    table = cfg["b2c_table"]
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT DISTINCT nKOLId FROM `{table}` ORDER BY nKOLId")
        )
        rows = [row[0] for row in result.fetchall()]
    logger.debug(f"get_all_kol_ids returned {len(rows)} rows")
    return rows


def get_b2c_page(engine, cfg, page_number, page_size, search_term=None):
    """Returns (rows, total_count) for the given page, optionally filtered by search_term.
    Never cached — always queries live."""
    table = cfg["b2c_table"]
    offset = (page_number - 1) * page_size

    if search_term:
        where_clause = (
            "WHERE CAST(nKOLId AS CHAR) LIKE :term OR sKOLEmail LIKE :term "
            "OR sKOLName LIKE :term OR sBDEmail LIKE :term OR sBDMEmail LIKE :term"
        )
    else:
        where_clause = ""

    with engine.connect() as conn:
        params = {"limit": page_size, "offset": offset}
        if search_term:
            params["term"] = f"%{search_term}%"

        rows = conn.execute(
            text(
                f"SELECT * FROM `{table}` {where_clause} "
                "ORDER BY nKOLId LIMIT :limit OFFSET :offset"
            ),
            params,
        ).fetchall()

        count_params = {"term": params["term"]} if search_term else {}
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM `{table}` {where_clause}"),
            count_params,
        ).scalar()

    logger.debug(
        f"get_b2c_page page={page_number} size={page_size} "
        f"search={search_term!r} returned {len(rows)}/{total} rows"
    )
    return rows, total


def get_recent_audit_log(engine, cfg, limit=50):
    table = cfg["audit_log_table"]
    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"SELECT id, action, kol_id, old_values, new_values, performed_at "
                f"FROM `{table}` ORDER BY performed_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        rows = result.fetchall()
    logger.debug(f"get_recent_audit_log returned {len(rows)} rows")
    return rows


# ---------- writes ----------

def call_set_b2c(
    engine, cfg, filter_type,
    bdm_id, bdm_email, bd_id, bd_email,
    kol_id, kol_name, kol_email, group_name,
    upfront_cost, commission, remarks,
    old_values=None, new_values=None,
):
    """
    Calls stp_SetB2CDetails and writes to audit_log in the same transaction.
    filter_type: 1=INSERT, 2=UPDATE, 3=UNMAP (DELETE)
    Returns (True, None) on success or (False, error_message) on failure.
    """
    action_map = {1: "INSERT", 2: "UPDATE", 3: "UNMAP"}
    action = action_map[filter_type]
    audit_table = cfg["audit_log_table"]

    logger.debug(
        f"call_set_b2c starting: filter_type={filter_type} ({action}), "
        f"kol_id={kol_id}, bdm_id={bdm_id}, bd_id={bd_id}"
    )

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"CALL {STORED_PROC}("
                    ":ft, :bdm_id, :bdm_email, :bd_id, :bd_email, "
                    ":kol_id, :kol_name, :kol_email, :group_name, "
                    ":upfront_cost, :commission, :remarks"
                    ")"
                ),
                {
                    "ft": filter_type,
                    "bdm_id": bdm_id,
                    "bdm_email": bdm_email,
                    "bd_id": bd_id,
                    "bd_email": bd_email,
                    "kol_id": kol_id,
                    "kol_name": kol_name,
                    "kol_email": kol_email,
                    "group_name": group_name,
                    "upfront_cost": upfront_cost,
                    "commission": commission,
                    "remarks": remarks,
                },
            )
            conn.execute(
                text(
                    f"INSERT INTO `{audit_table}` "
                    "(action, kol_id, old_values, new_values) "
                    "VALUES (:action, :kol_id, :old_values, :new_values)"
                ),
                {
                    "action": action,
                    "kol_id": str(kol_id),
                    "old_values": json.dumps(old_values) if old_values is not None else None,
                    "new_values": json.dumps(new_values) if new_values is not None else None,
                },
            )
        logger.debug(f"call_set_b2c succeeded: {action} for kol_id={kol_id}")
        return True, None
    except SQLAlchemyError as e:
        msg = str(e.orig) if hasattr(e, "orig") and e.orig else str(e)
        logger.error(
            f"call_set_b2c FAILED: {action} for kol_id={kol_id}. Raw error: {msg}",
            exc_info=True,
        )
        return False, msg


def humanize_db_error(raw_error: str) -> str:
    """Convert common raw DB error strings into plain-English messages."""
    lowered = raw_error.lower()
    if "1062" in raw_error or "duplicate entry" in lowered:
        return "This combination already exists in the database. It may have just been added by someone else."
    if "1452" in raw_error or "foreign key constraint" in lowered:
        return "This record references data that doesn't exist or was recently removed."
    if "1146" in raw_error or "doesn't exist" in lowered:
        return "A required table is missing. Contact the system administrator."
    if "2003" in raw_error or "can't connect" in lowered:
        return "Lost connection to the database. Please check your network and try again."
    if "1048" in raw_error or "cannot be null" in lowered:
        return "A required field was left empty."
    return f"An unexpected database error occurred. Technical detail: {raw_error}"
