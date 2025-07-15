from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import json
import csv
import io
import re
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import os
import requests
import string

# Download NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

app = Flask(__name__)
app.secret_key = "lost-is-coding🔥123"

# Load secrets from environment or instance/config.py
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['GENAI_API_KEY'] = os.environ.get('GENAI_API_KEY')
# (Recommended: set these in your environment or in instance/config.py, which is gitignored)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()


# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    checkins = db.relationship('CheckIn', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    time_of_day = db.Column(db.String(10),
                            nullable=False)  # 'morning' or 'evening'

    # Morning check-in fields
    sleep_hours = db.Column(db.Float, nullable=True)
    sleep_quality = db.Column(db.Integer, nullable=True)  # 1-5 scale
    energy_level = db.Column(db.Integer, nullable=True)  # 1-5 scale
    morning_goal = db.Column(db.Text, nullable=True)
    anxiety_level = db.Column(db.Text, nullable=True)

    # Evening check-in fields
    goal_accomplished = db.Column(db.Boolean, nullable=True)
    mood_rating = db.Column(db.Integer, nullable=True)  # 1-5 scale
    exercise_done = db.Column(db.Boolean, nullable=True)
    what_drained_you = db.Column(db.Text, nullable=True)
    gratitude = db.Column(db.Text, nullable=True)
    day_win = db.Column(db.Boolean, nullable=True)  # Yes/No
    overall_day_rating = db.Column(db.String(10), nullable=True)  # 😀 😐 😞

    # Legacy fields (kept for backward compatibility)
    mood = db.Column(db.String(20), nullable=True)
    focus_level = db.Column(db.Integer, nullable=True)
    tasks_done = db.Column(db.Text, nullable=True)
    diet = db.Column(db.Text, nullable=True)
    exercise = db.Column(db.Text, nullable=True)
    habits = db.Column(db.Text, nullable=True)  # JSON string of habit tags

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CheckIn {self.date} {self.time_of_day}>'

    @property
    def is_morning(self):
        return self.time_of_day == 'morning'

    @property
    def is_evening(self):
        return self.time_of_day == 'evening'


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_of_day = db.Column(db.String(10), nullable=False, default='morning')
    task_name = db.Column(db.String(255), nullable=False)
    task_notes = db.Column(db.Text, nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    is_carried_over = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(50), nullable=True, default='General')
    priority = db.Column(db.String(10), nullable=False, default='Medium')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('tasks', lazy=True))

    def __repr__(self):
        return f'<Task {self.task_name} ({self.date} {self.time_of_day})>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('checkin.dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('checkin.dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


checkin_bp = Blueprint('checkin', __name__)


@checkin_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    today = date.today()
    current_hour = datetime.now().hour
    suggested_time = 'morning' if 5 <= current_hour < 12 else 'evening'
    time_of_day = request.form.get(
        'time_of_day') if request.method == 'POST' else request.args.get(
            'time', suggested_time)

    # --- MORNING CHECK-IN LOGIC ---
    if request.method == 'POST' and time_of_day == 'morning':
        # Remove existing tasks for today (avoid duplicates)
        Task.query.filter_by(user_id=current_user.id,
                             date=today,
                             time_of_day='morning').delete()
        db.session.commit()
        # Get all task fields from the form
        task_names = request.form.getlist('task_name')
        task_notes = request.form.getlist('task_notes')
        task_categories = request.form.getlist('task_category')
        task_priorities = request.form.getlist('task_priority')
        for i, name in enumerate(task_names):
            notes = task_notes[i] if i < len(task_notes) else ''
            category = task_categories[i] if i < len(
                task_categories) else 'General'
            priority = task_priorities[i] if i < len(
                task_priorities) else 'Medium'
            new_task = Task(user_id=current_user.id,
                            date=today,
                            time_of_day='morning',
                            task_name=name,
                            task_notes=notes,
                            is_completed=False,
                            is_carried_over=False,
                            category=category,
                            priority=priority)
            db.session.add(new_task)
        # Carry forward unfinished tasks from yesterday
        yesterday = today - timedelta(days=1)
        unfinished = Task.query.filter_by(user_id=current_user.id,
                                          date=yesterday,
                                          time_of_day='morning',
                                          is_completed=False).all()
        for ut in unfinished:
            # Only carry if not already carried today
            exists = Task.query.filter_by(user_id=current_user.id,
                                          date=today,
                                          time_of_day='morning',
                                          task_name=ut.task_name,
                                          is_carried_over=True).first()
            if not exists:
                t = Task(user_id=current_user.id,
                         date=today,
                         time_of_day='morning',
                         task_name=ut.task_name,
                         task_notes=ut.task_notes,
                         is_completed=False,
                         is_carried_over=True,
                         category=ut.category,
                         priority=ut.priority)
                db.session.add(t)
        db.session.commit()

    # --- EVENING CHECK-IN LOGIC ---
    if request.method == 'POST' and time_of_day == 'evening':
        # Update is_completed for today's tasks
        tasks_today = Task.query.filter_by(user_id=current_user.id,
                                           date=today,
                                           time_of_day='morning').all()
        for task in tasks_today:
            completed = request.form.get(f'task_completed_{task.id}') == '1'
            task.is_completed = completed
        db.session.commit()
        # Add new tasks for tomorrow morning (if any)
        task_names = request.form.getlist('task_name')
        task_notes = request.form.getlist('task_notes')
        task_categories = request.form.getlist('task_category')
        task_priorities = request.form.getlist('task_priority')
        tomorrow = today + timedelta(days=1)
        for i, name in enumerate(task_names):
            if not name.strip():
                continue
            notes = task_notes[i] if i < len(task_notes) else ''
            category = task_categories[i] if i < len(
                task_categories) else 'General'
            priority = task_priorities[i] if i < len(
                task_priorities) else 'Medium'
            new_task = Task(user_id=current_user.id,
                            date=tomorrow,
                            time_of_day='morning',
                            task_name=name,
                            task_notes=notes,
                            is_completed=False,
                            is_carried_over=False,
                            category=category,
                            priority=priority)
            db.session.add(new_task)
        db.session.commit()

    # --- Existing check-in logic ---
    if request.method == 'POST':
        # Get time of day (auto-detect or manual selection)
        time_of_day = request.form.get('time_of_day')
        if not time_of_day:
            # Auto-detect based on current time
            current_hour = datetime.now().hour
            time_of_day = 'morning' if 5 <= current_hour < 12 else 'evening'
        today = date.today()
        print(
            f"[DEBUG] Submitting check-in: user_id={current_user.id}, date={today}, time_of_day={time_of_day}"
        )

        # Check if check-in already exists for today and time of day
        existing_checkin = CheckIn.query.filter_by(
            user_id=current_user.id, date=today,
            time_of_day=time_of_day).first()

        # Get habits as list and convert to JSON
        habits = request.form.getlist('habits')
        habits_json = json.dumps(habits) if habits else None

        if existing_checkin:
            # Update existing check-in
            update_checkin_fields(existing_checkin, request.form, time_of_day)
            existing_checkin.habits = habits_json
            flash(f'{time_of_day.title()} check-in updated successfully!',
                  'success')
        else:
            # Create new check-in
            checkin = CheckIn(user_id=current_user.id,
                              date=today,
                              time_of_day=time_of_day,
                              habits=habits_json)
            update_checkin_fields(checkin, request.form, time_of_day)
            db.session.add(checkin)
            flash(f'{time_of_day.title()} check-in submitted successfully!',
                  'success')

        db.session.commit()
        return redirect(url_for('checkin.dashboard'))

    # Get today's check-ins if they exist
    morning_checkin = CheckIn.query.filter_by(user_id=current_user.id,
                                              date=today,
                                              time_of_day='morning').first()
    evening_checkin = CheckIn.query.filter_by(user_id=current_user.id,
                                              date=today,
                                              time_of_day='evening').first()
    # Get today's morning tasks for display
    morning_tasks = Task.query.filter_by(user_id=current_user.id,
                                         date=today,
                                         time_of_day='morning').all()
    evening_tasks = morning_tasks  # For now, evening tasks are today's morning tasks

    return render_template('submit.html',
                           morning_checkin=morning_checkin,
                           evening_checkin=evening_checkin,
                           suggested_time=suggested_time,
                           morning_tasks=morning_tasks,
                           evening_tasks=evening_tasks)


def update_checkin_fields(checkin, form_data, time_of_day):
    """Update check-in fields based on time of day"""
    if time_of_day == 'morning':
        checkin.sleep_hours = float(form_data.get('sleep_hours', 0))
        checkin.sleep_quality = int(form_data.get('sleep_quality', 3))
        checkin.energy_level = int(form_data.get('energy_level', 3))
        checkin.morning_goal = form_data.get('morning_goal', '')
        checkin.anxiety_level = form_data.get('anxiety_level', '')
    else:  # evening
        checkin.goal_accomplished = form_data.get('goal_accomplished') == 'yes'
        checkin.mood_rating = int(form_data.get('mood_rating', 3))
        checkin.exercise_done = form_data.get('exercise_done') == 'yes'
        checkin.what_drained_you = form_data.get('what_drained_you', '')
        checkin.gratitude = form_data.get('gratitude', '')
        checkin.day_win = form_data.get('day_win') == 'yes'
        checkin.overall_day_rating = form_data.get('overall_day_rating', '😐')

    # Legacy field updates for backward compatibility
    if form_data.get('mood'):
        checkin.mood = form_data.get('mood')
    if form_data.get('focus_level'):
        checkin.focus_level = int(form_data.get('focus_level'))
    if form_data.get('tasks_done'):
        checkin.tasks_done = form_data.get('tasks_done')
    if form_data.get('diet'):
        checkin.diet = form_data.get('diet')
    if form_data.get('exercise'):
        checkin.exercise = form_data.get('exercise')


@checkin_bp.route('/dashboard')
@login_required
def dashboard():
    # Get the latest 14 check-ins (7 days worth of morning + evening)
    checkins = CheckIn.query.filter_by(user_id=current_user.id).order_by(
        CheckIn.date.desc(), CheckIn.time_of_day.desc()).limit(14).all()

    # Get today's check-ins if they exist
    today = date.today()
    morning_checkin = CheckIn.query.filter_by(user_id=current_user.id,
                                              date=today,
                                              time_of_day='morning').first()
    evening_checkin = CheckIn.query.filter_by(user_id=current_user.id,
                                              date=today,
                                              time_of_day='evening').first()

    # Separate morning and evening check-ins
    morning_checkins = [c for c in checkins if c.is_morning]
    evening_checkins = [c for c in checkins if c.is_evening]

    # Calculate insights for both morning and evening
    morning_insights = generate_morning_insights(morning_checkins)
    evening_insights = generate_evening_insights(evening_checkins)

    # Prepare data for charts
    chart_data = prepare_chart_data(checkins, morning_checkins,
                                    evening_checkins)

    # Generate insights
    insights = generate_insights(checkins)

    # Get keyword analysis
    keyword_data = analyze_keywords(checkins)

    # Get habit analysis
    habit_data = analyze_habits(checkins)

    # Get motivational quote
    motivational_quote = get_motivational_quote()

    # Prepare heatmap dates (4 weeks x 7 days)
    heatmap_dates = []
    if checkins:
        start_date = checkins[0].date
        for week in range(4):
            week_dates = []
            for day in range(7):
                day_offset = week * 7 + day
                week_dates.append(start_date - timedelta(days=day_offset))
            heatmap_dates.append(week_dates)
    else:
        # fallback: just show last 28 days from today
        for week in range(4):
            week_dates = []
            for day in range(7):
                day_offset = week * 7 + day
                week_dates.append(today - timedelta(days=day_offset))
            heatmap_dates.append(week_dates)

    # Prepare energy/focus pairs for charting or display
    energy_levels = [
        c.energy_level for c in checkins if c.energy_level is not None
    ]
    focus_levels = [
        c.focus_level for c in checkins if c.focus_level is not None
    ]
    energy_focus_pairs = list(zip(energy_levels, focus_levels))

    # Task stats for today
    yesterday = today - timedelta(days=1)
    tasks_today = Task.query.filter_by(user_id=current_user.id,
                                       date=today,
                                       time_of_day='morning').all()
    tasks_yesterday = Task.query.filter_by(user_id=current_user.id,
                                           date=yesterday,
                                           time_of_day='morning').all()
    total_tasks = len(tasks_today)
    completed_tasks = sum(1 for t in tasks_today if t.is_completed)
    pending_tasks = sum(1 for t in tasks_today if not t.is_completed)
    carried_over_tasks = sum(1 for t in tasks_today if t.is_carried_over)
    yesterdays_pending = sum(1 for t in tasks_yesterday if not t.is_completed)
    # Completion rate (today, week, overall)
    week_dates = [today - timedelta(days=i) for i in range(7)]
    week_tasks = Task.query.filter(Task.user_id == current_user.id,
                                   Task.date.in_(week_dates),
                                   Task.time_of_day == 'morning').all()
    week_completed = sum(1 for t in week_tasks if t.is_completed)
    week_total = len(week_tasks)
    week_completion_rate = (week_completed / week_total *
                            100) if week_total else 0
    # Consistency: % of days all tasks done
    days_with_tasks = {t.date for t in week_tasks}
    days_all_done = sum(
        all(t.is_completed for t in Task.query.filter_by(
            user_id=current_user.id, date=d, time_of_day='morning').all())
        for d in days_with_tasks)
    consistency_rate = (days_all_done / len(days_with_tasks) *
                        100) if days_with_tasks else 0
    # Streak: longest streak of all tasks done
    streak = 0
    max_streak = 0
    for i in range(14):
        d = today - timedelta(days=i)
        day_tasks = Task.query.filter_by(user_id=current_user.id,
                                         date=d,
                                         time_of_day='morning').all()
        if day_tasks and all(t.is_completed for t in day_tasks):
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    # Chart data for tasks (last 7 days)
    chart_dates = [today - timedelta(days=i) for i in reversed(range(7))]
    chart_data_tasks = {
        'dates': [d.strftime('%a %d') for d in chart_dates],
        'total': [],
        'completed': [],
        'pending': [],
        'carried_over': []
    }
    for d in chart_dates:
        day_tasks = Task.query.filter_by(user_id=current_user.id,
                                         date=d,
                                         time_of_day='morning').all()
        chart_data_tasks['total'].append(len(day_tasks))
        chart_data_tasks['completed'].append(
            sum(1 for t in day_tasks if t.is_completed))
        chart_data_tasks['pending'].append(
            sum(1 for t in day_tasks if not t.is_completed))
        chart_data_tasks['carried_over'].append(
            sum(1 for t in day_tasks if t.is_carried_over))

    # Advanced analytics
    # Rolling completion rates
    def get_completion_rate(days):
        dates = [today - timedelta(days=i) for i in range(days)]
        tasks = Task.query.filter(Task.user_id == current_user.id,
                                  Task.date.in_(dates),
                                  Task.time_of_day == 'morning').all()
        completed = sum(1 for t in tasks if t.is_completed)
        total = len(tasks)
        return (completed / total * 100) if total else 0

    rolling_7 = get_completion_rate(7)
    rolling_14 = get_completion_rate(14)
    rolling_30 = get_completion_rate(30)
    # Moving average (7-day)
    moving_avg = []
    for i in range(7):
        d = today - timedelta(days=i)
        tasks = Task.query.filter_by(user_id=current_user.id,
                                     date=d,
                                     time_of_day='morning').all()
        if tasks:
            moving_avg.append(
                sum(1 for t in tasks if t.is_completed) / len(tasks) * 100)
        else:
            moving_avg.append(None)
    moving_avg = moving_avg[::-1]
    # Streaks
    streak = 0
    max_streak = 0
    current_streak = 0
    for i in range(30):
        d = today - timedelta(days=i)
        day_tasks = Task.query.filter_by(user_id=current_user.id,
                                         date=d,
                                         time_of_day='morning').all()
        if day_tasks and all(t.is_completed for t in day_tasks):
            streak += 1
            max_streak = max(max_streak, streak)
            if i == 0:
                current_streak = streak
        else:
            streak = 0
    # Calendar heatmap (30 days)
    heatmap = []
    for i in range(30):
        d = today - timedelta(days=i)
        day_tasks = Task.query.filter_by(user_id=current_user.id,
                                         date=d,
                                         time_of_day='morning').all()
        if not day_tasks:
            heatmap.append('none')
        elif all(t.is_completed for t in day_tasks):
            heatmap.append('all')
        elif any(t.is_completed for t in day_tasks):
            heatmap.append('some')
        else:
            heatmap.append('none_done')
    heatmap = heatmap[::-1]
    # Carry-over insights
    carry_over_tasks = Task.query.filter_by(user_id=current_user.id,
                                            is_carried_over=True).all()
    carry_over_rate = (len(carry_over_tasks) /
                       Task.query.filter_by(user_id=current_user.id).count() *
                       100) if Task.query.filter_by(
                           user_id=current_user.id).count() else 0
    from collections import Counter
    top_carried = Counter([t.task_name
                           for t in carry_over_tasks]).most_common(5)
    # Days to completion for carried tasks
    # (for simplicity, not tracking original creation date, so skip for now)
    # Category breakdown
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    category_counts = Counter([t.category or 'General' for t in all_tasks])
    category_completion = {
        cat: (sum(1
                  for t in all_tasks if t.category == cat and t.is_completed) /
              count * 100) if count else 0
        for cat, count in category_counts.items()
    }
    # Personal bests
    best_day = None
    best_count = 0
    for i in range(30):
        d = today - timedelta(days=i)
        day_tasks = Task.query.filter_by(user_id=current_user.id,
                                         date=d,
                                         time_of_day='morning').all()
        if len(day_tasks) > best_count and all(t.is_completed
                                               for t in day_tasks):
            best_day = d
            best_count = len(day_tasks)
    # Milestones
    first_full = None
    for i in range(30):
        d = today - timedelta(days=i)
        day_tasks = Task.query.filter_by(user_id=current_user.id,
                                         date=d,
                                         time_of_day='morning').all()
        if day_tasks and all(t.is_completed for t in day_tasks):
            first_full = d
            break

    # AI-powered tips for sleep, energy, mood
    ai_tips = []
    if morning_checkin:
        if morning_checkin.sleep_quality and morning_checkin.sleep_quality <= 3:
            tip = get_ai_tip('sleep', morning_checkin.sleep_quality)
            if tip:
                ai_tips.append({'type': 'sleep', 'message': tip})
        if morning_checkin.energy_level and morning_checkin.energy_level <= 3:
            tip = get_ai_tip('energy', morning_checkin.energy_level)
            if tip:
                ai_tips.append({'type': 'energy', 'message': tip})
    if evening_checkin:
        if evening_checkin.mood_rating and evening_checkin.mood_rating <= 3:
            tip = get_ai_tip('mood', evening_checkin.mood_rating)
            if tip:
                ai_tips.append({'type': 'mood', 'message': tip})

    return render_template('dashboard.html',
                           checkins=checkins,
                           morning_checkins=morning_checkins,
                           evening_checkins=evening_checkins,
                           chart_data=chart_data,
                           morning_checkin=morning_checkin,
                           evening_checkin=evening_checkin,
                           insights=insights,
                           morning_insights=morning_insights,
                           evening_insights=evening_insights,
                           keyword_data=keyword_data,
                           habit_data=habit_data,
                           heatmap_dates=heatmap_dates,
                           motivational_quote=motivational_quote,
                           energy_focus_pairs=energy_focus_pairs,
                           total_tasks=total_tasks,
                           completed_tasks=completed_tasks,
                           pending_tasks=pending_tasks,
                           carried_over_tasks=carried_over_tasks,
                           yesterdays_pending=yesterdays_pending,
                           week_completion_rate=week_completion_rate,
                           consistency_rate=consistency_rate,
                           max_streak=max_streak,
                           chart_data_tasks=chart_data_tasks,
                           rolling_7=rolling_7,
                           rolling_14=rolling_14,
                           rolling_30=rolling_30,
                           moving_avg=moving_avg,
                           current_streak=current_streak,
                           heatmap=heatmap,
                           carry_over_rate=carry_over_rate,
                           top_carried=top_carried,
                           category_counts=category_counts,
                           category_completion=category_completion,
                           best_day=best_day,
                           best_count=best_count,
                           first_full=first_full,
                           ai_tips=ai_tips)


def prepare_chart_data(checkins, morning_checkins, evening_checkins):
    """Prepare data for various charts"""
    # Get unique dates for the last 7 days
    dates = sorted(list(set([c.date for c in checkins[:14]])),
                   reverse=True)[:7]

    chart_data = {
        'dates': [d.strftime('%m/%d') for d in dates],
        'morning_energy': [],
        'morning_sleep': [],
        'morning_sleep_quality': [],
        'evening_mood': [],
        'evening_win_rate': [],
        'overall_day_ratings': [],
        'habit_counts': {},
        'goal_accomplishment_rate': 0,
        'avg_sleep': 0,
        'avg_energy': 0
    }

    # Prepare data for each date
    for date_obj in dates:
        morning = next((c for c in morning_checkins if c.date == date_obj),
                       None)
        evening = next((c for c in evening_checkins if c.date == date_obj),
                       None)

        chart_data['morning_energy'].append(
            morning.energy_level
            if morning and morning.energy_level is not None else None)
        chart_data['morning_sleep'].append(
            morning.sleep_hours
            if morning and morning.sleep_hours is not None else None)
        chart_data['morning_sleep_quality'].append(
            morning.sleep_quality
            if morning and morning.sleep_quality is not None else None)
        chart_data['evening_mood'].append(
            evening.mood_rating
            if evening and evening.mood_rating is not None else None)
        chart_data['evening_win_rate'].append(
            1 if evening and evening.day_win else 0)
        chart_data['overall_day_ratings'].append(
            evening.overall_day_rating
            if evening and evening.overall_day_rating is not None else None)

    # Calculate averages
    sleep_values = [v for v in chart_data['morning_sleep'] if v is not None]
    energy_values = [v for v in chart_data['morning_energy'] if v is not None]

    if sleep_values:
        chart_data['avg_sleep'] = sum(sleep_values) / len(sleep_values)
    if energy_values:
        chart_data['avg_energy'] = sum(energy_values) / len(energy_values)

    # Calculate goal accomplishment rate
    evening_with_goals = [
        c for c in evening_checkins if c.goal_accomplished is not None
    ]
    if evening_with_goals:
        accomplished = sum(1 for c in evening_with_goals
                           if c.goal_accomplished)
        chart_data['goal_accomplishment_rate'] = (
            accomplished / len(evening_with_goals)) * 100

    return chart_data


def generate_morning_insights(morning_checkins):
    if not morning_checkins:
        return []
    insights = []
    # Sleep insights
    sleep_values = [
        c.sleep_hours for c in morning_checkins if c.sleep_hours is not None
    ]
    if sleep_values:
        avg_sleep = sum(sleep_values) / len(sleep_values)
        if avg_sleep < 7:
            insights.append({
                'type':
                'warning',
                'icon':
                'bed',
                'title':
                'Sleep Improvement Needed',
                'message':
                f'Your average sleep is {avg_sleep:.1f}h. Try to get 7-9 hours of sleep.'
            })
    # Sleep quality insights
    sleep_quality_values = [
        c.sleep_quality for c in morning_checkins
        if c.sleep_quality is not None
    ]
    if sleep_quality_values:
        avg_sleep_quality = sum(sleep_quality_values) / len(
            sleep_quality_values)
        if avg_sleep_quality < 3:
            insights.append({
                'type':
                'info',
                'icon':
                'moon',
                'title':
                'Sleep Quality Issues',
                'message':
                f'Your average sleep quality is {avg_sleep_quality:.1f}/5. Consider improving your sleep environment.'
            })
    # Energy insights
    low_energy_days = len([
        c for c in morning_checkins
        if c.energy_level is not None and c.energy_level <= 2
    ])
    if low_energy_days > len(morning_checkins) * 0.5:
        insights.append({
            'type':
            'warning',
            'icon':
            'battery-empty',
            'title':
            'Low Morning Energy',
            'message':
            f'{low_energy_days} out of {len(morning_checkins)} days had low energy. Consider morning routines.'
        })
    return insights


def generate_evening_insights(evening_checkins):
    if not evening_checkins:
        return []
    insights = []
    # Goal accomplishment insights
    with_goals = [
        c for c in evening_checkins if c.goal_accomplished is not None
    ]
    if with_goals:
        accomplished = sum(1 for c in with_goals if c.goal_accomplished)
        rate = (accomplished / len(with_goals)) * 100
        if rate < 50:
            insights.append({
                'type':
                'warning',
                'icon':
                'target',
                'title':
                'Goal Achievement Low',
                'message':
                f'You accomplished {rate:.0f}% of your daily goals. Try setting smaller, more achievable goals.'
            })
        elif rate > 80:
            insights.append({
                'type':
                'success',
                'icon':
                'trophy',
                'title':
                'Goal Achievement High',
                'message':
                f'Great job! You accomplished {rate:.0f}% of your daily goals.'
            })
    # Exercise insights
    exercise_days = len([c for c in evening_checkins if c.exercise_done])
    if exercise_days < len(evening_checkins) * 0.3:
        insights.append({
            'type':
            'info',
            'icon':
            'dumbbell',
            'title':
            'Exercise Frequency',
            'message':
            f'You exercised on {exercise_days} out of {len(evening_checkins)} days. Consider adding more movement.'
        })
    # Mood insights
    mood_rating_values = [
        c.mood_rating for c in evening_checkins if c.mood_rating is not None
    ]
    low_mood_days = len([v for v in mood_rating_values if v <= 2])
    if mood_rating_values and low_mood_days > len(mood_rating_values) * 0.4:
        insights.append({
            'type':
            'warning',
            'icon':
            'heart',
            'title':
            'Mood Patterns',
            'message':
            f'{low_mood_days} out of {len(mood_rating_values)} days had low mood ratings.'
        })
    return insights


def get_motivational_quote():
    """Get a motivational quote from an API"""
    try:
        response = requests.get(
            'https://api.quotable.io/random?tags=motivation', timeout=3)
        if response.status_code == 200:
            data = response.json()
            return {
                'text': data.get('content', 'Every day is a new beginning.'),
                'author': data.get('author', 'Unknown')
            }
    except:
        pass

    # Fallback quotes
    fallback_quotes = [{
        'text': 'Every day is a new beginning.',
        'author': 'Anonymous'
    }, {
        'text': 'The only way to do great work is to love what you do.',
        'author': 'Steve Jobs'
    }, {
        'text':
        'Success is not final, failure is not fatal: it is the courage to continue that counts.',
        'author': 'Winston Churchill'
    }]
    import random
    return random.choice(fallback_quotes)


@app.route('/analytics')
@login_required
def analytics():
    # Get all check-ins for comprehensive analysis
    all_checkins = CheckIn.query.filter_by(user_id=current_user.id).order_by(
        CheckIn.date.desc()).all()
    if not all_checkins:
        return render_template('analytics.html', checkins=[], insights={})
    # Calculate comprehensive insights
    total_checkins = len(all_checkins)
    sleep_values = [
        c.sleep_hours for c in all_checkins if c.sleep_hours is not None
    ]
    energy_values = [
        c.energy_level for c in all_checkins if c.energy_level is not None
    ]
    focus_values = [
        c.focus_level for c in all_checkins if c.focus_level is not None
    ]
    avg_sleep = sum(sleep_values) / len(sleep_values) if sleep_values else 0
    avg_energy = sum(energy_values) / len(
        energy_values) if energy_values else 0
    avg_focus = sum(focus_values) / len(focus_values) if focus_values else 0
    # Mood analysis
    mood_counts = {}
    for checkin in all_checkins:
        if checkin.mood:
            mood_counts[checkin.mood] = mood_counts.get(checkin.mood, 0) + 1
    most_common_mood = max(mood_counts.items(),
                           key=lambda x: x[1]) if mood_counts else ('None', 0)
    # Sleep quality analysis
    sleep_quality = {
        'excellent':
        len([
            c for c in all_checkins
            if c.sleep_hours is not None and 7 <= c.sleep_hours <= 9
        ]),
        'good':
        len([
            c for c in all_checkins
            if c.sleep_hours is not None and 6 <= c.sleep_hours < 7
        ]),
        'poor':
        len([
            c for c in all_checkins if c.sleep_hours is not None and (
                c.sleep_hours < 6 or c.sleep_hours > 9)
        ])
    }
    # Productivity analysis
    high_productivity_days = len([
        c for c in all_checkins
        if c.energy_level is not None and c.focus_level is not None
        and c.energy_level >= 4 and c.focus_level >= 4
    ])
    productivity_percentage = (high_productivity_days /
                               total_checkins) * 100 if total_checkins else 0
    # Weekly patterns
    weekly_data = {}
    for checkin in all_checkins:
        day_name = checkin.date.strftime('%A')
        if day_name not in weekly_data:
            weekly_data[day_name] = {'energy': [], 'focus': [], 'sleep': []}
        if checkin.energy_level is not None:
            weekly_data[day_name]['energy'].append(checkin.energy_level)
        if checkin.focus_level is not None:
            weekly_data[day_name]['focus'].append(checkin.focus_level)
        if checkin.sleep_hours is not None:
            weekly_data[day_name]['sleep'].append(checkin.sleep_hours)
    # Calculate averages for each day
    for day in weekly_data:
        energies = weekly_data[day]['energy']
        focuses = weekly_data[day]['focus']
        sleeps = weekly_data[day]['sleep']
        weekly_data[day]['avg_energy'] = sum(energies) / len(
            energies) if energies else 0
        weekly_data[day]['avg_focus'] = sum(focuses) / len(
            focuses) if focuses else 0
        weekly_data[day]['avg_sleep'] = sum(sleeps) / len(
            sleeps) if sleeps else 0
    insights = {
        'total_checkins': total_checkins,
        'avg_sleep': avg_sleep,
        'avg_energy': avg_energy,
        'avg_focus': avg_focus,
        'most_common_mood': most_common_mood,
        'sleep_quality': sleep_quality,
        'productivity_percentage': productivity_percentage,
        'weekly_data': weekly_data
    }
    return render_template('analytics.html',
                           checkins=all_checkins,
                           insights=insights)


@app.route('/edit/<date_str>/<time_of_day>', methods=['GET', 'POST'])
@login_required
def edit_checkin(date_str, time_of_day):
    """Edit a specific check-in by date and time of day"""
    try:
        checkin_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(url_for('checkin.dashboard'))

    if time_of_day not in ['morning', 'evening']:
        flash('Invalid time of day', 'danger')
        return redirect(url_for('checkin.dashboard'))

    checkin = CheckIn.query.filter_by(user_id=current_user.id,
                                      date=checkin_date,
                                      time_of_day=time_of_day).first()

    if not checkin:
        flash(f'No {time_of_day} check-in found for {date_str}', 'danger')
        return redirect(url_for('checkin.dashboard'))

    if request.method == 'POST':
        # Update check-in fields
        update_checkin_fields(checkin, request.form, time_of_day)

        # Update habits
        habits = request.form.getlist('habits')
        habits_json = json.dumps(habits) if habits else None
        checkin.habits = habits_json

        db.session.commit()
        flash(f'{time_of_day.title()} check-in updated successfully!',
              'success')
        return redirect(url_for('checkin.dashboard'))

    return render_template('edit_checkin.html',
                           checkin=checkin,
                           date_str=date_str)


@app.route('/export/<format>')
@login_required
def export_data(format):
    checkins = CheckIn.query.filter_by(user_id=current_user.id).order_by(
        CheckIn.date.desc(), CheckIn.time_of_day.desc()).all()

    if format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Date', 'Time of Day', 'Sleep Hours', 'Sleep Quality',
            'Energy Level', 'Morning Goal', 'Anxiety Level',
            'Goal Accomplished', 'Mood Rating', 'Exercise Done',
            'What Drained You', 'Gratitude', 'Day Win', 'Overall Day Rating',
            'Habits', 'Legacy Mood', 'Legacy Focus Level', 'Legacy Tasks Done',
            'Legacy Diet', 'Legacy Exercise'
        ])

        for checkin in checkins:
            habits = json.loads(checkin.habits) if checkin.habits else []
            writer.writerow([
                checkin.date.strftime('%Y-%m-%d'), checkin.time_of_day,
                checkin.sleep_hours or '', checkin.sleep_quality or '',
                checkin.energy_level or '', checkin.morning_goal or '',
                checkin.anxiety_level or '', 'Yes' if checkin.goal_accomplished
                else 'No' if checkin.goal_accomplished is not None else '',
                checkin.mood_rating or '', 'Yes' if checkin.exercise_done else
                'No' if checkin.exercise_done is not None else '',
                checkin.what_drained_you or '', checkin.gratitude or '',
                'Yes' if checkin.day_win else
                'No' if checkin.day_win is not None else '',
                checkin.overall_day_rating or '', ', '.join(habits),
                checkin.mood or '', checkin.focus_level or '',
                checkin.tasks_done or '', checkin.diet or '', checkin.exercise
                or ''
            ])

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=
            f'checkin_data_{current_user.username}_{date.today()}.csv')

    elif format == 'json':
        data = []
        for checkin in checkins:
            habits = json.loads(checkin.habits) if checkin.habits else []
            data.append({
                'date': checkin.date.strftime('%Y-%m-%d'),
                'time_of_day': checkin.time_of_day,
                'sleep_hours': checkin.sleep_hours,
                'sleep_quality': checkin.sleep_quality,
                'energy_level': checkin.energy_level,
                'morning_goal': checkin.morning_goal,
                'anxiety_level': checkin.anxiety_level,
                'goal_accomplished': checkin.goal_accomplished,
                'mood_rating': checkin.mood_rating,
                'exercise_done': checkin.exercise_done,
                'what_drained_you': checkin.what_drained_you,
                'gratitude': checkin.gratitude,
                'day_win': checkin.day_win,
                'overall_day_rating': checkin.overall_day_rating,
                'habits': habits,
                # Legacy fields
                'legacy_mood': checkin.mood,
                'legacy_focus_level': checkin.focus_level,
                'legacy_tasks_done': checkin.tasks_done,
                'legacy_diet': checkin.diet,
                'legacy_exercise': checkin.exercise
            })

        return send_file(
            io.BytesIO(json.dumps(data, indent=2).encode('utf-8')),
            mimetype='application/json',
            as_attachment=True,
            download_name=
            f'checkin_data_{current_user.username}_{date.today()}.json')

    return redirect(url_for('checkin.dashboard'))


