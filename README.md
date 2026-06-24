# KOL Mapping Tool

A Streamlit app for mapping KOLs (Key Opinion Leaders) to BDs and BD Managers inside `tbl_B2CDetails`, with a paginated table view, audit history, and safe transactional writes via a stored procedure.

---

## Prerequisites

- Python 3.9+
- MySQL server with `tbl_B2CDetails`, `user_info`, and `stp_SetB2CDetails` already present
- `pip` or a virtual environment manager

---

## Setup

**1. Clone and install dependencies**

```bash
git clone <repo-url>
cd Sql-data-form-autofilling
pip install -r requirements.txt
```

**2. Configure the database connection**

Copy the example config and fill in your credentials:

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "db_host": "localhost",
  "db_port": 3306,
  "db_user": "your_user",
  "db_password": "your_password",
  "db_name": "your_database",
  "b2c_table": "tbl_B2CDetails",
  "userinfo_table": "user_info",
  "audit_log_table": "audit_log"
}
```

`config.json` is gitignored — never commit it.

**3. Apply the corrected stored procedure**

The procedure `stp_SetB2CDetails` must exist in your database before running the app. Two bugs in the original procedure must be fixed first:

- The `DELETE` branch had `IF A_nFilterType = 2` (duplicate of UPDATE) — corrected to `IF A_nFilterType = 3`.
- `sGroupName` was hardcoded as `'Deepankar'` in the INSERT — corrected to use the parameter `A_sGroupName`.

The corrected procedure definition is in [CLAUDE.md](CLAUDE.md) under "Stored procedure: `stp_SetB2CDetails`". Run that `CREATE PROCEDURE` block in MySQL Workbench or the `mysql` CLI against your target database.

**4. Run the app**

```bash
streamlit run app.py
```

On first launch the app will:
- Verify the DB connection
- Check that `tbl_B2CDetails`, `user_info`, and `stp_SetB2CDetails` all exist
- Auto-create the `audit_log` table if it doesn't exist yet

---

## Project structure

```
.
├── config.json              # real credentials (gitignored)
├── config.example.json      # template — commit this, not config.json
├── app.py                   # Streamlit entry point, page routing, audit log UI
├── db.py                    # engine creation and config loading
├── queries.py               # all SQL: SELECT reads + CALL stp_SetB2CDetails writes
├── health_check.py          # startup DB/table/procedure checks
├── logger.py                # logging setup
├── check_db.py              # standalone connection test utility
├── pages/
│   ├── insert_form.py       # Form 1: Add a KOL mapping
│   ├── manage_form.py       # Form 2: Update or Unmap a KOL
│   └── b2c_table_view.py    # Paginated table view with row selection
└── requirements.txt
```

---

## Usage

### Main menu

After launch, the menu offers two entry points:

- **tbl_B2CDetails** — paginated view of all KOL mappings with search, row selection, and action buttons
- **View Change History** — audit log of the last 50 INSERT / UPDATE / UNMAP actions

### Add a KOL mapping (Form 1)

1. Select a BD Manager from the dropdown (live query)
2. Select a BD filtered by that BD Manager (live query)
3. Search and select a KOL from `user_info` — only unmapped KOLs appear
4. KOL email auto-populates (read-only); KOL name pre-fills but is editable
5. Select a Group Name (live distinct query against `tbl_B2CDetails`)
6. Enter Upfront Cost, Commission %, and Remarks
7. Review the plain-English preview of the record to be inserted
8. Click **Confirm Add** to write — calls `stp_SetB2CDetails(1, ...)`

A KOL can only be mapped to one BD Manager + BD combination. If the KOL is already mapped, the form hard-blocks the insert and names the existing assignment.

### Update or Unmap a KOL (Form 2)

- **Update**: search by KOL ID, edit Upfront Cost / Commission / Remarks, review a diff of changed fields, confirm — calls `stp_SetB2CDetails(2, ...)`
- **Unmap**: select a KOL, confirm the irreversibility warning — calls `stp_SetB2CDetails(3, ...)` (hard delete, no soft-delete)

BD Manager and BD are not editable in Form 2. To reassign a KOL, unmap it first then re-add via Form 1.

---

## Database tables

| Table | Owned by | Notes |
|---|---|---|
| `tbl_B2CDetails` | Pre-existing in production | All writes go through `stp_SetB2CDetails` |
| `user_info` | Pre-existing in production | Read-only; KOL lookup uses `id`, `email`, `real_name` |
| `audit_log` | This tool | Auto-created on first run |

---

## Important constraints

- **No raw writes to `tbl_B2CDetails`** — every INSERT/UPDATE/DELETE goes through `CALL stp_SetB2CDetails(...)`.
- **No caching of dropdown or duplicate-check queries** — all live to support concurrent multi-user use.
- **KOL uniqueness is enforced in Python**, not the DB schema — the composite primary key `(nBDMId, nBDId, nKOLId)` does not prevent the same `nKOLId` under a different BD/BDM pair.
- Every write and its audit log entry execute in the same transaction — both succeed or both roll back.

---

## Switching environments

To point the app at a different database (dev → production), edit only `config.json`. No code changes are needed.
