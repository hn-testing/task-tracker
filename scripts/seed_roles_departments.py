import os
from dotenv import load_dotenv
from psycopg2.extras import execute_values
import psycopg2

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))

PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_PORT = os.getenv('PG_PORT', '5432')
PG_DB = os.getenv('PG_DB', 'task_tracker')
PG_USER = os.getenv('PG_USER', 'postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD', 'postgres')

ROLES = [
    ("Admin", "Full application access"),
    ("Manager", "Manage team tasks and reporting"),
    ("Contributor", "Update and complete assigned work"),
    ("Viewer", "Read-only access"),
]

DEPARTMENTS = [
    "Sales",
    "Marketing",
    "Support",
    "Operations",
    "Human Resources",
]

def ensure_tables(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
        """
    )
    cur.execute(
        """
        ALTER TABLE employees
        ADD COLUMN IF NOT EXISTS role_id INTEGER REFERENCES roles(id)
        """
    )
    cur.execute(
        """
        ALTER TABLE employees
        ADD COLUMN IF NOT EXISTS department_id INTEGER REFERENCES departments(id)
        """
    )

def seed_roles(cur):
    cur.execute('SELECT name FROM roles')
    existing = {row[0] for row in cur.fetchall()}
    new_roles = [(name, desc) for name, desc in ROLES if name not in existing]
    if new_roles:
        execute_values(cur, 'INSERT INTO roles (name, description) VALUES %s ON CONFLICT DO NOTHING', new_roles)
        print(f"Inserted {len(new_roles)} role(s)")
    else:
        print('No new roles to insert')

def seed_departments(cur):
    cur.execute('SELECT name FROM departments')
    existing = {row[0] for row in cur.fetchall()}
    new_depts = [(name,) for name in DEPARTMENTS if name not in existing]
    if new_depts:
        execute_values(cur, 'INSERT INTO departments (name) VALUES %s ON CONFLICT DO NOTHING', new_depts)
        print(f"Inserted {len(new_depts)} department(s)")
    else:
        print('No new departments to insert')

def seed():
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)
    except Exception as exc:
        print(f"[ERROR] Could not connect to Postgres: {exc}")
        return
    try:
        with conn:
            with conn.cursor() as cur:
                ensure_tables(cur)
                seed_roles(cur)
                seed_departments(cur)
    finally:
        conn.close()

if __name__ == '__main__':
    seed()
