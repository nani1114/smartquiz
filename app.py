from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import os
from functools import wraps

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'smartquiz-secret-key-2025'
app.config['SESSION_TIMEOUT'] = 1800  # 30 minutes session timeout
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# ==================== SESSION MANAGEMENT ====================

@app.before_request
def make_session_permanent():
    """Make all sessions permanent and set cache control headers"""
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=30)
    # Set cache control headers to prevent back/forward caching of protected pages
    if 'user_id' in session:
        # For authenticated users, prevent caching
        pass  # Cache headers set in after_request

@app.after_request
def set_cache_control(response):
    """Set cache control headers based on authentication status"""
    if 'user_id' in session:
        # Authenticated pages: no caching
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    else:
        # Public pages: allow public cache
        response.headers['Cache-Control'] = 'public, max-age=3600'
    return response

def session_required(role=None):
    """Decorator to require active session and optional role check"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Session expired. Please log in again.', 'error')
                return redirect(url_for('login'))
            
            if role and session.get('role') != role:
                flash('Unauthorized access', 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# MySQL Configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'admin@123',
    'database': 'smartquiz'
}

# Initialize database and create tables
def init_db():
    try:
        # Connect to MySQL without database first to create it
        temp_config = {
            'host': DB_CONFIG['host'],
            'user': DB_CONFIG['user'],
            'password': DB_CONFIG['password']
        }
        conn = mysql.connector.connect(**temp_config)
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        conn.close()
        
        # Now connect to the actual database
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''CREATE TABLE IF NOT EXISTS users
                         (id INT AUTO_INCREMENT PRIMARY KEY, 
                          username VARCHAR(255) UNIQUE NOT NULL, 
                          password VARCHAR(255) NOT NULL,
                          role VARCHAR(50) NOT NULL, 
                          email VARCHAR(255), 
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Quizzes table
        cursor.execute('''CREATE TABLE IF NOT EXISTS quizzes
                         (id INT AUTO_INCREMENT PRIMARY KEY, 
                          title VARCHAR(255) NOT NULL, 
                          description TEXT,
                          created_by INT NOT NULL, 
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                          duration INT,
                          FOREIGN KEY(created_by) REFERENCES users(id))''')
        
        # Questions table
        cursor.execute('''CREATE TABLE IF NOT EXISTS questions
                         (id INT AUTO_INCREMENT PRIMARY KEY, 
                          quiz_id INT NOT NULL, 
                          question TEXT NOT NULL,
                          option_a VARCHAR(255), 
                          option_b VARCHAR(255), 
                          option_c VARCHAR(255), 
                          option_d VARCHAR(255),
                          correct_answer VARCHAR(1), 
                          FOREIGN KEY(quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE)''')
        
        # Results table
        cursor.execute('''CREATE TABLE IF NOT EXISTS results
                         (id INT AUTO_INCREMENT PRIMARY KEY, 
                          user_id INT NOT NULL, 
                          quiz_id INT NOT NULL,
                          score INT, 
                          total_questions INT, 
                          completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                          FOREIGN KEY(user_id) REFERENCES users(id),
                          FOREIGN KEY(quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE)''')
        
        # Notifications table
        cursor.execute('''CREATE TABLE IF NOT EXISTS notifications
                         (id INT AUTO_INCREMENT PRIMARY KEY, 
                          title VARCHAR(255), 
                          message TEXT, 
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Courses table
        cursor.execute('''CREATE TABLE IF NOT EXISTS courses
                         (id INT AUTO_INCREMENT PRIMARY KEY, 
                          name VARCHAR(255) NOT NULL, 
                          description TEXT, 
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Review submissions table
        cursor.execute('''CREATE TABLE IF NOT EXISTS review_submissions
                         (id INT AUTO_INCREMENT PRIMARY KEY, 
                          user_id INT NOT NULL, 
                          title VARCHAR(255), 
                          details TEXT,
                          status VARCHAR(50) DEFAULT 'pending', 
                          submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)''')
        
        conn.commit()
        
        # Check if admin user exists, if not create it
        cursor.execute("SELECT id FROM users WHERE username = %s", ('admin',))
        if not cursor.fetchone():
            admin_password = generate_password_hash('admin123')
            cursor.execute("INSERT INTO users (username, password, role, email) VALUES (%s, %s, %s, %s)",
                          ('admin', admin_password, 'admin', 'admin@smartquiz.com'))
            conn.commit()
        
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Error initializing database: {e}")

def get_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

# Keep the database initialization in before_request (called on every request)

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session['role'] == 'lecturer':
            return redirect(url_for('lecturer_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    # Serve the template index.html as the landing page
    return render_template('index.html')

@app.route('/Admin_Login.html')
def admin_login_html():
    return render_template('Admin_Login.html')

@app.route('/Lecturer_Login.html')
def lecturer_login_html():
    return render_template('Lecturer_Login.html')

@app.route('/Student_Login.html')
def student_login_html():
    return render_template('Student_Login.html')

@app.route('/signup.html')
def signup_html():
    return render_template('signup.html')

# Serve CSS, JS, and Images from htmls folder
@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), '../../htmls/css'), filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), '../../htmls/js'), filename)

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), '../../htmls/images'), filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user and check_password_hash(user['password'], password):
                session.permanent = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']  # Use role from database, not from form
                session['login_time'] = datetime.now().isoformat()
                flash(f'Welcome back, {username}!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password', 'error')
        else:
            flash('Database connection error', 'error')
    
    # For GET requests, redirect users to the landing page which already
    # provides role-specific login pages (Student/Admin/Lecturer).
    # POST handling above remains unchanged (forms on role pages still submit to /login).
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role', 'student')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('signup.html'))
        
        conn = get_db()
        if conn:
            cursor = conn.cursor()
            try:
                hashed_password = generate_password_hash(password)
                cursor.execute("INSERT INTO users (username, password, role, email) VALUES (%s, %s, %s, %s)",
                              (username, hashed_password, role, email))
                conn.commit()
                flash('Account created successfully! Please log in.', 'success')
                return redirect(url_for('login'))
            except mysql.connector.Error as err:
                if err.errno == 1062:  # Duplicate username
                    flash('Username already exists', 'error')
                else:
                    flash(f'Error: {err}', 'error')
            finally:
                cursor.close()
                conn.close()
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
def admin():
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/dashboard')
@session_required(role='admin')
def admin_dashboard():
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT COUNT(*) as count FROM users WHERE role='student'")
    students = c.fetchone()['count']
    c.execute("SELECT COUNT(*) as count FROM users WHERE role='lecturer'")
    lecturers = c.fetchone()['count']
    c.execute("SELECT COUNT(*) as count FROM quizzes")
    quizzes = c.fetchone()['count']
    c.execute("SELECT COUNT(*) as count FROM results")
    results = c.fetchone()['count']
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         students=students, lecturers=lecturers, 
                         quizzes=quizzes, results=results)

@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id, username, email, role FROM users")
    users = c.fetchall()
    conn.close()
    
    return render_template('admin_users.html', users=users)


@app.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@session_required(role='admin')
def admin_edit_user(user_id):
    conn = get_db()
    c = conn.cursor(dictionary=True)

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            if password:
                hashed = generate_password_hash(password)
                c.execute("UPDATE users SET username=%s, email=%s, password=%s WHERE id=%s", (username, email, hashed, user_id))
            else:
                c.execute("UPDATE users SET username=%s, email=%s WHERE id=%s", (username, email, user_id))
            conn.commit()
            flash('User updated successfully.', 'success')
        except Error as e:
            conn.rollback()
            flash(f'Error updating user: {e}', 'error')
        finally:
            c.close()
            conn.close()
        return redirect(url_for('admin_users'))

    # GET
    c.execute("SELECT id, username, email, role FROM users WHERE id = %s", (user_id,))
    user = c.fetchone()
    c.close()
    conn.close()
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin_users'))

    template = 'EditLecturer.html' if user['role'] == 'lecturer' else 'EditStudent.html'
    return render_template(template, user=user, error=None)


@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@session_required(role='admin')
def admin_delete_user(user_id):

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        flash('User deleted.', 'info')
    except Error as e:
        conn.rollback()
        flash(f'Error deleting user: {e}', 'error')
    finally:
        c.close()
        conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/reports')
@session_required(role='admin')
def admin_reports():
    
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""SELECT u.username, q.title, r.score, r.total_questions, r.completed_at 
                 FROM results r 
                 JOIN users u ON r.user_id = u.id 
                 JOIN quizzes q ON r.quiz_id = q.id
                 ORDER BY r.completed_at DESC""")
    reports = c.fetchall()
    conn.close()
    
    return render_template('admin_reports.html', reports=reports)

