# All database related functions will be defined here



"""Deprecated SQLite module removed.

All functionality now lives in `database_postgres.py`.
Importing anything from this module will raise immediately.
"""

def __getattr__(name):  # pragma: no cover
    raise RuntimeError("SQLite support has been removed. Use database_postgres.")

__all__ = []
