import os
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(BASE_DIR,'.env'))
import psycopg2
from psycopg2.extras import execute_values

BRANCHES = ["North","South","East","West","Central"]

PG_HOST = os.getenv('PG_HOST','localhost')
PG_PORT = os.getenv('PG_PORT','5432')
PG_DB = os.getenv('PG_DB','task_tracker')
PG_USER = os.getenv('PG_USER','postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD','postgres')

def seed():
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)
    except Exception as e:
        print(f"[ERROR] Could not connect to Postgres: {e}")
        return
    cur = conn.cursor()
    try:
        cur.execute('CREATE TABLE IF NOT EXISTS branches (id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE)')
        existing = set()
        cur.execute('SELECT name FROM branches')
        for (name,) in cur.fetchall():
            existing.add(name)
        new = [(b,) for b in BRANCHES if b not in existing]
        if new:
            execute_values(cur, 'INSERT INTO branches (name) VALUES %s ON CONFLICT DO NOTHING', new)
            print(f"Inserted {len(new)} branches")
        else:
            print("No new branches to insert")
        conn.commit()
    except Exception as e:
        print(f"[ERROR] Seeding failed: {e}")
    finally:
        cur.close(); conn.close()

if __name__ == '__main__':
    seed()