# -------------------- Admin: Pending approvals / Approve/Reject --------------------
@app.route('/admin/pending')
@session_required(role='admin')
def admin_pending():

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id, username, email, role, created_at FROM users WHERE role = 'pending'")
    pending = c.fetchall()
    conn.close()
    return render_template('admin_pending.html', pending=pending)

@app.route('/admin/approve_user/<int:user_id>', methods=['POST'])
@session_required(role='admin')
def admin_approve_user(user_id):

    new_role = request.form.get('role', 'student')
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
    conn.commit()
    conn.close()
    flash('User approved.', 'success')
    return redirect(url_for('admin_pending'))

@app.route('/admin/reject_user/<int:user_id>', methods=['POST'])
@session_required(role='admin')
def admin_reject_user(user_id):

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    flash('User rejected and removed.', 'info')
    return redirect(url_for('admin_pending'))

# -------------------- Admin: Notifications --------------------
@app.route('/admin/notifications', methods=['GET', 'POST'])
@session_required(role='admin')
def admin_notifications():

    conn = get_db()
    c = conn.cursor(dictionary=True)
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        c.execute("INSERT INTO notifications (title, message) VALUES (%s, %s)", (title, message))
        conn.commit()
        flash('Notification created.', 'success')

    c.execute("SELECT * FROM notifications ORDER BY created_at DESC")
    notes = c.fetchall()
    conn.close()
    return render_template('admin_notifications.html', notes=notes)