# Custom Jinja filters
@app.template_filter('from_json')
def from_json(value):
    if value:
        try:
            return json.loads(value)
        except:
            return []
    return []


# Helper functions
def generate_insights(checkins):
    if not checkins:
        return []
    insights = []
    # Sleep insights
    sleep_values = [
        c.sleep_hours for c in checkins if c.sleep_hours is not None
    ]
    if sleep_values:
        avg_sleep = sum(sleep_values) / len(sleep_values)
    else:
        avg_sleep = 0
    if avg_sleep < 7:
        insights.append({
            'type':
            'warning',
            'icon':
            'bed',
            'title':
            'Sleep Improvement Needed',
            'message':
            f'Your average sleep is {avg_sleep:.1f}h. Try to get 7-9 hours of sleep.'
        })
    # Energy-Focus correlation
    low_energy_days = len([
        c for c in checkins
        if c.energy_level is not None and c.energy_level <= 2
    ])
    if low_energy_days > len(
        [c for c in checkins if c.energy_level is not None]) * 0.5:
        insights.append({
            'type':
            'info',
            'icon':
            'battery-empty',
            'title':
            'Low Energy Pattern',
            'message':
            'You\'ve had many low-energy days. Consider improving your sleep and exercise routine.'
        })
    # Focus insights
    low_focus_days = len([
        c for c in checkins if c.focus_level is not None and c.focus_level <= 2
    ])
    if low_focus_days > len([c for c in checkins if c.focus_level is not None
                             ]) * 0.5:
        insights.append({
            'type':
            'warning',
            'icon':
            'bullseye',
            'title':
            'Focus Issues',
            'message':
            'Your focus levels have been low. Try reducing distractions and taking regular breaks.'
        })
    return insights


