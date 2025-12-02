CREATE TABLE IF NOT EXISTS designations (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL UNIQUE,
    parent_id INTEGER REFERENCES designations(id)
);

CREATE TABLE IF NOT EXISTS branches (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    designation_id INTEGER NOT NULL REFERENCES designations(id),
    manager_id INTEGER REFERENCES employees(id),
    branch_id INTEGER REFERENCES branches(id),
    role_id INTEGER REFERENCES roles(id),
    department_id INTEGER REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('personal','team')),
    type TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    target INTEGER NOT NULL,
    current_progress INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    assigned_by INTEGER NOT NULL REFERENCES employees(id),
    assigned_to INTEGER NOT NULL REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS task_audit (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    action TEXT NOT NULL,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    changed_by INTEGER NOT NULL REFERENCES employees(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recurring task templates
CREATE TABLE IF NOT EXISTS task_recurrence (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('personal','team')),
    type TEXT NOT NULL,
    target INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'todo',
    assigned_by INTEGER NOT NULL REFERENCES employees(id),
    assigned_to INTEGER NOT NULL REFERENCES employees(id),
    frequency TEXT NOT NULL CHECK (frequency IN ('daily','weekly','monthly','yearly')),
    interval INTEGER NOT NULL DEFAULT 1,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    next_run_date DATE NOT NULL,
    stop_date DATE NULL,
    duration_days INTEGER NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_generated_task_id INTEGER NULL REFERENCES tasks(id)
);

ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS role_id INTEGER REFERENCES roles(id);

ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS department_id INTEGER REFERENCES departments(id);