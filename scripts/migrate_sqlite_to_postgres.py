import os, sqlite3, psycopg2, sys, hashlib
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(BASE_DIR,'.env'))
from psycopg2.extras import execute_values
try:
    from passlib.hash import bcrypt
    _bcrypt_available = True
except Exception:
    _bcrypt_available = False
def safe_hash(pw: str):
    if not pw:
        pw = 'changeme'
    pw = pw[:72]
    if _bcrypt_available:
        try:
            return bcrypt.hash(pw)
        except Exception:
            pass
    # Fallback: store legacy hash with prefix
    return 'legacy$' + hashlib.sha256(pw.encode('utf-8')).hexdigest()

SQLITE_DB = os.path.join(os.path.dirname(__file__),'..','app','db','task_tracker.db')
PG_HOST = os.getenv('PG_HOST','localhost')
PG_PORT = os.getenv('PG_PORT','5432')
PG_DB = os.getenv('PG_DB','task_tracker')
PG_USER = os.getenv('PG_USER','postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD','postgres')

conn_sqlite = sqlite3.connect(SQLITE_DB)
cur_sqlite = conn_sqlite.cursor()

try:
    pg_conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)
except Exception as e:
    print(f"[ERROR] Postgres connection failed: {e}")
    sys.exit(1)
pg_cur = pg_conn.cursor()

# Ensure schema exists
with open(os.path.join(os.path.dirname(__file__),'..','app','db','postgres_schema.sql'),'r') as f:
    pg_cur.execute(f.read())
pg_conn.commit()

# Migrate designations
cur_sqlite.execute('SELECT id,title,parent_id FROM designations')
rows = cur_sqlite.fetchall()
for r in rows:
    pg_cur.execute('INSERT INTO designations (id,title,parent_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING', r)
pg_conn.commit()

# Migrate branches if exists
cur_sqlite.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='branches'")
if cur_sqlite.fetchone():
    cur_sqlite.execute('SELECT id,name FROM branches')
    rows = cur_sqlite.fetchall()
    for r in rows:
        pg_cur.execute('INSERT INTO branches (id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING', r)
    pg_conn.commit()

"""Iteratively insert employees ensuring managers exist first."""
cur_sqlite.execute('SELECT id,name,email,password,designation_id,manager_id,branch_id FROM employees')
all_emp_rows = [dict(zip(['id','name','email','password','designation_id','manager_id','branch_id'], r)) for r in cur_sqlite.fetchall()]
pending = {e['id']: e for e in all_emp_rows}
migrated_emps = 0
passes = 0
while pending and passes < 20:  # safety cap
    passes += 1
    inserted_this_pass = []
    for eid, emp in list(pending.items()):
        mgr_id = emp['manager_id']
        # Manager must either be None or already inserted
        if mgr_id is not None:
            pg_cur.execute('SELECT 1 FROM employees WHERE id=%s', (mgr_id,))
            if pg_cur.fetchone() is None:
                continue  # wait until manager inserted
        plaintext = emp['password']
        if plaintext and plaintext.startswith(('$2a$','$2b$','$2y$','legacy$')):
            hashed = plaintext
        else:
            hashed = safe_hash(plaintext)
        try:
            pg_cur.execute('''INSERT INTO employees (id,name,email,password,designation_id,manager_id,branch_id)
                              VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                           (emp['id'], emp['name'], emp['email'], hashed, emp['designation_id'], emp['manager_id'], emp['branch_id']))
            migrated_emps += 1
            inserted_this_pass.append(eid)
        except Exception as e:
            print(f"[WARN] Failed inserting employee {eid}: {e}")
    for eid in inserted_this_pass:
        pending.pop(eid, None)
    pg_conn.commit()
if pending:
    print(f"[INFO] Unable to insert {len(pending)} employees due to missing managers after {passes} passes: {list(pending.keys())}")

# Migrate tasks
cur_sqlite.execute('SELECT id,name,category,type,start_date,end_date,target,current_progress,status,assigned_by,assigned_to FROM tasks')
rows = cur_sqlite.fetchall()
pg_cur.execute('SELECT id FROM employees')
existing_emp_ids = {row[0] for row in pg_cur.fetchall()}
skipped = 0
for r in rows:
    tid, name, category, type_, start_date, end_date, target, current_progress, status, assigned_by, assigned_to = r
    if assigned_by not in existing_emp_ids or assigned_to not in existing_emp_ids:
        skipped += 1
        continue
    pg_cur.execute('''INSERT INTO tasks (id,name,category,type,start_date,end_date,target,current_progress,status,assigned_by,assigned_to)
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''', (tid,name,category,type_,start_date,end_date,target,current_progress,status,assigned_by,assigned_to))
if skipped:
    print(f"[INFO] Skipped {skipped} tasks due to missing employee references.")
print(f"[INFO] Migrated employees: {migrated_emps}")
pg_conn.commit()

cur_sqlite.close(); conn_sqlite.close(); pg_cur.close(); pg_conn.close()
print('Migration complete.')
