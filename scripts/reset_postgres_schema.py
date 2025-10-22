import os, psycopg2
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
load_dotenv(os.path.join(BASE_DIR,'.env'))
PG_HOST = os.getenv('PG_HOST','localhost')
PG_PORT = os.getenv('PG_PORT','5432')
PG_DB = os.getenv('PG_DB','task_tracker')
PG_USER = os.getenv('PG_USER','postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD','postgres')

def main():
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)
    cur = conn.cursor()
    for tbl in ['tasks','employees','branches','designations','alembic_version']:
        try:
            cur.execute(f'DROP TABLE IF EXISTS {tbl} CASCADE')
        except Exception as e:
            print(f"Failed dropping {tbl}: {e}")
    conn.commit(); cur.close(); conn.close()
    print('Schema reset complete.')

if __name__ == '__main__':
    main()
