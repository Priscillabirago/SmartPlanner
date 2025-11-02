from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user

from models.database import db, Subject, StudySession, SessionStatus
from models.metrics import get_study_statistics
from utils.timezone_utils import utc_to_local, localize_to_utc

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
    
    # Get study statistics (planned vs actual, quality)
    study_stats = get_study_statistics(current_user.id)
    
    # Get upcoming study sessions (next 3 days) in user's timezone
    now_utc = datetime.now(timezone.utc)
    now_local = utc_to_local(now_utc, current_user.timezone)

    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end_local = today_start_local + timedelta(days=1)

    today_start_utc = localize_to_utc(today_start_local.replace(tzinfo=None), current_user.timezone)
    today_end_utc = localize_to_utc(today_end_local.replace(tzinfo=None), current_user.timezone)

    upcoming_end_local = now_local + timedelta(days=3)
    upcoming_end_utc = localize_to_utc(upcoming_end_local.replace(tzinfo=None), current_user.timezone)

    upcoming_sessions = StudySession.query.filter(
        StudySession.user_id == current_user.id,
        StudySession.start_time >= now_utc,
        StudySession.start_time <= upcoming_end_utc
    ).order_by(StudySession.start_time).all()

    # Get today's sessions
    today_sessions = StudySession.query.filter(
        StudySession.user_id == current_user.id,
        StudySession.start_time >= today_start_utc,
        StudySession.start_time < today_end_utc
    ).order_by(StudySession.start_time).all()
    
    # Calculate study statistics
    total_sessions = StudySession.query.filter_by(
        user_id=current_user.id).count()
    completed_sessions = StudySession.query.filter_by(
        user_id=current_user.id, status=SessionStatus.completed).count()
    
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
        subject_hours=subject_hours,
        study_stats=study_stats
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

        start_local = utc_to_local(session.start_time, current_user.timezone)
        end_local = utc_to_local(session.end_time, current_user.timezone)
        
        events.append({
            'id': session.id,
            'title': subject.name,
            'start': start_local.isoformat(),
            'end': end_local.isoformat(),
            'color': subject.color if hasattr(subject, 'color') else "#3498db",
            'completed': session.completed
        })
    
    return render_template('main/calendar.html', events=events)


@main.route('/mark_completed/<int:session_id>', methods=['POST'])
@login_required
def mark_completed(session_id):
    """Mark a study session as completed with optional actual time."""
    from flask import request
    
    session = StudySession.query.get_or_404(session_id)
    
    # Security check: ensure the session belongs to the current user
    if session.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Get actual minutes from request (optional)
    data = request.get_json(silent=True) or {}
    actual_minutes = data.get('actual_minutes')
    productivity_rating = data.get('productivity_rating')
    
    session.status = SessionStatus.completed
    session.completed = True  # Keep for backward compatibility
    session.completed_at = datetime.now(timezone.utc)
    
    # If actual_minutes provided, use it; otherwise defaults to planned time
    if actual_minutes is not None:
        session.actual_minutes = int(actual_minutes)
    
    # If productivity rating provided
    if productivity_rating is not None:
        session.productivity_rating = int(productivity_rating)
    
    db.session.commit()
    
    return jsonify({'success': True}) 