import os
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(BASE_DIR,'.env'))
import sys
import psycopg2
from psycopg2 import OperationalError

PG_HOST = os.getenv('PG_HOST','localhost')
PG_PORT = os.getenv('PG_PORT','5432')
PG_DB = os.getenv('PG_DB','task_tracker')
PG_USER = os.getenv('PG_USER','postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD','postgres')

def main():
    print("Testing PostgreSQL connection with:")
    print(f" HOST={PG_HOST} PORT={PG_PORT} DB={PG_DB} USER={PG_USER} {PG_PASSWORD}")
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)
        cur = conn.cursor()
        cur.execute('SELECT 1')
        print("Connection successful.")
        cur.close(); conn.close()
        sys.exit(0)
    except OperationalError as e:
        print("Connection failed:")
        print(e)
        print("Troubleshooting tips:\n 1. Verify PG_USER and PG_PASSWORD.\n 2. Check pg_hba.conf auth method (md5 vs scram).\n 3. Ensure the database exists (createdb task_tracker).\n 4. Confirm server listening on the given host/port.\n 5. If using Docker, ensure port mapping.")
        sys.exit(1)

if __name__ == '__main__':
    main()
