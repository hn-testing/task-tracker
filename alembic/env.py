from __future__ import annotations
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context
import os

# this is the Alembic Config object, which provides access to the values within the .ini file.
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# Load environment variables
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(BASE_DIR, '.env'))

pg_url = (
    f"postgresql://{os.getenv('PG_USER','postgres')}:{os.getenv('PG_PASSWORD','postgres')}@"
    f"{os.getenv('PG_HOST','localhost')}:{os.getenv('PG_PORT','5432')}/{os.getenv('PG_DB','task_tracker')}"
)
config.set_main_option('sqlalchemy.url', pg_url)

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=None, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(config.get_main_option('sqlalchemy.url'), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
