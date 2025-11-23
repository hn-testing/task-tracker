import os
import psycopg2
from psycopg2.extras import RealDictCursor
from passlib.hash import bcrypt
import hashlib

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
    hashed = bcrypt.hash(raw_password)
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO employees (name,email,password,designation_id,manager_id,branch_id) VALUES (%s,%s,%s,%s,%s,%s)''',
                    (name,email,hashed,designation_id,manager_id,branch_id))
        conn.commit()

def get_employee(emp_id):
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM employees WHERE id=%s',(emp_id,))
        row = cur.fetchone()
        return row

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
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (name,category,type_,start_date,end_date,target,status,assigned_by,assigned_to,current_progress))
        conn.commit()

def get_tasks_for_employee(employee_id):
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM tasks WHERE assigned_to=%s',(employee_id,))
        return cur.fetchall()

def get_task(task_id):
    with connect_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM tasks WHERE id=%s',(task_id,))
        return cur.fetchone()

def update_task_progress_and_status(task_id, current_progress, status):
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('UPDATE tasks SET current_progress=%s, status=%s WHERE id=%s',(current_progress,status,task_id))
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

def update_task(task_id, name, category, type_, start_date, end_date, target, status, assigned_to, current_progress):
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('''UPDATE tasks SET name=%s, category=%s, type=%s, start_date=%s, end_date=%s, target=%s, status=%s, assigned_to=%s, current_progress=%s WHERE id=%s''',
                    (name, category, type_, start_date, end_date, target, status, assigned_to, current_progress, task_id))
        conn.commit()