@app.route('/admin/notification/<int:notification_id>/delete', methods=['POST'])
@session_required(role='admin')
def admin_delete_notification(notification_id):
    

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM notifications WHERE id = %s", (notification_id,))
        conn.commit()
        flash('Notification deleted.', 'info')
    except Error as e:
        conn.rollback()
        flash(f'Error deleting notification: {e}', 'error')
    finally:
        c.close()
        conn.close()
    return redirect(url_for('admin_notifications'))

# -------------------- Admin: Course Management --------------------
@app.route('/admin/courses', methods=['GET', 'POST'])
@session_required(role='admin')
def admin_courses():

    conn = get_db()
    c = conn.cursor(dictionary=True)
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        c.execute("INSERT INTO courses (name, description) VALUES (%s, %s)", (name, description))
        conn.commit()
        flash('Course added.', 'success')

    c.execute("SELECT * FROM courses ORDER BY created_at DESC")
    courses = c.fetchall()
    conn.close()
    return render_template('admin_courses.html', courses=courses)


@app.route('/admin/course/<int:course_id>/delete', methods=['POST'])
@session_required(role='admin')
def admin_delete_course(course_id):
    

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM courses WHERE id = %s", (course_id,))
        conn.commit()
        flash('Course deleted.', 'info')
    except Error as e:
        conn.rollback()
        flash(f'Error deleting course: {e}', 'error')
    finally:
        c.close()
        conn.close()
    return redirect(url_for('admin_courses'))

