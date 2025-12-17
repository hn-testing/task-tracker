from flask import Flask, render_template, request, redirect, url_for, session, abort
import os
from datetime import date
import datetime
from collections import Counter
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=env_path)

# Postgres only
from app.db import database_postgres as database

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('../config/config.py')
    app.secret_key = 'your_secret_key_here'

    # Initialize DB and add dummy data only once at app startup
    try:
        database.init_db()
        if hasattr(database,'ensure_sequences'):
            database.ensure_sequences()
        conn = database.connect_db()
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        return app
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM designations')
    designation_count = cur.fetchone()[0]
    chairman_id = None
    ceo_id = None
    hod_id = None
    manager_id = None
    if designation_count == 0:
        cur.execute('INSERT INTO designations (title, parent_id) VALUES (%s, %s) RETURNING id', ('Chairman', None))
        chairman_id = cur.fetchone()[0]
        cur.execute('INSERT INTO designations (title, parent_id) VALUES (%s, %s) RETURNING id', ('CEO', chairman_id))
        ceo_id = cur.fetchone()[0]
        cur.execute('INSERT INTO designations (title, parent_id) VALUES (%s, %s) RETURNING id', ('Head of Department', ceo_id))
        hod_id = cur.fetchone()[0]
        cur.execute('INSERT INTO designations (title, parent_id) VALUES (%s, %s) RETURNING id', ('Manager', hod_id))
        manager_id = cur.fetchone()[0]
        cur.execute('INSERT INTO designations (title, parent_id) VALUES (%s, %s)', ('Staff', manager_id))
    else:
        cur.execute('SELECT id FROM designations WHERE title=%s', ('Chairman',))
        row = cur.fetchone()
        chairman_id = row[0] if row else None
        cur.execute('SELECT id FROM designations WHERE title=%s', ('CEO',))
        row = cur.fetchone()
        ceo_id = row[0] if row else None
        cur.execute('SELECT id FROM designations WHERE title=%s', ('Head of Department',))
        row = cur.fetchone()
        hod_id = row[0] if row else None
        cur.execute('SELECT id FROM designations WHERE title=%s', ('Manager',))
        row = cur.fetchone()
        manager_id = row[0] if row else None
        cur.execute('SELECT id FROM designations WHERE title=%s', ('Staff',))
        row = cur.fetchone()
        if not row and manager_id:
            cur.execute('INSERT INTO designations (title, parent_id) VALUES (%s, %s)', ('Staff', manager_id))
    if not manager_id:
        cur.execute('SELECT id FROM designations WHERE title=%s', ('Manager',))
        row = cur.fetchone()
        if row:
            manager_id = row[0]
    cur.execute('SELECT id FROM designations WHERE title=%s', ('Auditor',))
    if not cur.fetchone():
        cur.execute('INSERT INTO designations (title, parent_id) VALUES (%s, %s)', ('Auditor', manager_id))
    cur.execute('SELECT id FROM roles WHERE name=%s', ('Auditor',))
    if not cur.fetchone():
        cur.execute('INSERT INTO roles (name, description) VALUES (%s, %s)',
                    ('Auditor', 'Responsible for auditing tasks and ensuring compliance.'))
    conn.commit()
    conn.close()

    try:
        if hasattr(database, 'ensure_task_types'):
            database.ensure_task_types()
    except Exception as e:
        print(f"[WARN] Task type seeding failed: {e}")

    def can_user_approve_update(current_user, task, update, employee_lookup=None):
        """Return True when the user is authorised to approve a task update."""
        if not current_user or not task or not update:
            return False
        if current_user.get('designation_id') == 1:
            return True
        assigned_by = task.get('assigned_by')
        assigned_to = task.get('assigned_to')
        if assigned_by and assigned_by != assigned_to and current_user['id'] == assigned_by:
            return True
        updated_by = update.get('updated_by')
        if not updated_by:
            return False
        employee = None
        if employee_lookup:
            employee = employee_lookup.get(updated_by)
        if not employee:
            employee = database.get_employee(updated_by)
        if employee and employee.get('manager_id') == current_user['id']:
            return True
        return False

    def get_role_name(employee):
        if not employee or not employee.get('role_id'):
            return None
        try:
            roles = database.get_roles()
        except Exception:
            return None
        role_id = employee.get('role_id')
        for role in roles:
            if role.get('id') == role_id:
                return role.get('name')
        return None

    @app.context_processor
    def inject_user_context():
        current_user = database.get_employee(session['user_id']) if 'user_id' in session else None
        current_role_name = get_role_name(current_user)
        return {
            'current_user': current_user,
            'current_role_name': current_role_name
        }

    def _coerce_to_datetime(value):
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, date):
            return datetime.datetime.combine(value, datetime.time())
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            parse_attempts = (
                '%Y-%m-%d',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',
                '%d-%m-%Y',
                '%d-%m-%Y %H:%M',
                '%d-%m-%Y %H:%M:%S',
                '%d/%m/%Y'
            )
            for fmt in parse_attempts:
                try:
                    return datetime.datetime.strptime(stripped, fmt)
                except ValueError:
                    continue
            try:
                normalized = stripped.replace('Z', '+00:00')
                return datetime.datetime.fromisoformat(normalized)
            except ValueError:
                return None
        return None

    @app.template_filter('as_dmy')
    def format_as_dmy(value):
        dt_value = _coerce_to_datetime(value)
        if dt_value:
            return dt_value.strftime('%d-%m-%Y')
        if isinstance(value, str):
            return value
        return ''

    @app.template_filter('as_dmy_hm')
    def format_as_dmy_hm(value):
        dt_value = _coerce_to_datetime(value)
        if dt_value:
            return dt_value.strftime('%d-%m-%Y %H:%M')
        if isinstance(value, str):
            return value
        return ''

    @app.route('/')
    def home():
        if 'user_id' in session:
            current_user = database.get_employee(session['user_id'])
        else:
            current_user = None
        current_role_name = get_role_name(current_user)
        return render_template('index.html', current_user=current_user, current_role_name=current_role_name)

    @app.route('/hello')
    def hello_world():
        return 'Hello, World!'

    @app.route('/employees', methods=['GET'])
    def employees():
        employees = database.get_employees()
        designations = database.get_designations()
        valid_managers = employees
        branches = database.get_branches()
        roles = database.get_roles()
        departments = database.get_departments()
        current_user = database.get_employee(session['user_id']) if 'user_id' in session else None
        current_role_name = get_role_name(current_user)
        return render_template(
            'employees.html',
            employees=employees,
            designations=designations,
            valid_managers=valid_managers,
            branches=branches,
            roles=roles,
            departments=departments,
            current_user=current_user,
            current_role_name=current_role_name
        )

    @app.route('/employees/create', methods=['POST'])
    def create_employee():
        name = request.form['name']
        email = request.form['email']
        designation_id = int(request.form['designation_id'])
        manager_raw = request.form.get('manager_id') or None
        branch_raw = request.form.get('branch_id') or None
        role_raw = request.form.get('role_id') or None
        department_raw = request.form.get('department_id') or None
        password = request.form.get('password') or 'changeme'
        # Resolve manager id allowing either numeric id or name/email
        manager_id = None
        if manager_raw:
            if manager_raw.isdigit():
                manager_id = int(manager_raw)
            else:
                emps = database.get_employees()
                match_emp = next((e for e in emps if e['name'].lower() == manager_raw.lower() or e['email'].lower() == manager_raw.lower()), None)
                if match_emp:
                    manager_id = match_emp['id']
        # Resolve branch id allowing either numeric id or branch name
        branch_id = None
        if branch_raw:
            if branch_raw.isdigit():
                branch_id = int(branch_raw)
            else:
                branches_list = database.get_branches()
                match_branch = next((b for b in branches_list if b['name'].lower() == branch_raw.lower()), None)
                if match_branch:
                    branch_id = match_branch['id']
        role_id = None
        if role_raw:
            if role_raw.isdigit():
                role_id = int(role_raw)
            else:
                roles_list = database.get_roles()
                match_role = next((r for r in roles_list if r['name'].lower() == role_raw.lower()), None)
                if match_role:
                    role_id = match_role['id']
        department_id = None
        if department_raw:
            if department_raw.isdigit():
                department_id = int(department_raw)
            else:
                departments_list = database.get_departments()
                match_department = next((d for d in departments_list if d['name'].lower() == department_raw.lower()), None)
                if match_department:
                    department_id = match_department['id']
        error = None
        try:
            database.create_employee(name, email, designation_id, manager_id, branch_id, role_id, department_id, raw_password=password)
        except Exception:
            error = 'An error occurred while creating the employee.'
        employees = database.get_employees()
        designations = database.get_designations()
        valid_managers = employees
        branches = database.get_branches()
        roles = database.get_roles()
        departments = database.get_departments()
        current_user = database.get_employee(session['user_id']) if 'user_id' in session else None
        current_role_name = get_role_name(current_user)
        return render_template(
            'employees.html',
            employees=employees,
            designations=designations,
            error=error,
            valid_managers=valid_managers,
            branches=branches,
            roles=roles,
            departments=departments,
            current_user=current_user,
            current_role_name=current_role_name
        )

    @app.route('/employees/update/<int:emp_id>', methods=['GET', 'POST'])
    def update_employee(emp_id):
        if request.method == 'POST':
            name = request.form['name']
            email = request.form['email']
            designation_id = int(request.form['designation_id'])
            manager_raw = request.form.get('manager_id') or None
            branch_raw = request.form.get('branch_id') or None
            role_raw = request.form.get('role_id') or None
            department_raw = request.form.get('department_id') or None

            resolved_manager = None
            if manager_raw:
                if manager_raw.isdigit():
                    resolved_manager = int(manager_raw)
                else:
                    employees_list = database.get_employees()
                    match_manager = next((e for e in employees_list if e['name'].lower() == manager_raw.lower() or e['email'].lower() == manager_raw.lower()), None)
                    if match_manager:
                        resolved_manager = match_manager['id']

            resolved_branch = None
            if branch_raw:
                if branch_raw.isdigit():
                    resolved_branch = int(branch_raw)
                else:
                    branches_list = database.get_branches()
                    match_branch = next((b for b in branches_list if b['name'].lower() == branch_raw.lower()), None)
                    if match_branch:
                        resolved_branch = match_branch['id']

            resolved_role = None
            if role_raw:
                if role_raw.isdigit():
                    resolved_role = int(role_raw)
                else:
                    roles_list = database.get_roles()
                    match_role = next((r for r in roles_list if r['name'].lower() == role_raw.lower()), None)
                    if match_role:
                        resolved_role = match_role['id']

            resolved_department = None
            if department_raw:
                if department_raw.isdigit():
                    resolved_department = int(department_raw)
                else:
                    departments_list = database.get_departments()
                    match_department = next((d for d in departments_list if d['name'].lower() == department_raw.lower()), None)
                    if match_department:
                        resolved_department = match_department['id']

            database.update_employee(emp_id, name, email, designation_id, resolved_manager, resolved_branch, resolved_role, resolved_department)
            return redirect(url_for('employees'))
        emp = database.get_employee(emp_id)
        employees = database.get_employees()
        designations = database.get_designations()
        valid_managers = [e for e in employees if e['id'] != emp_id]
        branches = database.get_branches()
        roles = database.get_roles()
        departments = database.get_departments()
        current_user = database.get_employee(session['user_id']) if 'user_id' in session else None
        current_role_name = get_role_name(current_user)
        return render_template(
            'employees.html',
            employees=employees,
            designations=designations,
            edit_employee=emp,
            valid_managers=valid_managers,
            branches=branches,
            roles=roles,
            departments=departments,
            current_user=current_user,
            current_role_name=current_role_name
        )

    @app.route('/employees/delete/<int:emp_id>')
    def delete_employee(emp_id):
        database.delete_employee(emp_id)
        return redirect(url_for('employees'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']
            user = database.get_employee_by_email_and_password(email, password)
            if user:
                session['user_email'] = email
                session['user_id'] = user['id']
                return redirect(url_for('tasks'))
            else:
                error = 'Invalid email or password.'
        return render_template('login.html', error=error)

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/change_password', methods=['GET','POST'])
    def change_password():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        current_user = database.get_employee(session['user_id'])
        error = None
        success = None
        if request.method == 'POST':
            current_pw = request.form.get('current_password','')
            new_pw = request.form.get('new_password','')
            confirm_pw = request.form.get('confirm_password','')
            # Verify current password
            if not database.get_employee_by_email_and_password(current_user['email'], current_pw):
                error = 'Current password incorrect.'
            elif not new_pw:
                error = 'New password required.'
            elif new_pw != confirm_pw:
                error = 'New password and confirmation do not match.'
            elif len(new_pw) < 6:
                error = 'New password must be at least 6 characters.'
            else:
                try:
                    if hasattr(database,'update_employee_password'):
                        database.update_employee_password(current_user['id'], new_pw)
                        success = 'Password updated successfully.'
                except Exception:
                    error = 'Failed to update password.'
        return render_template('change_password.html', current_user=current_user, error=error, success=success)

    @app.route('/profile', methods=['GET'])
    def profile():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user_id = session['user_id']
        current_user = database.get_employee(user_id)
        employees = database.get_employees()
        profile_entry = next((e for e in employees if e['id'] == user_id), None)
        manager_name = profile_entry.get('manager_name') if profile_entry else None
        designation_name = profile_entry.get('designation') if profile_entry else None
        branch_name = profile_entry.get('branch_name') if profile_entry else None
        role_name = profile_entry.get('role_name') if profile_entry else None
        department_name = profile_entry.get('department_name') if profile_entry else None
        direct_reports = [e for e in employees if e.get('manager_id') == user_id]
        subordinate_ids = []
        if hasattr(database, 'get_subordinate_employee_ids'):
            subordinate_ids = database.get_subordinate_employee_ids(user_id)
        team_size = len(subordinate_ids)
        my_tasks = database.get_tasks_by_employee(user_id)
        total_tasks = len(my_tasks)
        completed_tasks = sum(1 for t in my_tasks if str(t.get('status','')).lower() == 'completed')
        active_tasks = sum(1 for t in my_tasks if str(t.get('status','')).lower() in {'todo', 'in progress', 'blocked'})
        progress_values = []
        for t in my_tasks:
            current_progress = t.get('current_progress') or 0
            target = t.get('target') or 0
            try:
                current_progress = float(current_progress)
            except (TypeError, ValueError):
                current_progress = 0.0
            try:
                target = float(target)
            except (TypeError, ValueError):
                target = 0.0
            pct = (current_progress / target * 100) if target else 0.0
            progress_values.append(pct)
        avg_progress = sum(progress_values) / len(progress_values) if progress_values else 0.0
        pending_updates_total = 0
        task_ids = [t.get('id') for t in my_tasks if t.get('id')]
        if task_ids:
            pending_counts = database.get_pending_update_counts(task_ids)
            pending_updates_total = sum(pending_counts.values())
        return render_template(
            'profile.html',
            current_user=current_user,
            profile=profile_entry or current_user,
            manager_name=manager_name,
            designation_name=designation_name,
            branch_name=branch_name,
            role_name=role_name,
            department_name=department_name,
            direct_reports=direct_reports,
            team_size=team_size,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            active_tasks=active_tasks,
            avg_progress=avg_progress,
            pending_updates_total=pending_updates_total
        )

    @app.route('/tasks', methods=['GET'])
    def tasks():
        if 'user_email' not in session:
            return redirect(url_for('login'))
        # Generate due recurring tasks before listing
        try:
            if hasattr(database, 'generate_due_recurring_tasks'):
                database.generate_due_recurring_tasks()
        except Exception as e:
            print(f"[WARN] Recurring task generation failed: {e}")
        user_id = session['user_id']
        all_tasks = database.get_tasks_by_employee(user_id)
        employees = database.get_employees()
        current_user = database.get_employee(user_id)
        current_role_name = get_role_name(current_user)
        status_filter = request.args.get('status_filter','all')
        for t in all_tasks:
            current_val = t.get('current_progress') or 0
            try:
                current_val = float(current_val)
            except (TypeError, ValueError):
                current_val = 0.0
            t['current_progress'] = current_val
            t['progress'] = (current_val / t['target'] * 100) if t['target'] else 0
        # Get subordinates based on managerial tree (not just designation level)
        subordinate_ids = []
        if hasattr(database, 'get_subordinate_employee_ids'):
            subordinate_ids = database.get_subordinate_employee_ids(current_user['id'])
        subordinates = [e for e in employees if e['id'] in subordinate_ids]
        subordinate_tasks = []
        for emp in subordinates:
            emp_tasks = database.get_tasks_by_employee(emp['id'])
            for t in emp_tasks:
                t['employee_name'] = emp['name']
                current_val = t.get('current_progress') or 0
                try:
                    current_val = float(current_val)
                except (TypeError, ValueError):
                    current_val = 0.0
                t['current_progress'] = current_val
                t['progress'] = (current_val / t['target'] * 100) if t['target'] else 0
                subordinate_tasks.append(t)
        if status_filter and status_filter != 'all':
            all_tasks = [t for t in all_tasks if t.get('status') == status_filter]
            subordinate_tasks = [t for t in subordinate_tasks if t.get('status') == status_filter]
        pending_counts = {}
        task_ids_for_counts = list({t['id'] for t in (all_tasks + subordinate_tasks)})
        if task_ids_for_counts:
            pending_counts = database.get_pending_update_counts(task_ids_for_counts)
        for t in all_tasks:
            t['pending_updates_count'] = pending_counts.get(t['id'], 0)
        for t in subordinate_tasks:
            t['pending_updates_count'] = pending_counts.get(t['id'], 0)
        allowed_assignee_ids = {current_user['id']} | set(subordinate_ids)
        allowed_copy_assignees = [e for e in employees if e['id'] in allowed_assignee_ids]
        return render_template(
            'tasks.html',
            tasks=all_tasks,
            employees=employees,
            current_user=current_user,
            subordinate_tasks=subordinate_tasks,
            status_filter=status_filter,
            allowed_copy_assignees=allowed_copy_assignees,
            current_role_name=current_role_name
        )

    @app.route('/tasks/export', methods=['GET'])
    def export_tasks():
        if 'user_email' not in session:
            return redirect(url_for('login'))
        user_id = session['user_id']
        employees = database.get_employees()
        current_user = database.get_employee(user_id)
        # own tasks
        own_tasks = database.get_tasks_by_employee(user_id)
        for t in own_tasks:
            current_val = t.get('current_progress') or 0
            try:
                current_val = float(current_val)
            except (TypeError, ValueError):
                current_val = 0.0
            t['current_progress'] = current_val
            t['progress'] = (current_val / t['target'] * 100) if t['target'] else 0
        # subordinate tasks via managerial tree
        subordinate_ids = []
        if hasattr(database, 'get_subordinate_employee_ids'):
            subordinate_ids = database.get_subordinate_employee_ids(current_user['id'])
        subordinates = [e for e in employees if e['id'] in subordinate_ids]
        subordinate_tasks = []
        for emp in subordinates:
            emp_tasks = database.get_tasks_by_employee(emp['id'])
            for t in emp_tasks:
                t['employee_name'] = emp['name']
                current_val = t.get('current_progress') or 0
                try:
                    current_val = float(current_val)
                except (TypeError, ValueError):
                    current_val = 0.0
                t['current_progress'] = current_val
                t['progress'] = (current_val / t['target'] * 100) if t['target'] else 0
                subordinate_tasks.append(t)
        all_export_tasks = own_tasks + subordinate_tasks
        import csv, io, datetime
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['id','name','category','type','start_date','end_date','target','current_progress','status','progress_percent','assigned_by_name','employee_name'])
        for t in all_export_tasks:
            writer.writerow([
                t.get('id'), t.get('name'), t.get('category'), t.get('type'), t.get('start_date'), t.get('end_date'),
                t.get('target'), t.get('current_progress'), t.get('status'), f"{t.get('progress',0):.2f}", t.get('assigned_by_name'), t.get('employee_name')
            ])
        from flask import make_response
        resp = make_response(output.getvalue())
        resp.headers['Content-Disposition'] = f"attachment; filename=tasks_export_{datetime.date.today().isoformat()}.csv"
        resp.headers['Content-Type'] = 'text/csv'
        return resp

    @app.route('/tasks/template', methods=['GET'])
    def tasks_template():
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['name','category','type','start_date','end_date','target','status','assigned_to','current_progress','recurrence_frequency','recurrence_interval','recurrence_stop_date'])
        from flask import make_response
        resp = make_response(output.getvalue())
        resp.headers['Content-Disposition'] = 'attachment; filename=tasks_upload_template.csv'
        resp.headers['Content-Type'] = 'text/csv'
        return resp

    @app.route('/employees/template', methods=['GET'])
    def employees_template():
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['name','email','designation_title','manager_email','branch_name','role_name','department_name','password'])
        from flask import make_response
        resp = make_response(output.getvalue())
        resp.headers['Content-Disposition'] = 'attachment; filename=employees_upload_template.csv'
        resp.headers['Content-Type'] = 'text/csv'
        return resp

    @app.route('/tasks/upload', methods=['GET','POST'])
    def upload_tasks():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        current_user = database.get_employee(session['user_id'])
        allowed_roles = {'Admin', 'Manager'}
        role_name = get_role_name(current_user)
        if current_user.get('designation_id') != 1 and role_name not in allowed_roles:
            return redirect(url_for('tasks'))
        employees = database.get_employees()
        subordinate_ids = []
        if hasattr(database,'get_subordinate_employee_ids'):
            subordinate_ids = database.get_subordinate_employee_ids(current_user['id'])
        allowed_assignees = {current_user['id']} | set(subordinate_ids)
        task_type_rows = database.get_task_types() if hasattr(database, 'get_task_types') else []
        valid_task_types = {row.get('name') for row in task_type_rows if row.get('name')}
        result = None
        errors = []
        if request.method == 'POST':
            file = request.files.get('file')
            if not file or file.filename == '':
                errors.append('No file provided.')
            else:
                import csv, io, datetime
                try:
                    content = file.read().decode('utf-8')
                    reader = csv.DictReader(io.StringIO(content))
                    created = 0
                    for i,row in enumerate(reader, start=2):
                        name = row.get('name','').strip()
                        category = row.get('category','').strip()
                        type_ = row.get('type','').strip()
                        start_date = row.get('start_date','').strip()
                        end_date = row.get('end_date','').strip()
                        target = row.get('target','').strip()
                        status = row.get('status','').strip().lower()
                        assigned_to = row.get('assigned_to','').strip()
                        current_progress = row.get('current_progress','').strip()
                        rec_freq = row.get('recurrence_frequency','').strip().lower()
                        rec_interval_raw = row.get('recurrence_interval','').strip()
                        rec_stop_date = row.get('recurrence_stop_date','').strip()

                        row_errors = []

                        def add_error(column, message):
                            row_errors.append(f"{column}: {message}")

                        if not name:
                            add_error('name', 'Value required.')
                        if not category:
                            add_error('category', 'Value required.')
                        elif category.lower() not in {'personal','team'}:
                            add_error('category', "Must be 'personal' or 'team'.")
                        if not type_:
                            add_error('type', 'Value required.')
                        elif valid_task_types and type_ not in valid_task_types:
                            add_error('type', 'Not found in configured task types.')
                        if not start_date:
                            add_error('start_date', 'Value required.')
                        if not end_date:
                            add_error('end_date', 'Value required.')
                        if not target:
                            add_error('target', 'Value required.')
                        if not status:
                            add_error('status', 'Value required.')
                        elif status not in {'todo','in progress','completed','blocked'}:
                            add_error('status', "Must be one of todo / in progress / completed / blocked.")
                        if not assigned_to:
                            add_error('assigned_to', 'Value required.')

                        target_int = None
                        if target:
                            try:
                                target_int = int(target)
                            except Exception:
                                add_error('target', 'Must be an integer.')

                        current_progress_int = 0
                        if current_progress:
                            try:
                                current_progress_int = int(current_progress)
                            except Exception:
                                add_error('current_progress', 'Must be an integer when provided.')

                        start_date_obj = None
                        if start_date:
                            try:
                                start_date_obj = datetime.datetime.strptime(start_date, '%d-%m-%Y').date()
                            except Exception:
                                add_error('start_date', 'Invalid format, expected DD-MM-YYYY.')

                        end_date_obj = None
                        if end_date:
                            try:
                                end_date_obj = datetime.datetime.strptime(end_date, '%d-%m-%Y').date()
                            except Exception:
                                add_error('end_date', 'Invalid format, expected DD-MM-YYYY.')

                        assigned_to_id = None
                        if assigned_to:
                            if assigned_to.isdigit():
                                assigned_to_id = int(assigned_to)
                            else:
                                match_emp = next((e for e in employees if e['email'].lower()==assigned_to.lower()), None)
                                if match_emp:
                                    assigned_to_id = match_emp['id']
                            if not assigned_to_id:
                                add_error('assigned_to', 'Employee not found.')
                            elif assigned_to_id not in allowed_assignees:
                                add_error('assigned_to', 'Employee is not you or within your hierarchy.')

                        if rec_freq and rec_freq not in {'daily','weekly','monthly','yearly'}:
                            add_error('recurrence_frequency', "Must be one of daily/weekly/monthly/yearly.")

                        interval_val = 1
                        if rec_interval_raw:
                            try:
                                interval_val = int(rec_interval_raw)
                            except Exception:
                                add_error('recurrence_interval', 'Must be an integer if provided.')

                        stop_date_val = None
                        if rec_stop_date:
                            try:
                                stop_date_val = datetime.datetime.strptime(rec_stop_date, '%d-%m-%Y').date().isoformat()
                            except Exception:
                                add_error('recurrence_stop_date', 'Invalid format, expected DD-MM-YYYY.')

                        if row_errors:
                            errors.append(f"Row {i}: " + '; '.join(row_errors))
                            continue

                        start_date_iso = start_date_obj.isoformat()
                        end_date_iso = end_date_obj.isoformat()
                        new_task_id = None
                        try:
                            new_task_id = database.create_task(name, category.lower(), type_, start_date_iso, end_date_iso, target_int, status, current_user['id'], assigned_to_id, current_progress=current_progress_int)
                            created += 1
                        except Exception:
                            errors.append(f'Row {i}: database error creating task.')
                            continue

                        if new_task_id and rec_freq in {'daily','weekly','monthly','yearly'}:
                            try:
                                if hasattr(database,'create_recurring_template_from_existing'):
                                    database.create_recurring_template_from_existing(name, category.lower(), type_, start_date_iso, end_date_iso, target_int, status, current_user['id'], assigned_to_id, new_task_id, rec_freq, interval_val, stop_date_val)
                            except Exception:
                                errors.append(f'Row {i}: failed to create recurrence template.')
                    result = f"Created {created} task(s)."
                except Exception:
                    errors.append('Failed to parse file.')
        return render_template('upload_tasks.html', current_user=current_user, result=result, errors=errors)

    @app.route('/employees/upload', methods=['GET','POST'])
    def upload_employees():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        current_user = database.get_employee(session['user_id'])
        allowed_roles = {'Admin', 'Manager'}
        role_name = get_role_name(current_user)
        if current_user.get('designation_id') != 1 and role_name not in allowed_roles:
            return redirect(url_for('employees'))
        designations = {d['title']: d['id'] for d in database.get_designations()}
        employees = database.get_employees()
        branches = {b['name']: b['id'] for b in database.get_branches()}
        roles = {r['name']: r['id'] for r in database.get_roles()}
        departments = {d['name']: d['id'] for d in database.get_departments()}
        email_to_id = {e['email'].lower(): e['id'] for e in employees}
        result = None
        errors = []
        if request.method == 'POST':
            file = request.files.get('file')
            if not file or file.filename == '':
                errors.append('No file provided.')
            else:
                import csv, io
                try:
                    content = file.read().decode('utf-8')
                    reader = csv.DictReader(io.StringIO(content))
                    created = 0
                    for i,row in enumerate(reader, start=2):
                        name = row.get('name','').strip()
                        email = row.get('email','').strip()
                        designation_title = row.get('designation_title','').strip()
                        manager_email = row.get('manager_email','').strip()
                        branch_name = row.get('branch_name','').strip()
                        role_name = row.get('role_name','').strip()
                        department_name = row.get('department_name','').strip()
                        password = row.get('password','changeme').strip() or 'changeme'

                        row_errors = []

                        def add_error(column, message):
                            row_errors.append(f"{column}: {message}")

                        if not name:
                            add_error('name', 'Value required.')
                        if not email:
                            add_error('email', 'Value required.')
                        elif email.lower() in email_to_id:
                            add_error('email', 'Already exists.')
                        if not designation_title:
                            add_error('designation_title', 'Value required.')

                        designation_id = None
                        if designation_title:
                            designation_id = designations.get(designation_title)
                            if not designation_id and designation_title.isdigit():
                                designation_id = int(designation_title)
                            elif not designation_id:
                                add_error('designation_title', 'Not found in designations list.')

                        manager_id = None
                        if manager_email:
                            manager_id = email_to_id.get(manager_email.lower())
                            if not manager_id:
                                add_error('manager_email', 'Manager email not found.')

                        branch_id = None
                        if branch_name:
                            branch_id = branches.get(branch_name)
                            if not branch_id and branch_name.isdigit():
                                branch_id = int(branch_name)
                            elif not branch_id:
                                add_error('branch_name', f'Branch "{branch_name}" not found.')

                        role_id = None
                        if role_name:
                            role_id = roles.get(role_name)
                            if not role_id and role_name.isdigit():
                                role_id = int(role_name)
                            elif not role_id:
                                add_error('role_name', f'Role "{role_name}" not found.')

                        department_id = None
                        if department_name:
                            department_id = departments.get(department_name)
                            if not department_id and department_name.isdigit():
                                department_id = int(department_name)
                            elif not department_id:
                                add_error('department_name', f'Department "{department_name}" not found.')

                        if row_errors:
                            errors.append(f"Row {i}: " + '; '.join(row_errors))
                            continue

                        try:
                            database.create_employee(name, email, designation_id, manager_id, branch_id, role_id, department_id, raw_password=password)
                            created += 1
                            email_to_id[email.lower()] = -1
                        except Exception:
                            errors.append(f'Row {i}: DB error creating employee.')
                    result = f"Created {created} employee(s)."
                except Exception:
                    errors.append('Failed to parse file.')
        return render_template('upload_employees.html', current_user=current_user, result=result, errors=errors)

    @app.route('/tasks/assign', methods=['GET', 'POST'])
    def assign_task():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        employees = database.get_employees()
        error = None
        task_types = database.get_task_types() if hasattr(database, 'get_task_types') else []
        task_type_names = [t.get('name') for t in task_types if t.get('name')]
        current_user = database.get_employee(session['user_id'])
        subordinate_ids = []
        if hasattr(database, 'get_subordinate_employee_ids'):
            subordinate_ids = database.get_subordinate_employee_ids(current_user['id'])
        assignable_employees = [current_user] + [e for e in employees if e['id'] in subordinate_ids]
        if request.method == 'POST':
            name = request.form['name']
            category = request.form['category']
            type_ = request.form.get('type', '').strip()
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            target = int(request.form['target'])
            status = request.form['status']
            current_progress = int(request.form['current_progress'])
            assigned_by = session['user_id']
            assigned_to = int(request.form['assigned_to'])
            if not task_type_names:
                error = 'No task types have been configured. Please contact an administrator.'
            elif not type_:
                error = 'Task type is required.'
            elif type_ not in task_type_names:
                error = 'Selected task type is not available.'
            if assigned_to not in [e['id'] for e in assignable_employees]:
                error = 'You can only assign tasks to subordinates.'
            if not error:
                try:
                    task_id = database.create_task(name, category, type_, start_date, end_date, target, status, assigned_by, assigned_to, current_progress=current_progress)
                    # Handle recurrence template creation
                    freq = request.form.get('recurrence_frequency') or ''
                    interval = int(request.form.get('recurrence_interval') or 1)
                    stop_date = request.form.get('recurrence_stop_date') or None
                    if freq in ['daily','weekly','monthly','yearly']:
                        try:
                            # Create template referencing the already created first occurrence (avoid duplicate task)
                            if hasattr(database, 'create_recurring_template_from_existing'):
                                database.create_recurring_template_from_existing(name, category, type_, start_date, end_date, target, status, assigned_by, assigned_to, task_id, freq, interval, stop_date)
                        except Exception as re:
                            print(f"[WARN] Failed to create recurrence template: {re}")
                    return redirect(url_for('tasks'))
                except Exception as e:
                    error = 'Error assigning task.'
        return render_template('assign_task.html', employees=assignable_employees, error=error, task_types=task_types, current_user=current_user)

    @app.route('/tasks/update_progress/<int:task_id>', methods=['POST'])
    def update_task_progress(task_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        status_input = request.form.get('status','').strip()
        update_value_raw = request.form.get('update_value','').strip()
        customer_name = request.form.get('customer_name','').strip()
        customer_location = request.form.get('customer_location','').strip()
        customer_business_nature = request.form.get('customer_business_nature','').strip()
        customer_response = request.form.get('customer_response','').strip()
        remarks = request.form.get('remarks','').strip()
        try:
            update_value = Decimal(update_value_raw) if update_value_raw else Decimal('0')
        except (InvalidOperation, TypeError):
            update_value = Decimal('0')
        # Update task progress/status using active Postgres backend
        task = database.get_task(task_id)
        if task:
            status = status_input or task.get('status') or 'todo'
            changed_by = session.get('user_id')
            try:
                database.create_task_update(
                    task_id,
                    changed_by,
                    update_value,
                    status,
                    customer_name,
                    customer_location,
                    customer_business_nature,
                    customer_response,
                    remarks
                )
            except Exception as e:
                print(f"[WARN] Failed to log task update: {e}")
        return redirect(url_for('tasks'))

    @app.route('/tasks/<int:task_id>/updates', methods=['GET'])
    def view_task_updates(task_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        task = database.get_task(task_id)
        if not task:
            return redirect(url_for('tasks'))
        updates = database.get_task_updates(task_id)
        total_progress = database.get_task_update_total(task_id)
        current_user = database.get_employee(session['user_id'])
        employees = database.get_employees()
        employees_by_id = {e['id']: e for e in employees}
        emp_map = {emp_id: emp['name'] for emp_id, emp in employees_by_id.items()}
        assigned_to_name = emp_map.get(task['assigned_to'], task['assigned_to']) if task.get('assigned_to') else ''
        pending_notice = request.args.get('pending') == '1'
        pending_updates = 0
        for update in updates:
            if not update.get('updated_by_name') and update.get('updated_by'):
                update['updated_by_name'] = emp_map.get(update['updated_by'], update['updated_by'])
            if update.get('approved_by') and not update.get('approved_by_name'):
                approver = employees_by_id.get(update['approved_by'])
                if approver:
                    update['approved_by_name'] = approver.get('name')
            if update.get('rejected_by') and not update.get('rejected_by_name'):
                rejector = employees_by_id.get(update['rejected_by'])
                if rejector:
                    update['rejected_by_name'] = rejector.get('name')
            approver_names = []
            for emp in employees:
                if emp and emp.get('id') and can_user_approve_update(emp, task, update, employees_by_id):
                    name = emp.get('name')
                    if name and name not in approver_names:
                        approver_names.append(name)
            update['approver_names'] = sorted(approver_names, key=lambda n: n.lower())
            update['can_approve'] = False
            is_pending = not update.get('approved') and not update.get('rejected')
            if is_pending:
                pending_updates += 1
                if can_user_approve_update(current_user, task, update, employees_by_id):
                    update['can_approve'] = True
            else:
                update['can_approve'] = False
        return render_template(
            'task_updates.html',
            task=task,
            updates=updates,
            assigned_to_name=assigned_to_name,
            total_progress=total_progress,
            current_user=current_user,
            pending_updates=pending_updates,
            pending_notice=pending_notice
        )

    @app.route('/task_updates/<int:update_id>/approve', methods=['POST'])
    def approve_task_update(update_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        current_user = database.get_employee(session['user_id'])
        update = database.get_task_update(update_id)
        if not update:
            return redirect(url_for('tasks'))
        task = database.get_task(update['task_id'])
        if not task:
            return redirect(url_for('tasks'))
        if update.get('approved'):
            return redirect(url_for('view_task_updates', task_id=task['id']))
        if not can_user_approve_update(current_user, task, update):
            abort(403)
        try:
            task_id, total_progress, status = database.approve_task_update(update_id, current_user['id'])
            new_status = status or task.get('status')
            database.update_task_progress_and_status(task_id, total_progress, new_status, current_user['id'])
        except Exception as e:
            print(f"[WARN] Failed to approve task update {update_id}: {e}")
        return redirect(url_for('view_task_updates', task_id=task['id']))

    @app.route('/task_updates/<int:update_id>/reject', methods=['POST'])
    def reject_task_update(update_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        current_user = database.get_employee(session['user_id'])
        update = database.get_task_update(update_id)
        if not update:
            return redirect(url_for('tasks'))
        task = database.get_task(update['task_id'])
        if not task:
            return redirect(url_for('tasks'))
        if update.get('approved') or update.get('rejected'):
            return redirect(url_for('view_task_updates', task_id=task['id']))
        if not can_user_approve_update(current_user, task, update):
            abort(403)
        comment = request.form.get('comment', '').strip()
        if not comment:
            comment = 'No comment provided.'
        try:
            task_id, total_progress, _ = database.reject_task_update(update_id, current_user['id'], comment)
            database.update_task_progress_and_status(task_id, total_progress, task.get('status'), current_user['id'])
        except Exception as e:
            print(f"[WARN] Failed to reject task update {update_id}: {e}")
        return redirect(url_for('view_task_updates', task_id=task['id']))

    @app.route('/tasks/copy_bulk', methods=['POST'])
    def copy_tasks_bulk():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        current_user = database.get_employee(session['user_id'])
        raw_ids = request.form.getlist('task_ids')
        selected_ids = []
        for raw in raw_ids:
            try:
                selected_ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        if not selected_ids:
            return redirect(url_for('tasks'))
        selected_ids = list(dict.fromkeys(selected_ids))
        subordinate_ids = []
        if hasattr(database, 'get_subordinate_employee_ids'):
            subordinate_ids = database.get_subordinate_employee_ids(current_user['id'])
        allowed_assignee_ids = {current_user['id']} | set(subordinate_ids)
        assigned_to_override = None
        override_raw = request.form.get('assigned_to_override', '').strip()
        if override_raw:
            try:
                candidate = int(override_raw)
                if candidate in allowed_assignee_ids:
                    assigned_to_override = candidate
            except ValueError:
                assigned_to_override = None
        created_count = 0
        for task_id in selected_ids:
            task = database.get_task(task_id)
            if not task:
                continue
            can_copy = (
                current_user.get('designation_id') == 1 or
                task.get('assigned_by') == current_user['id'] or
                task.get('assigned_to') == current_user['id'] or
                task.get('assigned_to') in subordinate_ids
            )
            if not can_copy:
                continue
            new_assigned_to = assigned_to_override or task.get('assigned_to')
            if new_assigned_to not in allowed_assignee_ids:
                continue
            target_value = task.get('target') or 0
            try:
                target_value = int(target_value)
            except (TypeError, ValueError):
                try:
                    target_value = int(float(target_value))
                except (TypeError, ValueError):
                    target_value = 0
            try:
                new_task_id = database.create_task(
                    f"{task.get('name')} (Copy)",
                    task.get('category'),
                    task.get('type'),
                    task.get('start_date'),
                    task.get('end_date'),
                    target_value,
                    task.get('status') or 'todo',
                    current_user['id'],
                    new_assigned_to,
                    current_progress=0
                )
                try:
                    database.log_task_copy(task, new_task_id, current_user['id'])
                except Exception:
                    pass
                created_count += 1
            except Exception as e:
                print(f"[WARN] Failed to bulk copy task {task_id}: {e}")
        return redirect(url_for('tasks'))

    @app.route('/tasks/<int:task_id>/update', methods=['GET', 'POST'])
    def task_update_form(task_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        task = database.get_task(task_id)
        if not task:
            return redirect(url_for('tasks'))
        employees = database.get_employees()
        current_user = database.get_employee(session['user_id'])
        emp_map = {e['id']: e['name'] for e in employees}
        assigned_to_name = emp_map.get(task['assigned_to'], task['assigned_to']) if task.get('assigned_to') else ''
        total_progress = database.get_task_update_total(task_id)
        if request.method == 'POST':
            status_input = request.form.get('status','').strip()
            update_value_raw = request.form.get('update_value','').strip()
            customer_name = request.form.get('customer_name','').strip()
            customer_location = request.form.get('customer_location','').strip()
            customer_business_nature = request.form.get('customer_business_nature','').strip()
            customer_response = request.form.get('customer_response','').strip()
            remarks = request.form.get('remarks','').strip()
            try:
                update_value = Decimal(update_value_raw) if update_value_raw else Decimal('0')
            except (InvalidOperation, TypeError):
                update_value = Decimal('0')
            status = status_input or task.get('status') or 'todo'
            changed_by = current_user['id']
            try:
                database.create_task_update(
                    task_id,
                    changed_by,
                    update_value,
                    status,
                    customer_name,
                    customer_location,
                    customer_business_nature,
                    customer_response,
                    remarks
                )
            except Exception as e:
                print(f"[WARN] Failed to log task update: {e}")
            return redirect(url_for('view_task_updates', task_id=task_id, pending='1'))
        return render_template('task_update_form.html', task=task, assigned_to_name=assigned_to_name, total_progress=total_progress, current_user=current_user)

    @app.route('/tasks/edit/<int:task_id>', methods=['GET','POST'])
    def edit_task(task_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        task = database.get_task(task_id)
        if not task:
            return redirect(url_for('tasks'))
        current_user = database.get_employee(session['user_id'])
        # Permission check: Only creator (assigned_by) or top designation (id==1)
        if not (current_user['id'] == task['assigned_by'] or current_user['designation_id'] == 1):
            return redirect(url_for('tasks'))
        # Restrict selectable assignees to self + managerial subordinates
        all_emps = database.get_employees()
        subordinate_ids = []
        if hasattr(database, 'get_subordinate_employee_ids'):
            subordinate_ids = database.get_subordinate_employee_ids(current_user['id'])
        employees = [e for e in all_emps if e['id'] == current_user['id'] or e['id'] in subordinate_ids]
        if request.method == 'POST':
            name = request.form['name']
            category = request.form['category']
            type_ = request.form['type']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            target = int(request.form['target'])
            status = request.form['status']
            current_progress = int(request.form['current_progress'])
            assigned_to = int(request.form['assigned_to'])
            allowed_ids = {e['id'] for e in employees}
            if assigned_to not in allowed_ids:
                return redirect(url_for('tasks'))
            database.update_task(task_id, name, category, type_, start_date, end_date, target, status, assigned_to, current_progress, current_user['id'])
            return redirect(url_for('tasks'))
        # annotate for display
        assigned_to_emp = next((e for e in employees if e['id']==task['assigned_to']), None)
        assigned_to_name = assigned_to_emp['name'] if assigned_to_emp else task['assigned_to']
        return render_template('edit_task.html', task=task, employees=employees, assigned_to_name=assigned_to_name, current_user=current_user)

    @app.route('/tasks/copy/<int:task_id>', methods=['GET','POST'])
    def copy_task(task_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        original = database.get_task(task_id)
        if not original:
            return redirect(url_for('tasks'))
        current_user = database.get_employee(session['user_id'])
        # Allowed assignees: self + managerial subordinates
        all_emps = database.get_employees()
        subordinate_ids = []
        if hasattr(database, 'get_subordinate_employee_ids'):
            subordinate_ids = database.get_subordinate_employee_ids(current_user['id'])
        employees = [e for e in all_emps if e['id'] == current_user['id'] or e['id'] in subordinate_ids]
        if request.method == 'POST':
            name = request.form['name']
            category = request.form['category']
            type_ = request.form['type']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            target = int(request.form['target'])
            status = request.form['status']
            assigned_to = int(request.form['assigned_to'])
            # progress reset to 0 for new copy unless overridden
            current_progress = int(request.form.get('current_progress', 0))
            allowed_ids = {e['id'] for e in employees}
            if assigned_to not in allowed_ids:
                return redirect(url_for('tasks'))
            new_task_id = database.create_task(name, category, type_, start_date, end_date, target, status, current_user['id'], assigned_to, current_progress=current_progress)
            try:
                database.log_task_copy(original, new_task_id, current_user['id'])
            except Exception:
                pass
            # Optional recurrence for copied task
            freq = request.form.get('recurrence_frequency') or ''
            interval = int(request.form.get('recurrence_interval') or 1)
            stop_date = request.form.get('recurrence_stop_date') or None
            if freq in ['daily','weekly','monthly','yearly']:
                try:
                    if hasattr(database, 'create_recurring_template_from_existing'):
                        database.create_recurring_template_from_existing(name, category, type_, start_date, end_date, target, status, current_user['id'], assigned_to, new_task_id, freq, interval, stop_date)
                except Exception as re:
                    print(f"[WARN] Failed to create recurrence template (copy): {re}")
            return redirect(url_for('tasks'))
        return render_template('copy_task.html', original=original, employees=employees, current_user=current_user)

    @app.route('/tasks/audit/<int:task_id>')
    def task_audit(task_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        audits = database.get_task_audit(task_id)
        employees = database.get_employees()
        emp_map = {e['id']: e['name'] for e in employees}
        for a in audits:
            a['changed_by_name'] = emp_map.get(a['changed_by'], a['changed_by'])
        task = database.get_task(task_id)
        current_user = database.get_employee(session['user_id'])
        return render_template('audit_task.html', audits=audits, task=task, current_user=current_user)

    @app.route('/tasks/report', methods=['GET'])
    def task_report():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        employees = database.get_employees()
        all_tasks = []
        current_user = database.get_employee(session['user_id']) if 'user_id' in session else None
        category = request.args.get('category')
        status = request.args.get('status')
        assigned_by = request.args.get('assigned_by')
        assigned_to = request.args.get('assigned_to')
        progress_min = request.args.get('progress_min')
        progress_max = request.args.get('progress_max')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        # Collect all tasks and annotate with names
        for emp in employees:
            emp_tasks = database.get_tasks_for_employee(emp['id'])
            for t in emp_tasks:
                t['employee_name'] = emp['name']
                assigned_by_emp = next((e for e in employees if e['id'] == t['assigned_by']), None)
                t['assigned_by_name'] = assigned_by_emp['name'] if assigned_by_emp else t['assigned_by']
                t['progress'] = (t['current_progress'] / t['target'] * 100) if t['target'] else 0
                all_tasks.append(t)
        # Apply filters
        filtered_tasks = all_tasks
        if category:
            filtered_tasks = [t for t in filtered_tasks if str(t.get('category', '')).lower() == category]
        if status:
            filtered_tasks = [t for t in filtered_tasks if str(t.get('status', '')).lower() == status]
        if assigned_by:
            filtered_tasks = [t for t in filtered_tasks if str(t['assigned_by']) == assigned_by or t.get('assigned_by_name','') == assigned_by]
        if assigned_to:
            filtered_tasks = [t for t in filtered_tasks if str(t['assigned_to']) == assigned_to or t.get('employee_name','') == assigned_to]
        if progress_min:
            filtered_tasks = [t for t in filtered_tasks if t['progress'] >= float(progress_min)]
        if progress_max:
            filtered_tasks = [t for t in filtered_tasks if t['progress'] <= float(progress_max)]
        if start_date:
            filtered_tasks = [t for t in filtered_tasks if t['start_date'] >= start_date]
        if end_date:
            filtered_tasks = [t for t in filtered_tasks if t['end_date'] <= end_date]
        num_tasks = len(filtered_tasks)
        status_counter = Counter(str(t.get('status', 'unknown')).lower() for t in filtered_tasks)
        status_order = ['todo', 'in progress', 'blocked', 'completed']
        status_labels = [label for label in status_order if label in status_counter]
        status_labels.extend([label for label in status_counter.keys() if label not in status_labels])
        status_counts = [status_counter[label] for label in status_labels]
        total_progress = sum(t['progress'] for t in filtered_tasks)
        avg_progress = round(total_progress / num_tasks, 2) if num_tasks else 0
        today = date.today()
        overdue_count = 0
        for t in filtered_tasks:
            end_val = t.get('end_date')
            end_dt = None
            if end_val:
                if isinstance(end_val, str):
                    try:
                        end_dt = date.fromisoformat(end_val)
                    except ValueError:
                        end_dt = None
                else:
                    end_dt = end_val
            if end_dt and end_dt < today and t.get('status') != 'completed':
                overdue_count += 1
        category_counter = Counter(str(t.get('category', 'uncategorized')).lower() for t in filtered_tasks)
        status_counter_dict = dict(status_counter)
        category_counter_dict = dict(category_counter)
        category_order = ['team', 'personal']
        category_labels = [label for label in category_order if label in category_counter_dict]
        category_labels.extend([label for label in category_counter_dict.keys() if label not in category_labels])
        category_counts = [category_counter_dict[label] for label in category_labels]
        status_percentages = {label: round(status_counter[label] / num_tasks * 100, 1) for label in status_labels} if num_tasks else {}
        completed_count = status_counter.get('completed', 0)
        active_count = num_tasks - completed_count
        in_progress_count = status_counter.get('in progress', 0)
        blocked_count = status_counter.get('blocked', 0)
        # Calculate top/bottom 5 for team and personal
        def get_top_bottom(tasks, category):
            emp_stats = {}
            for t in tasks:
                category_value = str(t.get('category', '')).lower()
                if category_value != category:
                    continue
                eid = t['assigned_to']
                if eid not in emp_stats:
                    emp_stats[eid] = {'name': t['employee_name'], 'percent_sum': 0, 'count': 0}
                percent = (t['current_progress'] / t['target'] * 100) if t['target'] else 0
                emp_stats[eid]['percent_sum'] += percent
                emp_stats[eid]['count'] += 1
            results = []
            for eid, stat in emp_stats.items():
                avg_percent = (stat['percent_sum'] / stat['count']) if stat['count'] else 0
                results.append({'name': stat['name'], 'avg_percent': avg_percent, 'num_tasks': stat['count']})
            results.sort(key=lambda x: x['avg_percent'], reverse=True)
            top5 = results[:5]
            bottom5 = results[-5:] if len(results) >= 5 else results[-len(results):]
            return top5, bottom5
        top5_team, bottom5_team = get_top_bottom(all_tasks, 'team')
        top5_personal, bottom5_personal = get_top_bottom(all_tasks, 'personal')
        # Prepare branch-wise chart data
        branch_chart_data = {}
        for emp in employees:
            branch = emp.get('designation') or 'Unknown'
            emp_tasks = [t for t in filtered_tasks if t['employee_name'] == emp['name']]
            if not emp_tasks:
                continue
            emp_avg_progress = sum(t['progress'] for t in emp_tasks) / len(emp_tasks)
            if branch not in branch_chart_data:
                branch_chart_data[branch] = []
            branch_chart_data[branch].append(emp_avg_progress)
        branch_labels = list(branch_chart_data.keys())
        branch_avg_progress = [sum(vals)/len(vals) for vals in branch_chart_data.values()]
        return render_template(
            'task_report.html',
            tasks=filtered_tasks,
            current_user=current_user,
            employees=employees,
            category=category,
            status=status,
            assigned_by=assigned_by,
            assigned_to=assigned_to,
            progress_min=progress_min,
            progress_max=progress_max,
            top5_team=top5_team,
            bottom5_team=bottom5_team,
            top5_personal=top5_personal,
            bottom5_personal=bottom5_personal,
            start_date=start_date,
            end_date=end_date,
            num_tasks=num_tasks,
            avg_progress=avg_progress,
            overdue_count=overdue_count,
            status_labels=status_labels,
            status_counts=status_counts,
            status_counter=status_counter_dict,
            status_percentages=status_percentages,
            category_labels=category_labels,
            category_counts=category_counts,
            category_counter=category_counter_dict,
            completed_count=completed_count,
            active_count=active_count,
            in_progress_count=in_progress_count,
            blocked_count=blocked_count,
            branch_labels=branch_labels,
            branch_avg_progress=branch_avg_progress
        )

    return app
