import os
import psycopg2
from psycopg2.extras import RealDictCursor
from passlib.hash import bcrypt
import hashlib
import json
from datetime import date, timedelta

PG_HOST = os.getenv('PG_HOST','localhost')
PG_PORT = os.getenv('PG_PORT','5432')
PG_DB = os.getenv('PG_DB','task_tracker')
PG_USER = os.getenv('PG_USER','postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD','password')

def connect_db():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)

def init_db():
    with connect_db() as conn:
        with conn.cursor() as cur:
            schema_path = os.path.join(os.path.dirname(__file__), 'postgres_schema.sql')
            with open(schema_path,'r') as f:
                cur.execute(f.read())
        conn.commit()

def get_designations():
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT id, title, parent_id FROM designations')
        return cur.fetchall()

def get_branches():
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT id, name FROM branches')
        return cur.fetchall()

def get_employees():
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''
            SELECT e.id, e.name, e.email, e.designation_id, d.title AS designation, m.name AS manager_name, b.name AS branch_name,
                   e.manager_id, e.branch_id
            FROM employees e
            LEFT JOIN designations d ON e.designation_id = d.id
            LEFT JOIN employees m ON e.manager_id = m.id
            LEFT JOIN branches b ON e.branch_id = b.id
        ''')
        return cur.fetchall()

def create_employee(name, email, designation_id, manager_id, branch_id=None, raw_password='changeme'):
    if raw_password:
        raw_password = raw_password[:72]
    try:
        hashed = bcrypt.hash(raw_password)
    except Exception:
        # Fallback to legacy sha256 if bcrypt backend fails (environment mismatch)
        legacy_hash = hashlib.sha256(raw_password.encode('utf-8')).hexdigest()
        hashed = 'legacy$' + legacy_hash
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO employees (name,email,password,designation_id,manager_id,branch_id) VALUES (%s,%s,%s,%s,%s,%s)''',
                    (name,email,hashed,designation_id,manager_id,branch_id))
        conn.commit()

def get_employee(emp_id):
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM employees WHERE id=%s',(emp_id,))
        row = cur.fetchone()
        return row

def update_employee_password(emp_id, new_password):
    if new_password:
        new_password = new_password[:72]
    try:
        hashed = bcrypt.hash(new_password)
    except Exception:
        legacy_hash = hashlib.sha256(new_password.encode('utf-8')).hexdigest()
        hashed = 'legacy$' + legacy_hash
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('UPDATE employees SET password=%s WHERE id=%s',(hashed, emp_id))
        conn.commit()

def update_employee(emp_id, name, email, designation_id, manager_id, branch_id):
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('''UPDATE employees SET name=%s, email=%s, designation_id=%s, manager_id=%s, branch_id=%s WHERE id=%s''',
                    (name,email,designation_id,manager_id,branch_id,emp_id))
        conn.commit()

def delete_employee(emp_id):
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('DELETE FROM employees WHERE id=%s',(emp_id,))
        conn.commit()

def get_employee_by_email_and_password(email,password):
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM employees WHERE email=%s',(email,))
        row = cur.fetchone()
        if row:
            stored = row['password']
            if stored.startswith('legacy$'):
                legacy_hash = stored.split('legacy$')[1]
                if hashlib.sha256(password.encode('utf-8')).hexdigest() == legacy_hash:
                    return row
            else:
                if bcrypt.verify(password, stored):
                    return row
        return None

def create_task(name, category, type_, start_date, end_date, target, status, assigned_by, assigned_to, current_progress=0):
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO tasks (name,category,type,start_date,end_date,target,status,assigned_by,assigned_to,current_progress)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                    (name,category,type_,start_date,end_date,target,status,assigned_by,assigned_to,current_progress))
        task_id = cur.fetchone()[0]
        payload = json.dumps({'name':name,'category':category,'type':type_,'start_date':str(start_date),'end_date':str(end_date),'target':target,'current_progress':current_progress,'status':status,'assigned_by':assigned_by,'assigned_to':assigned_to})
        cur.execute('''INSERT INTO task_audit (task_id, action, field_name, old_value, new_value, changed_by)
                       VALUES (%s,'create','ALL',NULL,%s,%s)''',(task_id,payload,assigned_by))
        conn.commit()
    return task_id

def get_tasks_for_employee(employee_id):
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM tasks WHERE assigned_to=%s',(employee_id,))
        return cur.fetchall()

def get_task(task_id):
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM tasks WHERE id=%s',(task_id,))
        return cur.fetchone()