def analyze_keywords(checkins):
    if not checkins:
        return []

    # Combine all tasks text
    all_tasks = ' '.join([c.tasks_done for c in checkins if c.tasks_done])

    if not all_tasks:
        return []

    # Tokenize and clean
    tokens = word_tokenize(all_tasks.lower())
    stop_words = set(stopwords.words('english'))

    # Filter out stop words and short words
    keywords = [
        word for word in tokens
        if word.isalnum() and len(word) > 2 and word not in stop_words
    ]

    # Count frequencies
    keyword_counts = Counter(keywords)

    return keyword_counts.most_common(10)


def analyze_habits(checkins):
    if not checkins:
        return []

    all_habits = []
    for checkin in checkins:
        if checkin.habits:
            habits = json.loads(checkin.habits)
            all_habits.extend(habits)

    habit_counts = Counter(all_habits)
    return habit_counts.most_common(10)


# Schedule daily reminders
def schedule_reminders():
    # Morning reminder at 9 AM
    scheduler.add_job(func=send_morning_reminder,
                      trigger=CronTrigger(hour=9, minute=0),
                      id='morning_reminder',
                      name='Send morning check-in reminder',
                      replace_existing=True)

    # Evening reminder at 9 PM
    scheduler.add_job(func=send_evening_reminder,
                      trigger=CronTrigger(hour=21, minute=0),
                      id='evening_reminder',
                      name='Send evening check-in reminder',
                      replace_existing=True)


