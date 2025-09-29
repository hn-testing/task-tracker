-- Table for branches
CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
-- Table for designations
CREATE TABLE IF NOT EXISTS designations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL UNIQUE,
    parent_id INTEGER,
    FOREIGN KEY (parent_id) REFERENCES designations(id)
);

-- Table for employees
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    designation_id INTEGER NOT NULL,
    manager_id INTEGER,
    branch_id INTEGER,
    FOREIGN KEY (designation_id) REFERENCES designations(id),
    FOREIGN KEY (manager_id) REFERENCES employees(id),
    FOREIGN KEY (branch_id) REFERENCES branches(id)
);

-- Table for tasks
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT CHECK(category IN ('personal', 'team')) NOT NULL,
    type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    target INTEGER NOT NULL,
    current_progress INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    assigned_by INTEGER NOT NULL,
    assigned_to INTEGER NOT NULL,
    FOREIGN KEY (assigned_by) REFERENCES employees(id),
    FOREIGN KEY (assigned_to) REFERENCES employees(id)
);