# -------------------- Admin: Review Queue --------------------
@app.route('/admin/review-queue')
@session_required(role='admin')
def admin_review_queue():

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT r.id, r.title, r.details, r.status, r.submitted_at, u.username FROM review_submissions r JOIN users u ON r.user_id = u.id ORDER BY r.submitted_at DESC")
    reviews = c.fetchall()
    conn.close()
    return render_template('admin_review_queue.html', reviews=reviews)

@app.route('/admin/review/<int:review_id>/approve', methods=['POST'])
@session_required(role='admin')
def admin_review_approve(review_id):
    

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE review_submissions SET status = %s WHERE id = %s", ('approved', review_id))
    conn.commit()
    conn.close()
    flash('Review approved.', 'success')
    return redirect(url_for('admin_review_queue'))

@app.route('/admin/review/<int:review_id>/reject', methods=['POST'])
@session_required(role='admin')
def admin_review_reject(review_id):
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE review_submissions SET status = %s WHERE id = %s", ('rejected', review_id))
    conn.commit()
    conn.close()
    flash('Review rejected.', 'info')
    return redirect(url_for('admin_review_queue'))

# ==================== LECTURER ROUTES ====================

@app.route('/lecturer/dashboard')
@session_required(role='lecturer')
def lecturer_dashboard():
    
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM quizzes WHERE created_by = %s", (session['user_id'],))
    quizzes = c.fetchall()

    # Additional metrics for lecturer: total questions across quizzes and distinct students who attempted those quizzes
    c.execute("SELECT COUNT(q.id) as total_questions FROM questions q JOIN quizzes qu ON q.quiz_id = qu.id WHERE qu.created_by = %s", (session['user_id'],))
    total_questions_row = c.fetchone()
    total_questions = total_questions_row['total_questions'] if total_questions_row else 0

    c.execute("SELECT COUNT(DISTINCT r.user_id) as total_students FROM results r JOIN quizzes qu ON r.quiz_id = qu.id WHERE qu.created_by = %s", (session['user_id'],))
    total_students_row = c.fetchone()
    total_students = total_students_row['total_students'] if total_students_row else 0

    conn.close()
    
    return render_template('lecturer_dashboard.html', quizzes=quizzes, total_questions=total_questions, total_students=total_students)

@app.route('/lecturer/create-quiz', methods=['GET', 'POST'])
@session_required(role='lecturer')
def create_quiz():
    
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        duration = request.form.get('duration', 30)
        
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO quizzes (title, description, created_by, duration) VALUES (%s, %s, %s, %s)",
                  (title, description, session['user_id'], duration))
        conn.commit()
        quiz_id = c.lastrowid
        conn.close()
        
        flash('Quiz created successfully!', 'success')
        return redirect(url_for('add_questions', quiz_id=quiz_id))
    
    return render_template('create_quiz.html')

@app.route('/lecturer/quiz/<int:quiz_id>/questions', methods=['GET', 'POST'])
@session_required(role='lecturer')
def add_questions(quiz_id):
    
    
    if request.method == 'POST':
        question = request.form.get('question')
        option_a = request.form.get('option_a')
        option_b = request.form.get('option_b')
        option_c = request.form.get('option_c')
        option_d = request.form.get('option_d')
        correct_answer = request.form.get('correct_answer')
        
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_answer) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                  (quiz_id, question, option_a, option_b, option_c, option_d, correct_answer))
        conn.commit()
        conn.close()
        
        flash('Question added successfully!', 'success')
    
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM questions WHERE quiz_id = %s", (quiz_id,))
    questions = c.fetchall()
    c.execute("SELECT title FROM quizzes WHERE id = %s", (quiz_id,))
    quiz = c.fetchone()
    conn.close()
    
    return render_template('add_questions.html', quiz_id=quiz_id, questions=questions, quiz=quiz)

