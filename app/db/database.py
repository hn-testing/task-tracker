# All database related functions will be defined here

import sqlite3
import os
from passlib.hash import bcrypt
import hashlib

DB_PATH = os.path.join(os.path.dirname(__file__), 'task_tracker.db')
def connect_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with connect_db() as conn:
        with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), 'r') as f:
            conn.executescript(f.read())

def get_employees():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT e.id, e.name, e.email, e.designation_id, d.title as designation, m.name as manager_name, b.name as branch_name
        FROM employees e
        LEFT JOIN designations d ON e.designation_id = d.id
        LEFT JOIN employees m ON e.manager_id = m.id
        LEFT JOIN branches b ON e.branch_id = b.id
    ''')
    employees = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]
    conn.close()
    return employees

def get_designations():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('SELECT id, title, parent_id FROM designations')
    designations = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]
    conn.close()
    return designations

def get_valid_managers(designation_id):
        conn = connect_db()
        cur = conn.cursor()
        # Find parent designation id
        cur.execute('SELECT parent_id FROM designations WHERE id=?', (designation_id,))
        parent_row = cur.fetchone()
        if not parent_row or parent_row[0] is None:
            conn.close()
            return []  # No valid managers for CEO or top-level
        parent_id = parent_row[0]
        # Get employees with parent designation
        cur.execute('SELECT id, name FROM employees WHERE designation_id=?', (parent_id,))
        managers = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]
        conn.close()
        return managers

def create_employee(name, email, designation_id, manager_id, branch_id=None, raw_password='changeme'):
    if raw_password:
        raw_password = raw_password[:72]
    conn = connect_db()
    cur = conn.cursor()
    hashed = bcrypt.hash(raw_password)
    cur.execute('INSERT INTO employees (name, email, password, designation_id, manager_id, branch_id) VALUES (?, ?, ?, ?, ?, ?)',
                (name, email, hashed, designation_id, manager_id if manager_id else None, branch_id if branch_id else None))
    conn.commit()
    conn.close()

def get_employee(emp_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM employees WHERE id = ?', (emp_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(zip([column[0] for column in cur.description], row))
    return None

def update_employee(emp_id, name, email, designation_id, manager_id, branch_id=None):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''UPDATE employees SET name=?, email=?, designation_id=?, manager_id=?, branch_id=? WHERE id=?''',
                (name, email, designation_id, manager_id if manager_id else None, branch_id if branch_id else None, emp_id))
    conn.commit()
    conn.close()

def delete_employee(emp_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM employees WHERE id=?', (emp_id,))
    conn.commit()
    conn.close()

def reset_db():
    """Drop all tables and reinitialize the database schema."""
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS employees")
    cur.execute("DROP TABLE IF EXISTS designations")
    conn.commit()
    conn.close()
    init_db()

def create_task(name, category, type, start_date, end_date, target, status, assigned_by, assigned_to, current_progress=0):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO tasks (name, category, type, start_date, end_date, target, status, assigned_by, assigned_to, current_progress)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, category, type, start_date, end_date, target, status, assigned_by, assigned_to, current_progress))
    conn.commit()
    conn.close()


def get_tasks_for_employee(employee_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM tasks WHERE assigned_to = ?
    ''', (employee_id,))
    tasks = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]
    conn.close()
    return tasks


def update_task_progress(task_id, current_progress):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''
        UPDATE tasks SET current_progress = ? WHERE id = ?
    ''', (current_progress, task_id))
    conn.commit()
    conn.close()


def update_task_progress_and_status(task_id, current_progress, status):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''
        UPDATE tasks SET current_progress = ?, status = ? WHERE id = ?
    ''', (current_progress, status, task_id))
    conn.commit()
    conn.close()

def update_task(task_id, name, category, type_, start_date, end_date, target, status, assigned_to, current_progress):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''
        UPDATE tasks
        SET name = ?, category = ?, type = ?, start_date = ?, end_date = ?, target = ?, status = ?, assigned_to = ?, current_progress = ?
        WHERE id = ?
    ''', (name, category, type_, start_date, end_date, target, status, assigned_to, current_progress, task_id))
    conn.commit()
    conn.close()


def get_task(task_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    task = cur.fetchone()
    conn.close()
    if task:
        return dict(zip([column[0] for column in cur.description], task))
    return None

def get_employee_by_email_and_password(email, password):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM employees WHERE email = ?', (email,))
    row = cur.fetchone()
    if not row:
        conn.close(); return None
    data = dict(zip([column[0] for column in cur.description], row))
    conn.close()
    stored = data['password']
    if stored.startswith('legacy$'):
        legacy_hash = stored.split('legacy$')[1]
        if hashlib.sha256(password.encode('utf-8')).hexdigest() == legacy_hash:
            return data
    else:
        if bcrypt.verify(password, stored):
            return data
    return None

def get_tasks_by_employee(employee_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT t.*, e.name as employee_name, m.name as assigned_by_name
        FROM tasks t
        JOIN employees e ON t.assigned_to = e.id
        JOIN employees m ON t.assigned_by = m.id
        WHERE t.assigned_to = ?
    ''', (employee_id,))
    rows = cur.fetchall()
    conn.close()
    tasks = []
    for row in rows:
        tasks.append(dict(zip([column[0] for column in cur.description], row)))
    return tasks

def get_lower_designation_ids(designation_id):
    conn = connect_db()
    cur = conn.cursor()
    # Recursively find all child designations
    def get_children(parent_id):
        cur.execute('SELECT id FROM designations WHERE parent_id=?', (parent_id,))
        children = [row[0] for row in cur.fetchall()]
        all_children = []
        for child in children:
            all_children.append(child)
            all_children.extend(get_children(child))
        return all_children
    ids = get_children(designation_id)
    conn.close()
    return ids

def get_branches():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('SELECT id, name FROM branches')
    branches = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]
    conn.close()
    return branches
