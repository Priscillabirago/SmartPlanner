from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models.database import db, User, StudyPreference
from utils.timezone_utils import get_common_timezones

auth = Blueprint('auth', __name__)

DASHBOARD_ROUTE = 'main.dashboard'
LOGIN_ROUTE = 'auth.login'
REGISTER_ROUTE = 'auth.register'

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for(DASHBOARD_ROUTE))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(email=email).first()
        
        # Check if user exists and password is correct
        if not user or not user.check_password(password):
            flash('Please check your login details and try again.', 'danger')
            return redirect(url_for(LOGIN_ROUTE))
        
        # If validation passes, log in the user
        login_user(user, remember=remember)
        
        # Redirect to the page they wanted to access or dashboard
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for(DASHBOARD_ROUTE))
    
    return render_template('auth/login.html')


@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration."""
    if current_user.is_authenticated:
        return redirect(url_for(DASHBOARD_ROUTE))
    
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')
        username = request.form.get('username')
        name = request.form.get('name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        school = request.form.get('school')
        grade_level = request.form.get('grade_level')
        study_hours = request.form.get('study_hours_per_week', type=int)
        
        # Validate passwords match
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for(REGISTER_ROUTE))
        
        # Check if email already exists
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email address already exists!', 'danger')
            return redirect(url_for(REGISTER_ROUTE))
        
        # Check if username already exists
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists!', 'danger')
            return redirect(url_for(REGISTER_ROUTE))
        
        # Create new user
        new_user = User(
            email=email,
            username=username,
            name=name,
            school=school,
            grade_level=grade_level,
            study_hours_per_week=study_hours or 10  # Default to 10 if not provided
        )
        new_user.set_password(password)
        
        # Add user to database
        db.session.add(new_user)
        db.session.flush()  # Get the user ID before committing
        
        # Create default study preferences
        preferences = StudyPreference(user_id=new_user.id)
        db.session.add(preferences)
        
        # Commit changes
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for(LOGIN_ROUTE))
    
    return render_template('auth/register.html')


@auth.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for(LOGIN_ROUTE))


@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Handle user profile viewing and editing."""
    user = current_user
    
    if request.method == 'POST':
        # Update user information
        user.name = request.form.get('name')
        user.school = request.form.get('school')
        user.grade_level = request.form.get('grade_level')
        user.timezone = request.form.get('timezone', 'UTC')
        user.study_hours_per_week = request.form.get('study_hours_per_week', type=int)
        user.academic_goals = request.form.get('academic_goals')
        
        # Update study preferences
        preferences = StudyPreference.query.filter_by(user_id=user.id).first()
        if not preferences:
            preferences = StudyPreference(user_id=user.id)
            db.session.add(preferences)
        
        preferences.max_consecutive_hours = request.form.get('max_consecutive_hours', type=int, default=2)
        preferences.break_duration = request.form.get('break_duration', type=int, default=15)
        preferences.preferred_session_length = request.form.get('preferred_session_length', type=int, default=60)
        preferences.weekend_study = bool(request.form.get('weekend_study'))
        
        # Update preferred study times
        preferred_times = {
            "morning": bool(request.form.get('morning')),
            "afternoon": bool(request.form.get('afternoon')),
            "evening": bool(request.form.get('evening')),
            "night": bool(request.form.get('night'))
        }
        user.set_preferred_times(preferred_times)
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))
    
    # For GET request, fetch the current preferences
    try:
        preferences = StudyPreference.query.filter_by(user_id=user.id).first()
        if not preferences:
            preferences = StudyPreference(user_id=user.id)
            db.session.add(preferences)
            db.session.commit()
    except Exception:
        preferences = None
    
    timezones = get_common_timezones()
    return render_template('auth/profile.html', user=user, preferences=preferences, timezones=timezones) 