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
 - Recurring tasks: choose frequency (daily/weekly/monthly/yearly), interval, optional stop date on assignment, copy, or bulk upload. Future occurrences auto-generate when viewing the Tasks page.

### 4. Future Improvements
- Alembic migrations added (initial revision executes schema). Future changes should use `alembic revision --autogenerate` after adding SQLAlchemy models.
- Pagination for reports
- Role-based access control
 - Advanced recurrence (weekday selection, exclusions)
 - XLSX import support
 - Row-level upload preview/dry-run

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

### Deployment Notes

- The server reads the `PORT` environment variable (defaults to `5000`) and binds to `0.0.0.0`, making it deployment friendly.
- Example using Gunicorn (ensure you reference `wsgi:app`):
   ```bash
   export PORT=8000
   gunicorn -w 4 -b 0.0.0.0:${PORT} wsgi:app
   ```
   Adjust worker count to match your CPU resources.

## Bulk Upload

### Task Upload
Route: `GET /tasks/upload` (requires login)

Download CSV template: `GET /tasks/template`

Template Columns:

| Column | Required | Notes |
| ------ | -------- | ----- |
| name | Yes | Task name |
| category | Yes | personal or team |
| type | Yes | Arbitrary type label |
| start_date | Yes | YYYY-MM-DD |
| end_date | Yes | YYYY-MM-DD |
| target | Yes | Integer target value |
| status | Yes | todo / in progress / completed / blocked |
| assigned_to | Yes | Employee id OR email; must be you or a subordinate |
| current_progress | No | Defaults 0 if blank |
| recurrence_frequency | No | daily/weekly/monthly/yearly to create template |
| recurrence_interval | No | Integer (defaults 1) |
| recurrence_stop_date | No | YYYY-MM-DD; template deactivates after this date |

Behavior:
- Each row creates the initial task plus (if recurrence_frequency provided) a recurrence template for future tasks.
- Validation errors are collected and displayed; successful rows proceed independently.
- Recurrence interval defaults to 1 if invalid.

### Employee Upload
Route: `GET /employees/upload` (admin only: designation_id==1)

Download CSV template: `GET /employees/template`

Template Columns:

| Column | Required | Notes |
| ------ | -------- | ----- |
| name | Yes | Employee name |
| email | Yes | Unique email |
| designation_title | Yes | Must match an existing designation title |
| manager_email | No | Must exist; establishes hierarchy |
| branch_name | No | Must match existing branch |
| password | No | Defaults to 'changeme' if blank |

Behavior:
- Skips rows with existing emails (logged as errors, continues).
- Requires existing designation and optional manager/branch to be valid.
- Passwords hashed with bcrypt.

### Notes
- Upload is synchronous and may need pagination / background processing for very large files (>1k rows). Consider splitting files.
- A future improvement will add a dry-run mode (`?dry_run=1`).
