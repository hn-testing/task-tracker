from flask import Flask, render_template, request, redirect, url_for, session
import os
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=env_path)  # Explicit load

db_type = os.getenv('DB_TYPE','sqlite').lower()
try:
    if db_type == 'postgres':
        from app.db import database_postgres as database
    else:
        from app.db import database
except Exception as e:
    # Fallback to sqlite with warning
    from app.db import database as database
    print(f"[WARN] Failed to initialize selected DB backend '{db_type}': {e}. Falling back to sqlite.")
import os

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('../config/config.py')
    app.secret_key = 'your_secret_key_here'

    # Initialize DB and add dummy data only once at app startup
    try:
        database.init_db()
        conn = database.connect_db()
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        return app
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM designations')
    if cur.fetchone()[0] == 0:
        cur.execute('INSERT INTO designations (title, parent_id) VALUES (?, ?)', ('CEO', None))
        ceo_id = cur.lastrowid
        cur.execute('INSERT INTO designations (title, parent_id) VALUES (?, ?)', ('Head of Department', ceo_id))
        hod_id = cur.lastrowid
        cur.execute('INSERT INTO designations (title, parent_id) VALUES (?, ?)', ('Manager', hod_id))
        manager_id = cur.lastrowid
        cur.execute('INSERT INTO designations (title, parent_id) VALUES (?, ?)', ('Staff', manager_id))
        conn.commit()
    conn.close()

    @app.route('/')
    def home():
        if 'user_id' in session:
            current_user = database.get_employee(session['user_id'])
        else:
            current_user = None
        return render_template('index.html', current_user=current_user)

    @app.route('/hello')
    def hello_world():
        return 'Hello, World!'

    @app.route('/employees', methods=['GET'])
    def employees():
        employees = database.get_employees()
        designations = database.get_designations()
        valid_managers = employees
        branches = database.get_branches()
        current_user = database.get_employee(session['user_id']) if 'user_id' in session else None
        return render_template('employees.html', employees=employees, designations=designations, valid_managers=valid_managers, branches=branches, current_user=current_user)

    @app.route('/employees/create', methods=['POST'])
    def create_employee():
        name = request.form['name']
        email = request.form['email']
        designation_id = int(request.form['designation_id'])
        manager_id = request.form.get('manager_id') or None
        branch_id = request.form.get('branch_id') or None
        error = None
        try:
            database.create_employee(name, email, designation_id, int(manager_id) if manager_id else None, int(branch_id) if branch_id else None)
        except Exception as e:
            import sqlite3
            if isinstance(e, sqlite3.IntegrityError) and 'UNIQUE constraint failed: employees.email' in str(e):
                error = 'Employee with this email already exists.'
            else:
                error = 'An error occurred while creating the employee.'
        employees = database.get_employees()
        designations = database.get_designations()
        valid_managers = employees
        branches = database.get_branches()
        current_user = database.get_employee(session['user_id']) if 'user_id' in session else None
        return render_template('employees.html', employees=employees, designations=designations, error=error, valid_managers=valid_managers, branches=branches, current_user=current_user)

    @app.route('/employees/update/<int:emp_id>', methods=['GET', 'POST'])
    def update_employee(emp_id):
        if request.method == 'POST':
            name = request.form['name']
            email = request.form['email']
            designation_id = int(request.form['designation_id'])
            manager_id = request.form.get('manager_id') or None
            branch_id = request.form.get('branch_id') or None
            database.update_employee(emp_id, name, email, designation_id, int(manager_id) if manager_id else None, int(branch_id) if branch_id else None)
            return redirect(url_for('employees'))
        emp = database.get_employee(emp_id)
        employees = database.get_employees()
        designations = database.get_designations()
        valid_managers = [e for e in employees if e['id'] != emp_id]
        branches = database.get_branches()
        current_user = database.get_employee(session['user_id']) if 'user_id' in session else None
        return render_template('employees.html', employees=employees, designations=designations, edit_employee=emp, valid_managers=valid_managers, branches=branches, current_user=current_user)

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

    @app.route('/tasks', methods=['GET'])
    def tasks():
        if 'user_email' not in session:
            return redirect(url_for('login'))
        user_id = session['user_id']
        all_tasks = database.get_tasks_by_employee(user_id)
        employees = database.get_employees()
        current_user = database.get_employee(user_id)
        for t in all_tasks:
            t['progress'] = (t['current_progress'] / t['target'] * 100) if t['target'] else 0
        # Get subordinate employees
        lower_designation_ids = database.get_lower_designation_ids(current_user['designation_id'])
        subordinates = [e for e in employees if e['designation_id'] in lower_designation_ids]
        subordinate_tasks = []
        for emp in subordinates:
            emp_tasks = database.get_tasks_by_employee(emp['id'])
            for t in emp_tasks:
                t['employee_name'] = emp['name']
                t['progress'] = (t['current_progress'] / t['target'] * 100) if t['target'] else 0
                subordinate_tasks.append(t)
        return render_template('tasks.html', tasks=all_tasks, employees=employees, current_user=current_user, subordinate_tasks=subordinate_tasks)

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
            t['progress'] = (t['current_progress'] / t['target'] * 100) if t['target'] else 0
        # subordinate tasks
        lower_designation_ids = database.get_lower_designation_ids(current_user['designation_id'])
        subordinates = [e for e in employees if e['designation_id'] in lower_designation_ids]
        subordinate_tasks = []
        for emp in subordinates:
            emp_tasks = database.get_tasks_by_employee(emp['id'])
            for t in emp_tasks:
                t['employee_name'] = emp['name']
                t['progress'] = (t['current_progress'] / t['target'] * 100) if t['target'] else 0
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

    @app.route('/tasks/assign', methods=['GET', 'POST'])
    def assign_task():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        employees = database.get_employees()
        error = None
        task_types = ['Sell product1', 'Sell product2', 'Support', 'Demo', 'Other']
        current_user = database.get_employee(session['user_id'])
        current_designation_id = current_user['designation_id']
        lower_designation_ids = database.get_lower_designation_ids(current_designation_id)
        assignable_employees = [e for e in employees if e['designation_id'] in lower_designation_ids]
        if request.method == 'POST':
            name = request.form['name']
            category = request.form['category']
            type_ = request.form['type']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            target = int(request.form['target'])
            status = request.form['status']
            current_progress = int(request.form['current_progress'])
            assigned_by = session['user_id']
            assigned_to = int(request.form['assigned_to'])
            if assigned_to not in [e['id'] for e in assignable_employees]:
                error = 'You can only assign tasks to subordinates.'
            else:
                try:
                    database.create_task(name, category, type_, start_date, end_date, target, status, assigned_by, assigned_to, current_progress=current_progress)
                    return redirect(url_for('tasks'))
                except Exception as e:
                    error = 'Error assigning task.'
        return render_template('assign_task.html', employees=assignable_employees, error=error, task_types=task_types, current_user=current_user)

    @app.route('/tasks/update_progress/<int:task_id>', methods=['POST'])
    def update_task_progress(task_id):
        current_progress = int(request.form['current_progress'])
        status = request.form['status']
        from app.db import database
        database.update_task_progress_and_status(task_id, current_progress, status)
        return redirect(url_for('tasks'))

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
        employees = database.get_employees()
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
            database.update_task(task_id, name, category, type_, start_date, end_date, target, status, assigned_to, current_progress)
            return redirect(url_for('tasks'))
        # annotate for display
        assigned_to_emp = next((e for e in employees if e['id']==task['assigned_to']), None)
        assigned_to_name = assigned_to_emp['name'] if assigned_to_emp else task['assigned_to']
        return render_template('edit_task.html', task=task, employees=employees, assigned_to_name=assigned_to_name, current_user=current_user)

    @app.route('/tasks/report', methods=['GET'])
    def task_report():
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
            filtered_tasks = [t for t in filtered_tasks if t['category'] == category]
        if status:
            filtered_tasks = [t for t in filtered_tasks if t['status'] == status]
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
        # Calculate top/bottom 5 for team and personal
        def get_top_bottom(tasks, category):
            emp_stats = {}
            for t in tasks:
                if t['category'] != category:
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
            avg_progress = sum(t['progress'] for t in emp_tasks) / len(emp_tasks)
            if branch not in branch_chart_data:
                branch_chart_data[branch] = []
            branch_chart_data[branch].append(avg_progress)
        branch_labels = list(branch_chart_data.keys())
        branch_avg_progress = [sum(vals)/len(vals) for vals in branch_chart_data.values()]
        return render_template('task_report.html', tasks=filtered_tasks, current_user=current_user, employees=employees, category=category, status=status, assigned_by=assigned_by, assigned_to=assigned_to, progress_min=progress_min, progress_max=progress_max, top5_team=top5_team, bottom5_team=bottom5_team, top5_personal=top5_personal, bottom5_personal=bottom5_personal, start_date=start_date, end_date=end_date, num_tasks=num_tasks, branch_labels=branch_labels, branch_avg_progress=branch_avg_progress)

    return app