@app.route('/lecturer/quiz/<int:quiz_id>/delete', methods=['POST'])
@session_required(role='lecturer')
def delete_quiz(quiz_id):
    conn = get_db()
    c = conn.cursor(dictionary=True)
    # Verify that the quiz belongs to this lecturer
    c.execute("SELECT id, created_by FROM quizzes WHERE id = %s", (quiz_id,))
    quiz = c.fetchone()
    
    if not quiz or quiz['created_by'] != session['user_id']:
        flash('You do not have permission to delete this quiz.', 'error')
        c.close()
        conn.close()
        return redirect(url_for('lecturer_dashboard'))
    
    # Delete quiz (questions will cascade delete due to ON DELETE CASCADE)
    try:
        c.execute("DELETE FROM quizzes WHERE id = %s", (quiz_id,))
        conn.commit()
        flash('Quiz deleted successfully.', 'success')
    except Error as e:
        conn.rollback()
        flash(f'Error deleting quiz: {e}', 'error')
    finally:
        c.close()
        conn.close()
    
    return redirect(url_for('lecturer_dashboard'))

# ==================== STUDENT ROUTES ====================

@app.route('/student/dashboard')
@session_required(role='student')
def student_dashboard():
    
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM quizzes")
    quizzes = c.fetchall()
    c.execute("SELECT * FROM results WHERE user_id = %s ORDER BY completed_at DESC", (session['user_id'],))
    results = c.fetchall()

    # Student metrics: average score percent across results (if any)
    c.execute("SELECT AVG(CAST(score AS FLOAT) / NULLIF(total_questions,0)) as avg_ratio FROM results WHERE user_id = %s", (session['user_id'],))
    avg_row = c.fetchone()
    avg_ratio = avg_row['avg_ratio'] if avg_row and avg_row['avg_ratio'] is not None else 0
    avg_percent = round(float(avg_ratio) * 100, 2) if avg_ratio else 0

    conn.close()
    
    return render_template('student_dashboard.html', quizzes=quizzes, results=results, avg_percent=avg_percent)

# -------------------- Admin: Analytics --------------------
@app.route('/admin/analytics')
@session_required(role='admin')
def admin_analytics():

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT COUNT(*) as total_students FROM users WHERE role='student'")
    total_students = c.fetchone()['total_students']
    c.execute("SELECT COUNT(*) as total_lecturers FROM users WHERE role='lecturer'")
    total_lecturers = c.fetchone()['total_lecturers']
    c.execute("SELECT COUNT(*) as total_quizzes FROM quizzes")
    total_quizzes = c.fetchone()['total_quizzes']
    c.execute("SELECT AVG(CAST(score AS FLOAT) / NULLIF(total_questions,0)) as avg_ratio FROM results")
    avg_row = c.fetchone()
    avg_ratio = avg_row['avg_ratio'] if avg_row and avg_row['avg_ratio'] is not None else 0
    avg_score_pct = round(float(avg_ratio) * 100, 2) if avg_ratio else 0
    conn.close()
    
    stats = {
        'total_students': total_students,
        'total_lecturers': total_lecturers,
        'total_quizzes': total_quizzes,
        'avg_score_pct': avg_score_pct
    }
    
    return render_template('admin_analytics.html', stats=stats)