def send_morning_reminder():
    """Send morning check-in reminders to all users"""
    users = User.query.all()
    for user in users:
        # Check if user already has a morning check-in for today
        today = date.today()
        existing_checkin = CheckIn.query.filter_by(
            user_id=user.id, date=today, time_of_day='morning').first()

        if not existing_checkin:
            # In a real app, you'd send an email or push notification here
            print(
                f"Morning reminder sent to {user.username} at {datetime.now()}"
            )
            # For now, we'll just log it
            # You could integrate with email services like SendGrid or push notifications


def send_evening_reminder():
    """Send evening check-in reminders to all users"""
    users = User.query.all()
    for user in users:
        # Check if user already has an evening check-in for today
        today = date.today()
        existing_checkin = CheckIn.query.filter_by(
            user_id=user.id, date=today, time_of_day='evening').first()

        if not existing_checkin:
            # In a real app, you'd send an email or push notification here
            print(
                f"Evening reminder sent to {user.username} at {datetime.now()}"
            )
            # For now, we'll just log it


# Initialize reminders when app starts
schedule_reminders()


@app.route('/reminder/<time_of_day>')
@login_required
def reminder_link(time_of_day):
    """Handle reminder links for quick check-in access"""
    if time_of_day not in ['morning', 'evening']:
        flash('Invalid reminder link', 'danger')
        return redirect(url_for('checkin.dashboard'))

    # Redirect to submit page with pre-selected time of day
    flash(f'Time for your {time_of_day} check-in!', 'info')
    return redirect(url_for('checkin.submit') + f'?time={time_of_day}')


