import sqlite3
import os
DB = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
if not os.path.exists(DB):
    print('ERROR: db.sqlite3 not found at', DB)
    raise SystemExit(1)
conn = sqlite3.connect(DB)
cur = conn.cursor()
# Get user tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
tables = [r[0] for r in cur.fetchall()]
print('TOTAL_TABLES:', len(tables))
print('TABLE_NAMES:')
for t in tables:
    print('-', t)

# Check specific table existence
for tbl in ('questions_syllabus','auth_user','accounts_userprofile'):
    exists = tbl in tables
    print(f'TABLE_EXISTS:{tbl}:{exists}')
    if exists:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{tbl}"')
            cnt = cur.fetchone()[0]
        except Exception as e:
            cnt = f'ERROR:{e}'
        print(f'TABLE_COUNT:{tbl}:{cnt}')

# Total rows across all user tables
total_rows = 0
for t in tables:
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{t}"')
        c = cur.fetchone()[0]
        total_rows += c
    except Exception:
        # skip views or problematic tables
        pass
print('TOTAL_ROWS_ACROSS_USER_TABLES:', total_rows)
print('DB_POPULATED:', total_rows > 0)
conn.close()
