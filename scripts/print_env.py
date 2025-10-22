import os
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(BASE_DIR,'.env'))
keys = [k for k in os.environ.keys() if k.startswith('PG_') or k=='DB_TYPE']
for k in keys:
    if 'PASSWORD' in k:
        print(f"{k}=***REDACTED***")
    else:
        print(f"{k}={os.getenv(k)}")
