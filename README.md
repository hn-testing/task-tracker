## Task Tracker Backend (PostgreSQL Only)

This application now uses only PostgreSQL. All prior SQLite support and migration scripts have been removed.

### 1. Setup
1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create `.env` with:
   ```
   PG_HOST=localhost
   PG_PORT=5432
   PG_DB=task_tracker
   PG_USER=postgres
   PG_PASSWORD=postgres
   ```
3. Create the database if it doesn't exist:
   ```
   createdb task_tracker
   ```
4. Run initial schema (handled automatically on app start) or via Alembic:
   ```
   alembic upgrade head
   ```

### 2. Branch Support
Branches are stored in `branches` table. Seed defaults via:
```
python scripts/seed_branches.py
```

### 3. Notes
- Passwords are now stored hashed with bcrypt (passlib). Default new employee password is `changeme` unless you supply one.
- Migration script re-hashes existing plaintext passwords.
- Ensure `psycopg2-binary`, `passlib`, `SQLAlchemy`, and `alembic` are installed.
 - Recurring tasks: choose frequency (daily/weekly/monthly/yearly), interval, optional stop date on assignment. Future occurrences auto-generate when viewing the Tasks page.

### 4. Future Improvements
- Alembic migrations added (initial revision executes schema). Future changes should use `alembic revision --autogenerate` after adding SQLAlchemy models.
- Pagination for reports
- Role-based access control
 - Advanced recurrence (weekday selection, exclusions), bulk upload templates

### 5. Alembic Usage
Initialize DB (already done) and apply migrations:
```
alembic upgrade head
```
Create a new revision:
```
alembic revision -m "add new table"
```
(You may need to add SQLAlchemy models & target_metadata for autogenerate.)

### 6. Environment Loading & Troubleshooting
The app now loads `.env` via `python-dotenv` at startup. Ensure the file exists at the project root.

Common Postgres auth issues:
1. Wrong password: Update `PG_PASSWORD` in `.env` and restart.
2. pg_hba.conf method mismatch: If server uses `scram-sha-256`, ensure user has a scram password; run `ALTER ROLE postgres PASSWORD 'newpass';`.
3. Database missing: Create with `createdb task_tracker`.
4. Port blocked: Verify PostgreSQL is listening on `5432` (check `postgresql.conf`).
5. Docker: Map the port `-p 5432:5432` and use host `localhost` or container name.

Test connection quickly:
```
python scripts/test_pg_connection.py
```
On failure the script prints troubleshooting tips.

Print currently loaded environment (sanitized):
```
python scripts/print_env.py
```
# Flask Task Tracker

Simple Flask app with task tracking, audit trail, copy, export, and edit features.

## Structure
- `app/` - Main application package
- `app/static/` - Static files (CSS, JS, images)
- `app/templates/` - Jinja2 templates
- `config/` - Configuration files
- `tests/` - Unit tests

## Quick Start
1. Install dependencies: `pip install -r requirements.txt`
2. Run the app: `python app.py`
