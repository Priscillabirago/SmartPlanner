from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user

from models.database import db, Subject, StudySession

main = Blueprint('main', __name__)


@main.route('/')
def index():
    """Render the home page."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html')


@main.route('/dashboard')
@login_required
def dashboard():
    """Render the user dashboard with summary of schedule and subjects."""
    # Get user's subjects
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    
    # Get upcoming study sessions (next 3 days)
    now = datetime.now()
    three_days_later = now + timedelta(days=3)
    
    upcoming_sessions = StudySession.query.filter(
        StudySession.user_id == current_user.id,
        StudySession.start_time >= now,
        StudySession.start_time <= three_days_later
    ).order_by(StudySession.start_time).all()
    
    # Get today's sessions
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    today_sessions = StudySession.query.filter(
        StudySession.user_id == current_user.id,
        StudySession.start_time >= today_start,
        StudySession.start_time < today_end
    ).order_by(StudySession.start_time).all()
    
    # Calculate study statistics
    total_sessions = StudySession.query.filter_by(
        user_id=current_user.id).count()
    completed_sessions = StudySession.query.filter_by(
        user_id=current_user.id, completed=True).count()
    
    completion_rate = 0
    if total_sessions > 0:
        completion_rate = (completed_sessions / total_sessions) * 100
    
    # Calculate subject distribution (hours per subject)
    subject_hours = {}
    for subject in subjects:
        subject_sessions = StudySession.query.filter_by(
            user_id=current_user.id, subject_id=subject.id).all()
        
        total_hours = sum(session.duration_minutes() for session in subject_sessions) / 60
        subject_hours[subject.name] = {
            'hours': round(total_hours, 1),
            'color': subject.color if hasattr(subject, 'color') else "#3498db"
        }
    
    return render_template(
        'main/dashboard.html',
        subjects=subjects,
        upcoming_sessions=upcoming_sessions,
        today_sessions=today_sessions,
        total_sessions=total_sessions,
        completed_sessions=completed_sessions,
        completion_rate=round(completion_rate, 1),
        subject_hours=subject_hours
    )


@main.route('/calendar')
@login_required
def calendar():
    """Render the calendar view of study sessions."""
    # Get all study sessions for this user
    sessions = StudySession.query.filter_by(user_id=current_user.id).all()
    
    # Format sessions for calendar
    events = []
    for session in sessions:
        subject = Subject.query.get(session.subject_id)
        if not subject:
            continue
            
        events.append({
            'id': session.id,
            'title': subject.name,
            'start': session.start_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'end': session.end_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'color': subject.color if hasattr(subject, 'color') else "#3498db",
            'completed': session.completed
        })
    
    return render_template('main/calendar.html', events=events)


@main.route('/mark_completed/<int:session_id>', methods=['POST'])
@login_required
def mark_completed(session_id):
    """Mark a study session as completed."""
    session = StudySession.query.get_or_404(session_id)
    
    # Security check: ensure the session belongs to the current user
    if session.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    session.completed = True
    db.session.commit()
    
    return jsonify({'success': True}) 