@app.route('/ai/suggest_tasks', methods=['POST'])
@login_required
def ai_suggest_tasks():
    data = request.json or {}
    habits = data.get('habits', [])
    goal = data.get('goal', '')
    previous_tasks = data.get('previous_tasks', [])
    api_key = app.config.get('GENAI_API_KEY')

    # Prepare prompt for Gemini
    prompt = (
        "Suggest 3-5 new, actionable tasks for tomorrow based on these habits: "
        f"{habits}, goal: '{goal}', and these existing tasks: {previous_tasks}. "
        "For each, provide a task name, priority (Low/Medium/High), category, and a short note. "
        "Return the result as a JSON array of objects with keys: task_name, priority, task_category, task_notes."
    )

    # Gemini API call
    def call_gemini_api(url, headers, payload):
        try:
            response = requests.post(url,
                                     headers=headers,
                                     json=payload,
                                     timeout=15)
            response.raise_for_status()
            gemini_data = response.json()
            candidates = gemini_data.get('candidates', [])
            if not candidates:
                return None, 'No suggestions from AI.'
            text = candidates[0]['content']['parts'][0]['text']
            import json as pyjson
            try:
                suggested_tasks = pyjson.loads(text)
            except Exception:
                import re
                match = re.search(r'\[.*\]', text, re.DOTALL)
                if match:
                    suggested_tasks = pyjson.loads(match.group(0))
                else:
                    return None, 'AI response could not be parsed.'
            for task in suggested_tasks:
                task.setdefault('task_name', '')
                task.setdefault('priority', 'Medium')
                task.setdefault('task_category', 'Work')
                task.setdefault('task_notes', '')
            return suggested_tasks, None
        except Exception as e:
            return None, str(e)

    # Use only the v1beta endpoint and gemini-1.5-flash model for AI Studio keys
    url_v1beta = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    suggested_tasks, error = call_gemini_api(url_v1beta, headers, payload)
    if suggested_tasks:
        return jsonify({"suggested_tasks": suggested_tasks}), 200
    else:
        return jsonify({"error": f"AI suggestion failed: {error}"}), 200