def update_task_progress_and_status(task_id, current_progress, status, changed_by=None):
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('SELECT current_progress, status FROM tasks WHERE id=%s',(task_id,))
        old_row = cur.fetchone()
        cur.execute('UPDATE tasks SET current_progress=%s, status=%s WHERE id=%s',(current_progress,status,task_id))
        if changed_by and old_row:
            old_progress, old_status = old_row
            if str(old_progress) != str(current_progress):
                cur.execute('''INSERT INTO task_audit (task_id, action, field_name, old_value, new_value, changed_by)
                               VALUES (%s,'update','current_progress',%s,%s,%s)''', (task_id, str(old_progress), str(current_progress), changed_by))
            if str(old_status) != str(status):
                cur.execute('''INSERT INTO task_audit (task_id, action, field_name, old_value, new_value, changed_by)
                               VALUES (%s,'update','status',%s,%s,%s)''', (task_id, str(old_status), str(status), changed_by))
        conn.commit()

def get_tasks_by_employee(employee_id):
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT t.*, e.name AS employee_name, m.name AS assigned_by_name
                       FROM tasks t JOIN employees e ON t.assigned_to=e.id JOIN employees m ON t.assigned_by=m.id
                       WHERE t.assigned_to=%s''',(employee_id,))
        return cur.fetchall()

def get_lower_designation_ids(designation_id):
    # Recursive retrieval using queries
    ids = []
    def get_children(parent_id):
        with connect_db() as conn, conn.cursor() as cur:
            cur.execute('SELECT id FROM designations WHERE parent_id=%s',(parent_id,))
            children = [row[0] for row in cur.fetchall()]
        all_children = []
        for child in children:
            all_children.append(child)
            all_children.extend(get_children(child))
        return all_children
    ids = get_children(designation_id)
    return ids

def get_subordinate_employee_ids(manager_id):
    """Return list of all employee IDs in the managerial tree beneath manager_id.

    Traverses employees via manager_id links (direct + indirect reports)."""
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('SELECT id, manager_id FROM employees')
        rows = cur.fetchall()
    children_map = {}
    for emp_id, mgr in rows:
        if mgr is None:
            continue
        children_map.setdefault(mgr, []).append(emp_id)
    result = []
    stack = children_map.get(manager_id, [])[:]
    while stack:
        cid = stack.pop()
        result.append(cid)
        stack.extend(children_map.get(cid, []))
    return result

def update_task(task_id, name, category, type_, start_date, end_date, target, status, assigned_to, current_progress, changed_by):
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT name, category, type, start_date, end_date, target, status, assigned_to, current_progress, assigned_by FROM tasks WHERE id=%s',(task_id,))
        old = cur.fetchone()
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('''UPDATE tasks SET name=%s, category=%s, type=%s, start_date=%s, end_date=%s, target=%s, status=%s, assigned_to=%s, current_progress=%s WHERE id=%s''',
                    (name, category, type_, start_date, end_date, target, status, assigned_to, current_progress, task_id))
        if old:
            new_vals = {'name':name,'category':category,'type':type_,'start_date':str(start_date),'end_date':str(end_date),'target':target,'status':status,'assigned_to':assigned_to,'current_progress':current_progress}
            for k,v in new_vals.items():
                if str(old.get(k)) != str(v):
                    cur.execute('''INSERT INTO task_audit (task_id, action, field_name, old_value, new_value, changed_by)
                                   VALUES (%s,'update',%s,%s,%s,%s)''', (task_id, k, str(old.get(k)), str(v), changed_by))
        conn.commit()

def log_task_copy(original_task, new_task_id, changed_by):
    with connect_db() as conn, conn.cursor() as cur:
        payload = json.dumps({'copied_from': original_task['id']})
        cur.execute('''INSERT INTO task_audit (task_id, action, field_name, old_value, new_value, changed_by)
                       VALUES (%s,'copy','source',%s,%s,%s)''',(new_task_id,str(original_task['id']),payload,changed_by))
        conn.commit()

def get_task_audit(task_id):
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT id, task_id, action, field_name, old_value, new_value, changed_by, changed_at
                       FROM task_audit WHERE task_id=%s ORDER BY changed_at ASC, id ASC''',(task_id,))
        return cur.fetchall()

def ensure_sequences():
    # Reset sequences to max(id) so nextval does not collide
    with connect_db() as conn, conn.cursor() as cur:
        for table, seq in [
            ('designations','designations_id_seq'),
            ('branches','branches_id_seq'),
            ('employees','employees_id_seq'),
            ('tasks','tasks_id_seq'),
            ('task_audit','task_audit_id_seq')
        ]:
            try:
                cur.execute(f"SELECT COALESCE(MAX(id),0) FROM {table}")
                max_id = cur.fetchone()[0]
                cur.execute(f"SELECT setval('{seq}', %s)", (max_id,))
            except Exception:
                pass
        conn.commit()

