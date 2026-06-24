from db import load_config, get_engine
from queries import check_connection, check_table_exists, check_procedure_exists, STORED_PROC

cfg = load_config()
engine = get_engine()
check_connection(engine)
print("Connection OK")

for key in ("b2c_table", "userinfo_table", "audit_log_table"):
    exists = check_table_exists(engine, cfg["db_name"], cfg[key])
    status = "EXISTS" if exists else "MISSING"
    print(f"{cfg[key]}: {status}")

proc_exists = check_procedure_exists(engine, cfg["db_name"])
proc_status = "EXISTS" if proc_exists else "MISSING"
print(f"{STORED_PROC}: {proc_status}")