# Register blueprint
app.register_blueprint(checkin_bp)


# Add this helper function for AI tips
def get_ai_tip(context_type, value):
    """Get an AI-powered tip for sleep, energy, or mood based on the value."""
    api_key = app.config.get('GENAI_API_KEY')
    # Example prompt
    prompt = f"Give a practical tip to improve {context_type} for someone who rated it as {value}/5."
    # Placeholder for actual GenAI call
    # response = requests.post('https://genai.googleapis.com/v1beta/models/gemini-pro:generateContent', ...)
    # For now, return a static tip
    if context_type == 'sleep' and value <= 3:
        return "Try to maintain a consistent sleep schedule and avoid screens before bed."
    if context_type == 'energy' and value <= 3:
        return "Consider a short walk or stretching in the morning to boost your energy."
    if context_type == 'mood' and value <= 3:
        return "Take a few minutes for deep breathing or gratitude journaling to lift your mood."
    return None


# Helper to get all check-ins for the current user
def get_all_checkins():
    return CheckIn.query.filter_by(user_id=current_user.id).order_by(
        CheckIn.date.asc()).all()


def get_all_tasks():
    return Task.query.filter_by(user_id=current_user.id).order_by(
        Task.date.asc()).all()


def call_gemini(prompt, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url,
                                 headers=headers,
                                 json=payload,
                                 timeout=20)
        response.raise_for_status()
        data = response.json()
        text = data['candidates'][0]['content']['parts'][0]['text']
        return text
    except Exception as e:
        return f"AI error: {e}"


