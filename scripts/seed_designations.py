import os
from dotenv import load_dotenv
import psycopg2

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))

PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_PORT = os.getenv('PG_PORT', '5432')
PG_DB = os.getenv('PG_DB', 'task_tracker')
PG_USER = os.getenv('PG_USER', 'postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD', 'postgres')

HIERARCHY = [
    ('Chairman', None),
    ('CEO', 'Chairman'),
    ('Head of Department', 'CEO'),
    ('Manager', 'Head of Department'),
    ('Staff', 'Manager'),
]


def ensure_designations():
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD,
        )
    except Exception as exc:
        print(f"[ERROR] Could not connect to Postgres: {exc}")
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS designations (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL UNIQUE,
                        parent_id INTEGER REFERENCES designations(id)
                    )
                    """
                )
                title_to_id = {}
                for title, parent in HIERARCHY:
                    cur.execute('SELECT id FROM designations WHERE title=%s', (title,))
                    row = cur.fetchone()
                    if row:
                        title_to_id[title] = row[0]
                        continue
                    parent_id = None
                    if parent:
                        parent_id = title_to_id.get(parent)
                        if parent_id is None:
                            cur.execute('SELECT id FROM designations WHERE title=%s', (parent,))
                            parent_row = cur.fetchone()
                            if parent_row:
                                parent_id = parent_row[0]
                    cur.execute(
                        'INSERT INTO designations (title, parent_id) VALUES (%s, %s) RETURNING id',
                        (title, parent_id),
                    )
                    new_id = cur.fetchone()[0]
                    title_to_id[title] = new_id
                print('Designations ensured successfully:')
                for title in HIERARCHY:
                    print(f" - {title[0]}")
    finally:
        conn.close()


if __name__ == '__main__':
    ensure_designations()