def _add_months(d: date, months: int) -> date:
    # Simple month addition without external libs
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = min(d.day, [31,
                      29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
                      31,30,31,30,31,31,30,31,30,31][m-1])
    return date(y, m, day)

def create_recurring_task_template(name, category, type_, start_date, end_date, target, status, assigned_by, assigned_to, frequency, interval=1, stop_date=None):
    duration_days = (end_date - start_date).days if isinstance(start_date, date) else 0
    if isinstance(start_date, str):
        start_date_obj = date.fromisoformat(start_date)
    else:
        start_date_obj = start_date
    if isinstance(end_date, str):
        end_date_obj = date.fromisoformat(end_date)
    else:
        end_date_obj = end_date
    # Initial occurrence already created outside or will be created now
    first_task_id = create_task(name, category, type_, start_date_obj, end_date_obj, target, status, assigned_by, assigned_to, current_progress=0)
    # Compute next_run_date
    if frequency == 'daily':
        next_run = start_date_obj + timedelta(days=interval)
    elif frequency == 'weekly':
        next_run = start_date_obj + timedelta(days=7*interval)
    elif frequency == 'monthly':
        next_run = _add_months(start_date_obj, interval)
    else:  # yearly
        next_run = _add_months(start_date_obj, 12*interval)
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO task_recurrence (name,category,type,target,status,assigned_by,assigned_to,frequency,interval,start_date,end_date,next_run_date,stop_date,duration_days,active,last_generated_task_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s) RETURNING id''',
                    (name,category,type_,target,status,assigned_by,assigned_to,frequency,interval,start_date_obj,end_date_obj,next_run,stop_date,duration_days,first_task_id))
        rec_id = cur.fetchone()[0]
        conn.commit()
    return rec_id

def create_recurring_template_from_existing(name, category, type_, start_date, end_date, target, status, assigned_by, assigned_to, first_task_id, frequency, interval=1, stop_date=None):
    """Create a recurrence template pointing to an already created first occurrence.

    This avoids creating a duplicate initial task (the existing create_recurring_task_template
    function creates a new first occurrence internally). Use this for flows where the
    initial task has already been persisted (e.g. assignment form or copy form).
    """
    # Normalize dates
    if isinstance(start_date, str):
        start_date_obj = date.fromisoformat(start_date)
    else:
        start_date_obj = start_date
    if isinstance(end_date, str):
        end_date_obj = date.fromisoformat(end_date)
    else:
        end_date_obj = end_date
    duration_days = (end_date_obj - start_date_obj).days if isinstance(start_date_obj, date) and isinstance(end_date_obj, date) else 0
    # Compute next_run_date based on frequency/interval
    if frequency == 'daily':
        next_run = start_date_obj + timedelta(days=interval)
    elif frequency == 'weekly':
        next_run = start_date_obj + timedelta(days=7 * interval)
    elif frequency == 'monthly':
        next_run = _add_months(start_date_obj, interval)
    else:  # yearly
        next_run = _add_months(start_date_obj, 12 * interval)
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO task_recurrence (name,category,type,target,status,assigned_by,assigned_to,frequency,interval,start_date,end_date,next_run_date,stop_date,duration_days,active,last_generated_task_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s) RETURNING id''',
                    (name, category, type_, target, status, assigned_by, assigned_to, frequency, interval, start_date_obj, end_date_obj, next_run, stop_date, duration_days, first_task_id))
        rec_id = cur.fetchone()[0]
        conn.commit()
    return rec_id

def generate_due_recurring_tasks():
    today = date.today()
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT * FROM task_recurrence WHERE active=TRUE AND next_run_date<=%s AND (stop_date IS NULL OR next_run_date<=stop_date)''',(today,))
        templates = cur.fetchall()
    for tpl in templates:
        start_dt = tpl['next_run_date']
        end_dt = start_dt + timedelta(days=tpl['duration_days'])
        new_task_id = create_task(tpl['name'], tpl['category'], tpl['type'], start_dt, end_dt, tpl['target'], tpl['status'], tpl['assigned_by'], tpl['assigned_to'], current_progress=0)
        # advance next_run_date
        if tpl['frequency'] == 'daily':
            nxt = start_dt + timedelta(days=tpl['interval'])
        elif tpl['frequency'] == 'weekly':
            nxt = start_dt + timedelta(days=7*tpl['interval'])
        elif tpl['frequency'] == 'monthly':
            nxt = _add_months(start_dt, tpl['interval'])
        else:
            nxt = _add_months(start_dt, 12*tpl['interval'])
        with connect_db() as conn, conn.cursor() as cur:
            cur.execute('''UPDATE task_recurrence SET next_run_date=%s, last_generated_task_id=%s WHERE id=%s''',(nxt,new_task_id,tpl['id']))
            conn.commit()