@app.route('/ai/personalized_tip', methods=['GET'])
@login_required
def ai_personalized_tip():
    api_key = app.config.get('GENAI_API_KEY')
    checkins = get_all_checkins()
    prompt = f"Based on this user's check-in history: {checkins}, give one actionable, personalized tip for today."
    tip = call_gemini(prompt, api_key)
    return jsonify({'tip': tip})


@app.route('/ai/habit_suggestion', methods=['GET'])
@login_required
def ai_habit_suggestion():
    api_key = app.config.get('GENAI_API_KEY')
    checkins = get_all_checkins()
    prompt = f"Based on this user's check-in and habit history: {checkins}, suggest 2-3 new habits to try."
    habits = call_gemini(prompt, api_key)
    return jsonify({'habits': habits})


@app.route('/ai/goal_suggestion', methods=['GET'])
@login_required
def ai_goal_suggestion():
    api_key = app.config.get('GENAI_API_KEY')
    checkins = get_all_checkins()
    tasks = get_all_tasks()
    prompt = f"Based on this user's check-ins and unfinished tasks: {checkins}, {tasks}, suggest a realistic, motivating goal for today."
    goal = call_gemini(prompt, api_key)
    return jsonify({'goal': goal})


@app.route('/ai/analytics_summary', methods=['GET'])
@login_required
def ai_analytics_summary():
    api_key = app.config.get('GENAI_API_KEY')
    checkins = get_all_checkins()
    tasks = get_all_tasks()
    prompt = f"Analyze this user's check-ins and tasks: {checkins}, {tasks}. Summarize any patterns in mood, energy, sleep, and task completion."
    summary = call_gemini(prompt, api_key)
    return jsonify({'summary': summary})


