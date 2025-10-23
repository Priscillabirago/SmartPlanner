from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for
from flask import flash, jsonify
from flask_login import login_required, current_user

from models.database import db, Subject, StudySession
from models.scheduler import StudyScheduler

scheduler = Blueprint('scheduler', __name__, url_prefix='/scheduler')

INDEX_ROUTE = 'scheduler.index'

@scheduler.route('/')
@login_required
def index():
    """Show scheduler options and current schedule."""
    # Get user's subjects
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    
    # Get current schedule
    now = datetime.now()
    one_week_ahead = now + timedelta(days=7)
    
    current_schedule = StudySession.query.filter(
        StudySession.user_id == current_user.id,
        StudySession.start_time >= now,
        StudySession.start_time <= one_week_ahead
    ).order_by(StudySession.start_time).all()
    
    # Group sessions by day for better display
    days = {}
    for session in current_schedule:
        day = session.start_time.strftime('%Y-%m-%d')
        if day not in days:
            days[day] = []
        days[day].append(session)
    
    return render_template(
        'scheduler/index.html',
        subjects=subjects,
        schedule_days=days,
        now=now,
        datetime=datetime,
        timedelta=timedelta
    )


@scheduler.route('/generate', methods=['POST'])
@login_required
def generate():
    """Generate a new study schedule."""
    # Get user's subjects
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    
    if not subjects:
        flash('You need to add subjects before generating a schedule.', 'warning')
        return redirect(url_for('subjects.index'))
    
    # ALWAYS clear existing future sessions to prevent overlaps
    now = datetime.now()
    
    # Get scheduling parameters
    start_date_str = request.form.get('start_date')
    days = request.form.get('days', type=int, default=7)
    
    # Parse start date if provided, otherwise use today
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            # Set time to current time
            current_time = datetime.now()
            start_date = start_date.replace(
                hour=current_time.hour, 
                minute=current_time.minute, 
                second=current_time.second
            )
        except ValueError:
            flash('Invalid start date format. Using today instead.', 'warning')
            start_date = now
    else:
        start_date = now
    
    # Calculate end date based on the provided days
    end_date = start_date + timedelta(days=days)
    
    # Always delete ALL future sessions to prevent overlaps
    StudySession.query.filter(
        StudySession.user_id == current_user.id,
        StudySession.start_time >= start_date
    ).delete()
    
    db.session.commit()
    
    # Create scheduler with user preferences
    schedule_generator = StudyScheduler(
        user=current_user,
        subjects=subjects,
        start_date=start_date,
        end_date=end_date
    )
    
    # Generate schedule
    schedule = schedule_generator.generate_schedule()
    
    if not schedule:
        flash(
            'Could not generate a schedule. Please check your study preferences '
            'and make sure you have available study hours.', 
            'warning'
        )
        return redirect(url_for(INDEX_ROUTE))
    
    # Save schedule to database
    schedule_generator.save_schedule_to_db(schedule, db)
    
    flash(f'Successfully generated a study schedule for {days} days!', 'success')
    return redirect(url_for(INDEX_ROUTE))


@scheduler.route('/session/<int:session_id>', methods=['GET', 'POST'])
@login_required
def session_details(session_id):
    """View and update session details."""
    session = StudySession.query.get_or_404(session_id)
    
    # Security check: ensure the session belongs to the current user
    if session.user_id != current_user.id:
        flash('You do not have permission to view this session.', 'danger')
        return redirect(url_for(INDEX_ROUTE))
    
    subject = Subject.query.get(session.subject_id)
    
    if request.method == 'POST':
        # Update session details
        completed = request.form.get('completed') == 'on'
        productivity = request.form.get('productivity_rating', type=int)
        notes = request.form.get('notes', '')
        location = request.form.get('location', '')
        
        session.completed = completed
        session.productivity_rating = productivity
        session.notes = notes
        session.location = location
        
        db.session.commit()
        
        flash('Session updated successfully!', 'success')
        return redirect(url_for('scheduler.session_details', session_id=session.id))
    
    return render_template(
        'scheduler/session.html',
        session=session,
        subject=subject
    )


@scheduler.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    """Delete a study session."""
    session = StudySession.query.get_or_404(session_id)
    
    # Security check: ensure the session belongs to the current user
    if session.user_id != current_user.id:
        flash('You do not have permission to delete this session.', 'danger')
        return redirect(url_for(INDEX_ROUTE))
    
    db.session.delete(session)
    db.session.commit()
    
    flash('Study session deleted successfully!', 'success')
    return redirect(url_for(INDEX_ROUTE))


def _find_session_by_composite_id(session_id):
    """Find a session using composite ID format (subject-date-time)."""
    parts = session_id.split('-')
    subject_name = parts[0]
    date_str = parts[1]
    time_str = parts[2] if len(parts) > 2 else None
    
    subject = Subject.query.filter_by(
        user_id=current_user.id, 
        name=subject_name
    ).first()
    
    if not subject or not time_str:
        return None
    
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    time_obj = datetime.strptime(time_str, '%H:%M').time()
    session_start = datetime.combine(date_obj, time_obj)
    
    return StudySession.query.filter(
        StudySession.user_id == current_user.id,
        StudySession.subject_id == subject.id,
        StudySession.start_time == session_start
    ).first()


def _get_session(session_id):
    """Get session by ID (numeric or composite)."""
    if isinstance(session_id, str) and '-' in session_id:
        try:
            return _find_session_by_composite_id(session_id)
        except Exception:
            return None
    return StudySession.query.get(session_id)


@scheduler.route('/reschedule', methods=['POST'])
@login_required
def reschedule_session():
    """Reschedule a study session to a different time."""
    data = request.get_json()
    
    session_id = data.get('session_id')
    new_date_str = data.get('new_date')
    new_time_str = data.get('new_time')
    
    if not session_id or not new_date_str or not new_time_str:
        return jsonify({'success': False, 'message': 'Missing required data'}), 400
    
    session = _get_session(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'}), 404
    
    if session.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        new_datetime_str = f"{new_date_str} {new_time_str}"
        new_start_time = datetime.strptime(new_datetime_str, '%Y-%m-%d %H:%M')
        
        duration = session.end_time - session.start_time
        session.start_time = new_start_time
        session.end_time = new_start_time + duration
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Session rescheduled successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error rescheduling: {str(e)}'}), 400 