@app.route('/analytics')
@session_required()
def analytics():

    conn = get_db()
    c = conn.cursor(dictionary=True)

    # Basic stats
    c.execute("SELECT COUNT(*) as total_students FROM users WHERE role='student'")
    total_students = c.fetchone()['total_students']
    c.execute("SELECT COUNT(*) as total_lecturers FROM users WHERE role='lecturer'")
    total_lecturers = c.fetchone()['total_lecturers']
    c.execute("SELECT COUNT(*) as total_quizzes FROM quizzes")
    total_quizzes = c.fetchone()['total_quizzes']
    c.execute("SELECT AVG(CAST(score AS FLOAT) / NULLIF(total_questions,0)) as avg_ratio FROM results")
    avg_row = c.fetchone()
    avg_ratio = avg_row['avg_ratio'] if avg_row and avg_row['avg_ratio'] is not None else 0
    avg_score_pct = round(float(avg_ratio) * 100, 2) if avg_ratio else 0

    # Monthly stats (last 6 months)
    c.execute("SELECT DATE_FORMAT(completed_at, '%Y-%m') as month, COUNT(DISTINCT user_id) as unique_students, COUNT(*) as total_attempts FROM results WHERE completed_at >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH) GROUP BY month ORDER BY month")
    monthly_rows = c.fetchall()
    monthly_labels = [r['month'] for r in monthly_rows]
    monthly_unique_students = [r['unique_students'] for r in monthly_rows]
    monthly_total_attempts = [r['total_attempts'] for r in monthly_rows]

    # Top quizzes
    c.execute("SELECT q.title, COUNT(r.id) as attempts, AVG(CAST(r.score AS FLOAT)/NULLIF(r.total_questions,0))*100 as avg_score FROM quizzes q LEFT JOIN results r ON q.id = r.quiz_id GROUP BY q.id ORDER BY attempts DESC LIMIT 6")
    top_rows = c.fetchall()
    quiz_labels = [r['title'] for r in top_rows]
    quiz_attempts = [r['attempts'] or 0 for r in top_rows]
    quiz_avg_scores = [round(r['avg_score'] or 0,2) for r in top_rows]

    # Recent user activity (last 7 days)
    c.execute("SELECT DATE(completed_at) as date, COUNT(DISTINCT user_id) as active_students, COUNT(*) as quiz_attempts FROM results WHERE completed_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) GROUP BY DATE(completed_at) ORDER BY DATE(completed_at) DESC")
    activity_rows = c.fetchall()
    user_activity = []
    for r in activity_rows:
        user_activity.append({
            'date': r['date'],
            'active_students': r['active_students'],
            'quiz_attempts': r['quiz_attempts']
        })

    conn.close()

    stats = {
        'total_students': total_students,
        'total_lecturers': total_lecturers,
        'total_quizzes': total_quizzes,
        'avg_score_pct': avg_score_pct
    }

    return render_template('AnalyticsDashboard.html',
                           stats=stats,
                           monthly_labels=monthly_labels,
                           monthly_unique_students=monthly_unique_students,
                           monthly_total_attempts=monthly_total_attempts,
                           quiz_labels=quiz_labels,
                           quiz_attempts=quiz_attempts,
                           quiz_avg_scores=quiz_avg_scores,
                           user_activity=user_activity)

@app.route('/student/quiz/<int:quiz_id>')
@session_required(role='student')
def take_quiz(quiz_id):
    
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM quizzes WHERE id = %s", (quiz_id,))
    quiz = c.fetchone()
    c.execute("SELECT * FROM questions WHERE quiz_id = %s", (quiz_id,))
    questions = c.fetchall()
    conn.close()
    
    return render_template('take_quiz.html', quiz=quiz, questions=questions)

@app.route('/student/submit-quiz/<int:quiz_id>', methods=['POST'])
@session_required(role='student')
def submit_quiz(quiz_id):
    
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM questions WHERE quiz_id = %s", (quiz_id,))
    questions = c.fetchall()
    
    score = 0
    for q in questions:
        answer = request.form.get(f"question_{q['id']}")
        if answer == q['correct_answer']:
            score += 1
    
    c.execute("INSERT INTO results (user_id, quiz_id, score, total_questions) VALUES (%s, %s, %s, %s)",
              (session['user_id'], quiz_id, score, len(questions)))
    conn.commit()
    conn.close()
    
    flash(f'Quiz submitted! Your score: {score}/{len(questions)}', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/student/results/<int:result_id>')
@session_required(role='student')
def view_result(result_id):
    
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM results WHERE id = %s AND user_id = %s", (result_id, session['user_id']))
    result = c.fetchone()
    
    if not result:
        flash('Result not found', 'error')
        return redirect(url_for('student_dashboard'))
    
    c.execute("SELECT title FROM quizzes WHERE id = %s", (result['quiz_id'],))
    quiz = c.fetchone()
    conn.close()
    
    return render_template('result_details.html', result=result, quiz=quiz)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