@app.route('/ai/reflection_prompt', methods=['GET'])
@login_required
def ai_reflection_prompt():
    api_key = app.config.get('GENAI_API_KEY')
    checkins = get_all_checkins()
    if not checkins:
        return jsonify({'prompt': ''})
    last = checkins[-1]
    if hasattr(last,
               'mood_rating') and last.mood_rating and last.mood_rating <= 2:
        prompt = f"The user rated their day as challenging. Suggest a gentle reflection prompt or encouragement."
        reflection = call_gemini(prompt, api_key)
        return jsonify({'prompt': reflection})
    return jsonify({'prompt': ''})


@app.route('/ai/weekly_report', methods=['GET'])
@login_required
def ai_weekly_report():
    api_key = app.config.get('GENAI_API_KEY')
    checkins = get_all_checkins()
    tasks = get_all_tasks()
    prompt = f"Summarize this user's progress over all available check-ins and tasks, highlight their biggest wins, and suggest one area to focus on next."
    report = call_gemini(prompt, api_key)
    return jsonify({'report': report})


@app.route('/ai/analytics_query', methods=['POST'])
@login_required
def ai_analytics_query():
    api_key = app.config.get('GENAI_API_KEY')
    checkins = get_all_checkins()
    tasks = get_all_tasks()
    user_query = request.json.get('query', '')
    prompt = f"User asked: '{user_query}'. Here is their check-in and task history: {checkins}, {tasks}. Answer the question concisely."
    answer = call_gemini(prompt, api_key)
    return jsonify({'answer': answer})


@app.route('/ai/motivation', methods=['GET'])
@login_required
def ai_motivation():
    api_key = app.config.get('GENAI_API_KEY')
    checkins = get_all_checkins()
    prompt = f"Based on this user's recent check-ins, generate a motivational quote or affirmation tailored to their current mood and goals."
    quote = call_gemini(prompt, api_key)
    return jsonify({'quote': quote})


@app.route('/ai/task_advice', methods=['GET'])
@login_required
def ai_task_advice():
    api_key = app.config.get('GENAI_API_KEY')
    tasks = get_all_tasks()
    prompt = f"Here are the user's current tasks: {tasks}. Suggest which tasks to prioritize and how to break down big goals into smaller steps."
    advice = call_gemini(prompt, api_key)
    return jsonify({'advice': advice})


@app.route('/ai/reminder_time', methods=['GET'])
@login_required
def ai_reminder_time():
    api_key = app.config.get('GENAI_API_KEY')
    checkins = get_all_checkins()
    prompt = f"Based on this user's check-in and habit patterns, suggest the best time of day for reminders."
    reminder = call_gemini(prompt, api_key)
    return jsonify({'reminder_time': reminder})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
