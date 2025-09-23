from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from flask_mail import Mail, Message
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, FloatField, TextAreaField, EmailField
from wtforms.validators import DataRequired, Length, EqualTo, Email
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gzclp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

# Custom Jinja filters
@app.template_filter('from_json')
def from_json_filter(json_string):
    try:
        return json.loads(json_string)
    except:
        return []

# Helper functions
def calculate_current_weight(start_weight, increment, week_number):
    """Calculate current weight based on start weight, increment, and week number"""
    return start_weight + (increment * (week_number - 1))

def get_current_week():
    """Get current week number (1-based) - in real app, this would be calculated from program start date"""
    return 1  # For now, always week 1

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    units = db.Column(db.String(10), nullable=False, default='metric')  # metric or imperial
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    created_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    programs = db.relationship('Program', backref='user', lazy=True)
    workout_logs = db.relationship('WorkoutLog', backref='user_workout_logs', lazy=True)

class Program(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    days_per_week = db.Column(db.Integer, nullable=False)  # 2-4
    length_weeks = db.Column(db.Integer, nullable=False)  # 8-16
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    created_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    program_days = db.relationship('ProgramDay', backref='program', lazy=True)

class ProgramDay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    day_number = db.Column(db.Integer, nullable=False)  # 1, 2, 3, or 4
    t1_exercise = db.Column(db.String(100), nullable=False)
    t1_start_weight = db.Column(db.Float, nullable=False)
    t1_increment = db.Column(db.Float, nullable=False)
    t2_exercise = db.Column(db.String(100), nullable=False)
    t2_start_weight = db.Column(db.Float, nullable=False)
    t2_increment = db.Column(db.Float, nullable=False)
    t3_exercises = db.Column(db.Text, nullable=False)  # JSON: [{"name": "Curls", "start_weight": 20, "increment": 2.5}]

class WorkoutLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    program_day_id = db.Column(db.Integer, db.ForeignKey('program_day.id'), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)
    sets_completed = db.Column(db.Text, nullable=False)  # JSON string of sets data
    
    # Relationships
    program = db.relationship('Program', backref='program_workout_logs')
    program_day = db.relationship('ProgramDay', backref='program_day_workout_logs')

class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    
    user = db.relationship('User', backref='password_reset_tokens')

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    units = SelectField('Units', choices=[('metric', 'Metric (kg)'), ('imperial', 'Imperial (lbs)')], default='metric')
    submit = SubmitField('Register')

class ForgotPasswordForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

class ProgramForm(FlaskForm):
    name = StringField('Program Name', validators=[DataRequired(), Length(min=1, max=100)])
    days_per_week = SelectField('Days Per Week', choices=[('2', '2 days'), ('3', '3 days'), ('4', '4 days')], validators=[DataRequired()])
    length_weeks = SelectField('Program Length', choices=[('8', '8 weeks'), ('10', '10 weeks'), ('12', '12 weeks'), ('16', '16 weeks')], validators=[DataRequired()])
    submit = SubmitField('Create Program')

class ProgramDayForm(FlaskForm):
    day_number = IntegerField('Day Number', validators=[DataRequired()])
    
    # T1 Exercise choices (main compounds)
    t1_choices = [
        ('Squat (Barbell)', 'Squat (Barbell)'),
        ('Deadlift (Barbell)', 'Deadlift (Barbell)'),
        ('Bench Press (Barbell)', 'Bench Press (Barbell)'),
        ('Overhead Press (Barbell)', 'Overhead Press (Barbell)')
    ]
    t1_exercise = SelectField('T1 Exercise', choices=t1_choices, validators=[DataRequired()])
    t1_start_weight = FloatField('T1 Start Weight', validators=[DataRequired()])
    t1_increment = SelectField('T1 Increment', choices=[(2.5, '2.5'), (5.0, '5.0')], validators=[DataRequired()])
    
    # T2 Exercise choices (T1 + secondary variations)
    t2_choices = [
        ('Squat (Barbell)', 'Squat (Barbell)'),
        ('Deadlift (Barbell)', 'Deadlift (Barbell)'),
        ('Bench Press (Barbell)', 'Bench Press (Barbell)'),
        ('Overhead Press (Barbell)', 'Overhead Press (Barbell)'),
        ('Chest Press (Machine)', 'Chest Press (Machine)'),
        ('Flat Bench Press (Barbell)', 'Flat Bench Press (Barbell)'),
        ('Flat Bench Press (Dumbbell)', 'Flat Bench Press (Dumbbell)'),
        ('Flat Bench Press (Smith Machine)', 'Flat Bench Press (Smith Machine)'),
        ('Incline Bench Press (Barbell)', 'Incline Bench Press (Barbell)'),
        ('Incline Bench Press (Dumbbell)', 'Incline Bench Press (Dumbbell)'),
        ('Incline Bench Press (Smith Machine)', 'Incline Bench Press (Smith Machine)'),
        ('Incline Chest Press (Machine)', 'Incline Chest Press (Machine)'),
        ('Conventional Deadlift (Barbell)', 'Conventional Deadlift (Barbell)'),
        ('Sumo Deadlift (Barbell)', 'Sumo Deadlift (Barbell)'),
        ('Romanian Deadlift (Barbell)', 'Romanian Deadlift (Barbell)'),
        ('Romanian Deadlift (Dumbbell)', 'Romanian Deadlift (Dumbbell)'),
        ('Good Morning (Barbell)', 'Good Morning (Barbell)'),
        ('Hip Thrusts (Barbell)', 'Hip Thrusts (Barbell)'),
        ('Single Leg Deadlift', 'Single Leg Deadlift'),
        ('Squat (Smith Machine)', 'Squat (Smith Machine)'),
        ('Front Squat (Barbell)', 'Front Squat (Barbell)'),
        ('Hack Squat (Machine)', 'Hack Squat (Machine)'),
        ('Leg Press (Machine)', 'Leg Press (Machine)'),
        ('Leg Extension (Machine)', 'Leg Extension (Machine)'),
        ('Bulgarian Split Squat', 'Bulgarian Split Squat'),
        ('Goblet Squat', 'Goblet Squat'),
        ('Split Squats', 'Split Squats'),
        ('Weighted Lunges', 'Weighted Lunges'),
        ('Weighted Step Ups', 'Weighted Step Ups'),
        ('Shoulder Press (Barbell)', 'Shoulder Press (Barbell)'),
        ('Shoulder Press (Dumbbell)', 'Shoulder Press (Dumbbell)'),
        ('Shoulder Press (Machine)', 'Shoulder Press (Machine)')
    ]
    t2_exercise = SelectField('T2 Exercise', choices=t2_choices, validators=[DataRequired()])
    t2_start_weight = FloatField('T2 Start Weight', validators=[DataRequired()])
    t2_increment = SelectField('T2 Increment', choices=[(2.5, '2.5'), (5.0, '5.0')], validators=[DataRequired()])
    
    # T3 Exercise choices (T1 + T2 + assistance work)
    t3_choices = t2_choices + [
        ('Ab Machine', 'Ab Machine'),
        ('Cable Crunch', 'Cable Crunch'),
        ('Cable Twists (Down Up)', 'Cable Twists (Down Up)'),
        ('Cable Twists (Up Down)', 'Cable Twists (Up Down)'),
        ('Hanging Knee Raise', 'Hanging Knee Raise'),
        ('Lying Leg Raise', 'Lying Leg Raise'),
        ('Weighted Crunches', 'Weighted Crunches'),
        ('Bicep Curl (Barbell)', 'Bicep Curl (Barbell)'),
        ('Bicep Curl (Cables)', 'Bicep Curl (Cables)'),
        ('Bicep Curl (Dumbbell)', 'Bicep Curl (Dumbbell)'),
        ('Bicep Curl (Machine)', 'Bicep Curl (Machine)'),
        ('Concentration Curl (Dumbbell)', 'Concentration Curl (Dumbbell)'),
        ('Hammer Curl (Dumbbell)', 'Hammer Curl (Dumbbell)'),
        ('Preacher Curl (Barbell)', 'Preacher Curl (Barbell)'),
        ('Preacher Curl (Dumbbell)', 'Preacher Curl (Dumbbell)'),
        ('Rope Curl (Cables)', 'Rope Curl (Cables)'),
        ('Calf Raise on Leg Press Machine', 'Calf Raise on Leg Press Machine'),
        ('Standing Calf Raise', 'Standing Calf Raise'),
        ('Chest Flyes (Cables)', 'Chest Flyes (Cables)'),
        ('Chest Flyes (Dumbbell)', 'Chest Flyes (Dumbbell)'),
        ('Upper Chest Fly (Cables)', 'Upper Chest Fly (Cables)'),
        ('Dips', 'Dips'),
        ('Lateral Raises (Cables)', 'Lateral Raises (Cables)'),
        ('Lateral Raises (Dumbbell)', 'Lateral Raises (Dumbbell)'),
        ('Rear Delt Fly (Cables)', 'Rear Delt Fly (Cables)'),
        ('Rear Delt Fly (Dumbbell)', 'Rear Delt Fly (Dumbbell)'),
        ('Rear Delt Fly (Machine)', 'Rear Delt Fly (Machine)'),
        ('Upright Row (Barbell)', 'Upright Row (Barbell)'),
        ('Upright Row (Cables)', 'Upright Row (Cables)'),
        ('Upright Row (Dumbbell)', 'Upright Row (Dumbbell)'),
        ('Rope Pull Through (Cables)', 'Rope Pull Through (Cables)'),
        ('Standing Leg Curl (Cables)', 'Standing Leg Curl (Cables)'),
        ('Single Leg Hip Thrust (Dumbbell)', 'Single Leg Hip Thrust (Dumbbell)'),
        ('Weighted Hyperextensions', 'Weighted Hyperextensions'),
        ('Leg Curl (Machine)', 'Leg Curl (Machine)'),
        ('Lying Leg Curl (Cables)', 'Lying Leg Curl (Cables)'),
        ('Bent Over Row (Barbell)', 'Bent Over Row (Barbell)'),
        ('Bent Over Row (Dumbbell)', 'Bent Over Row (Dumbbell)'),
        ('Bent Over Row (Smith Machine)', 'Bent Over Row (Smith Machine)'),
        ('Seated Row (Cables)', 'Seated Row (Cables)'),
        ('Seated Row (Machine)', 'Seated Row (Machine)'),
        ('Shrugs', 'Shrugs'),
        ('Lying Tricep Extensions (Barbell)', 'Lying Tricep Extensions (Barbell)'),
        ('Lying Tricep Extensions (Dumbbell)', 'Lying Tricep Extensions (Dumbbell)'),
        ('Tricep Extension (Machine)', 'Tricep Extension (Machine)'),
        ('Tricep Pushdowns (Cables)', 'Tricep Pushdowns (Cables)'),
        ('Tricep Pushdowns (Rope)', 'Tricep Pushdowns (Rope)'),
        ('Assisted Chinup (Machine)', 'Assisted Chinup (Machine)'),
        ('Assisted Neutral Grip Pullup', 'Assisted Neutral Grip Pullup'),
        ('Assisted Pullup (Machine)', 'Assisted Pullup (Machine)'),
        ('Assisted Pullup (Band)', 'Assisted Pullup (Band)'),
        ('Chinup', 'Chinup'),
        ('Strict Pullup', 'Strict Pullup'),
        ('Lat Pulldown', 'Lat Pulldown'),
        ('Neutral Grip Pulldown', 'Neutral Grip Pulldown'),
        ('Neutral Grip Pullup', 'Neutral Grip Pullup'),
        ('Pullup', 'Pullup'),
        ('Underhand Pulldown', 'Underhand Pulldown'),
        ('Push-ups', 'Push-ups'),
        ('Diamond Push-ups', 'Diamond Push-ups'),
        ('Clapping Push-ups', 'Clapping Push-ups'),
        ('Planks', 'Planks'),
        ('GHD Back Extensions', 'GHD Back Extensions'),
        ('Side Planks', 'Side Planks')
    ]
    
    # T3 Exercise 1
    t3_exercise_1 = SelectField('T3 Exercise 1', choices=[('', 'None')] + t3_choices)
    t3_start_weight_1 = FloatField('T3 Start Weight 1')
    t3_increment_1 = SelectField('T3 Increment 1', choices=[('', 'Select increment...'), (2.5, '2.5'), (5.0, '5.0')])
    
    # T3 Exercise 2
    t3_exercise_2 = SelectField('T3 Exercise 2', choices=[('', 'None')] + t3_choices)
    t3_start_weight_2 = FloatField('T3 Start Weight 2')
    t3_increment_2 = SelectField('T3 Increment 2', choices=[('', 'Select increment...'), (2.5, '2.5'), (5.0, '5.0')])
    
    # T3 Exercise 3
    t3_exercise_3 = SelectField('T3 Exercise 3', choices=[('', 'None')] + t3_choices)
    t3_start_weight_3 = FloatField('T3 Start Weight 3')
    t3_increment_3 = SelectField('T3 Increment 3', choices=[('', 'Select increment...'), (2.5, '2.5'), (5.0, '5.0')])
    
    submit = SubmitField('Save Day')

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    # Get active program and its days
    active_program = Program.query.filter_by(user_id=user.id, is_active=True).first()
    program_days = []
    if active_program:
        program_days = ProgramDay.query.filter_by(program_id=active_program.id).all()
    
    # Calculate completed workouts this week
    from datetime import datetime, timedelta
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())  # Monday of this week
    week_end = week_start + timedelta(days=6)  # Sunday of this week
    
    completed_workouts_this_week = WorkoutLog.query.filter(
        WorkoutLog.user_id == user.id,
        WorkoutLog.date >= week_start,
        WorkoutLog.date <= week_end
    ).count()
    
    # Get recent workouts (last 5)
    recent_workouts = WorkoutLog.query.filter_by(user_id=user.id).join(ProgramDay).order_by(WorkoutLog.date.desc()).limit(5).all()
    
    return render_template('dashboard.html', user=user, program_days=program_days, completed_workouts_this_week=completed_workouts_this_week, recent_workouts=recent_workouts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'error')
            return render_template('register.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'error')
            return render_template('register.html', form=form)
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            units=form.units.data
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Generate reset token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=1)
            
            # Invalidate any existing tokens for this user
            PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({'used': True})
            
            # Create new token
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=expires_at
            )
            db.session.add(reset_token)
            db.session.commit()
            
            # Send email
            try:
                msg = Message(
                    'Password Reset Request - GZCLP Tracker',
                    recipients=[user.email],
                    html=render_template('email/reset_password.html', 
                                       username=user.username, 
                                       reset_url=url_for('reset_password', token=token, _external=True))
                )
                mail.send(msg)
                flash('Password reset link sent to your email', 'success')
            except Exception as e:
                print(f"Email sending failed: {e}")
                flash('Failed to send email. Please try again later.', 'error')
        else:
            flash('No account found with that email address', 'error')
    return render_template('forgot_password.html', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    form = ResetPasswordForm()
    
    # Validate token
    reset_token = PasswordResetToken.query.filter_by(token=token, used=False).first()
    if not reset_token or reset_token.expires_at < datetime.utcnow():
        flash('Invalid or expired reset token', 'error')
        return redirect(url_for('forgot_password'))
    
    if form.validate_on_submit():
        # Update password
        user = reset_token.user
        user.password_hash = generate_password_hash(form.password.data)
        
        # Mark token as used
        reset_token.used = True
        
        db.session.commit()
        flash('Password updated successfully! Please login with your new password.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', form=form, token=token)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        # User doesn't exist, clear session and redirect to login
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    programs = Program.query.filter_by(user_id=user.id).all()
    form = ProgramForm()
    
    return render_template('settings.html', programs=programs, user=user, form=form)

@app.route('/create_program', methods=['POST'])
def create_program():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    form = ProgramForm()
    if form.validate_on_submit():
        try:
            # Deactivate all other programs
            Program.query.filter_by(user_id=session['user_id']).update({'is_active': False})
            
            program = Program(
                name=form.name.data,
                days_per_week=int(form.days_per_week.data),
                length_weeks=int(form.length_weeks.data),
                user_id=session['user_id'],
                is_active=True
            )
            db.session.add(program)
            db.session.commit()
            flash(f'Program "{program.name}" created successfully!', 'success')
            return redirect(url_for('edit_program', program_id=program.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Database error creating program: {str(e)}', 'error')
            return redirect(url_for('settings'))
    else:
        # Form validation failed - show specific errors
        error_messages = []
        for field, errors in form.errors.items():
            for error in errors:
                error_messages.append(f'{field}: {error}')
        
        flash(f'Form validation failed: {"; ".join(error_messages)}', 'error')
        return redirect(url_for('settings'))

@app.route('/set_active_program/<int:program_id>')
def set_active_program(program_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Deactivate all programs
    Program.query.filter_by(user_id=session['user_id']).update({'is_active': False})
    
    # Activate selected program
    program = Program.query.filter_by(id=program_id, user_id=session['user_id']).first()
    if program:
        program.is_active = True
        db.session.commit()
        flash(f'"{program.name}" is now your active program!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/edit_program/<int:program_id>')
def edit_program(program_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    program = Program.query.filter_by(id=program_id, user_id=user.id).first()
    if not program:
        flash('Program not found', 'error')
        return redirect(url_for('settings'))
    
    form = ProgramDayForm()
    return render_template('edit_program.html', program=program, form=form, user=user)

@app.route('/save_program_day/<int:program_id>', methods=['POST'])
def save_program_day(program_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get form data directly from request
    day_number = request.form.get('day_number')
    t1_exercise = request.form.get('t1_exercise')
    t1_start_weight = request.form.get('t1_start_weight')
    t1_increment = request.form.get('t1_increment')
    t2_exercise = request.form.get('t2_exercise')
    t2_start_weight = request.form.get('t2_start_weight')
    t2_increment = request.form.get('t2_increment')
    
    # Collect T3 exercises (only those that are filled in)
    t3_exercises = []
    
    # T3 Exercise 1
    t3_exercise_1 = request.form.get('t3_exercise_1')
    t3_start_weight_1 = request.form.get('t3_start_weight_1')
    t3_increment_1 = request.form.get('t3_increment_1')
    
    if t3_exercise_1 and t3_start_weight_1 and t3_start_weight_1.strip() != '' and t3_increment_1:
        t3_exercises.append({
            'name': t3_exercise_1,
            'start_weight': float(t3_start_weight_1),
            'increment': float(t3_increment_1)
        })
    
    # T3 Exercise 2
    t3_exercise_2 = request.form.get('t3_exercise_2')
    t3_start_weight_2 = request.form.get('t3_start_weight_2')
    t3_increment_2 = request.form.get('t3_increment_2')
    
    if t3_exercise_2 and t3_start_weight_2 and t3_start_weight_2.strip() != '' and t3_increment_2:
        t3_exercises.append({
            'name': t3_exercise_2,
            'start_weight': float(t3_start_weight_2),
            'increment': float(t3_increment_2)
        })
    
    # T3 Exercise 3
    t3_exercise_3 = request.form.get('t3_exercise_3')
    t3_start_weight_3 = request.form.get('t3_start_weight_3')
    t3_increment_3 = request.form.get('t3_increment_3')
    
    if t3_exercise_3 and t3_start_weight_3 and t3_start_weight_3.strip() != '' and t3_increment_3:
        t3_exercises.append({
            'name': t3_exercise_3,
            'start_weight': float(t3_start_weight_3),
            'increment': float(t3_increment_3)
        })
    
    # Validate required fields
    if not all([day_number, t1_exercise, t1_start_weight, t1_increment, t2_exercise, t2_start_weight, t2_increment]):
        flash('Please fill in all required fields', 'error')
        return redirect(url_for('edit_program', program_id=program_id))
    
    try:
        
        import json
        
        # Check if this day already exists
        existing_day = ProgramDay.query.filter_by(
            program_id=program_id, 
            day_number=int(day_number)
        ).first()
        
        if existing_day:
            # Update existing day
            existing_day.t1_exercise = t1_exercise
            existing_day.t1_start_weight = float(t1_start_weight)
            existing_day.t1_increment = float(t1_increment)
            existing_day.t2_exercise = t2_exercise
            existing_day.t2_start_weight = float(t2_start_weight)
            existing_day.t2_increment = float(t2_increment)
            existing_day.t3_exercises = json.dumps(t3_exercises)
            flash(f'Day {day_number} updated successfully!', 'success')
        else:
            # Create new day
            program_day = ProgramDay(
                program_id=program_id,
                day_number=int(day_number),
                t1_exercise=t1_exercise,
                t1_start_weight=float(t1_start_weight),
                t1_increment=float(t1_increment),
                t2_exercise=t2_exercise,
                t2_start_weight=float(t2_start_weight),
                t2_increment=float(t2_increment),
                t3_exercises=json.dumps(t3_exercises)
            )
            db.session.add(program_day)
            flash(f'Day {day_number} saved successfully!', 'success')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"Error saving program day: {str(e)}")
        flash(f'Error saving day: {str(e)}', 'error')
    
    return redirect(url_for('edit_program', program_id=program_id))

@app.route('/save_workout', methods=['POST'])
def save_workout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        data = request.get_json()
        user_id = session['user_id']
        day_number = data.get('day')
        exercises = data.get('exercises', [])
        
        # Get the active program and program day
        active_program = Program.query.filter_by(user_id=user_id, is_active=True).first()
        if not active_program:
            return jsonify({'success': False, 'message': 'No active program found'}), 400
        
        program_day = ProgramDay.query.filter_by(
            program_id=active_program.id, 
            day_number=day_number
        ).first()
        if not program_day:
            return jsonify({'success': False, 'message': 'Program day not found'}), 400
        
        # Calculate current week (simplified - you might want to make this more sophisticated)
        from datetime import datetime
        current_week = 1  # For now, assume week 1
        
        # Create workout log entry
        workout_log = WorkoutLog(
            user_id=user_id,
            program_id=active_program.id,
            program_day_id=program_day.id,
            week_number=current_week,
            date=datetime.now().date(),
            sets_completed=json.dumps(exercises)
        )
        
        db.session.add(workout_log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Workout saved successfully!'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error saving workout: {str(e)}")
        return jsonify({'success': False, 'message': f'Error saving workout: {str(e)}'}), 500

@app.route('/toggle_units')
def toggle_units():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    user.units = 'imperial' if user.units == 'metric' else 'metric'
    db.session.commit()
    flash(f'Switched to {user.units} units', 'info')
    return redirect(url_for('settings'))

@app.route('/track')
def track():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    active_program = Program.query.filter_by(user_id=user.id, is_active=True).first()
    
    if not active_program:
        flash('No active program found. Please create and set a program as active in Settings.', 'warning')
        return redirect(url_for('settings'))
    
    program_days = ProgramDay.query.filter_by(program_id=active_program.id).all()
    current_week = get_current_week()
    
    # Calculate current weights for each exercise and convert to JSON-serializable format
    serializable_program_days = []
    for day in program_days:
        # Parse T3 exercises
        t3_exercises = json.loads(day.t3_exercises)
        for exercise in t3_exercises:
            exercise['current_weight'] = calculate_current_weight(exercise['start_weight'], exercise['increment'], current_week)
        
        # Create serializable day object
        day_dict = {
            'day_number': day.day_number,
            't1_exercise': day.t1_exercise,
            't1_start_weight': day.t1_start_weight,
            't1_increment': day.t1_increment,
            't1_current_weight': calculate_current_weight(day.t1_start_weight, day.t1_increment, current_week),
            't2_exercise': day.t2_exercise,
            't2_start_weight': day.t2_start_weight,
            't2_increment': day.t2_increment,
            't2_current_weight': calculate_current_weight(day.t2_start_weight, day.t2_increment, current_week),
            't3_exercises': json.dumps(t3_exercises),
            't3_exercises_parsed': t3_exercises
        }
        serializable_program_days.append(day_dict)
    
    # Get recent workout logs (last 5 workouts)
    recent_workouts = WorkoutLog.query.filter_by(user_id=user.id).order_by(WorkoutLog.date.desc()).limit(5).all()
    
    return render_template('track.html', active_program=active_program, program_days=program_days, serializable_program_days=serializable_program_days, user=user, current_week=current_week, recent_workouts=recent_workouts)

@app.route('/log_workout', methods=['POST'])
def log_workout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Simple workout logging - can be enhanced
    flash('Workout logged successfully!', 'success')
    return redirect(url_for('track'))

@app.route('/workout_history')
def workout_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    # Get all workout logs for the user, ordered by date (newest first)
    workout_logs = WorkoutLog.query.filter_by(user_id=user.id).order_by(WorkoutLog.date.desc()).all()
    
    return render_template('workout_history.html', workout_logs=workout_logs, user=user)

@app.route('/delete_workout/<int:workout_id>')
def delete_workout(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    workout_log = WorkoutLog.query.get(workout_id)
    if not workout_log or workout_log.user_id != session['user_id']:
        flash('Workout not found or access denied.', 'error')
        return redirect(url_for('workout_history'))
    
    db.session.delete(workout_log)
    db.session.commit()
    flash('Workout deleted successfully!', 'success')
    return redirect(url_for('workout_history'))

@app.route('/edit_workout/<int:workout_id>')
def edit_workout(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    workout_log = WorkoutLog.query.get(workout_id)
    if not workout_log or workout_log.user_id != session['user_id']:
        flash('Workout not found or access denied.', 'error')
        return redirect(url_for('workout_history'))
    
    # Get the program day details
    program_day = ProgramDay.query.get(workout_log.program_day_id)
    program = Program.query.get(workout_log.program_id)
    
    return render_template('edit_workout.html', 
                         workout_log=workout_log, 
                         program_day=program_day, 
                         program=program,
                         user=User.query.get(session['user_id']))

@app.route('/update_workout/<int:workout_id>', methods=['POST'])
def update_workout(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    workout_log = WorkoutLog.query.get(workout_id)
    if not workout_log or workout_log.user_id != session['user_id']:
        flash('Workout not found or access denied.', 'error')
        return redirect(url_for('workout_history'))
    
    # Update workout details
    workout_log.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
    workout_log.sets_completed = request.form.get('sets_completed', '')
    
    db.session.commit()
    flash('Workout updated successfully!', 'success')
    return redirect(url_for('workout_history'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)

