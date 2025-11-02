from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for
from flask import flash, jsonify, session
from flask_login import login_required, current_user

from models.database import db, Subject, StudySession, SessionStatus, SessionType, Task
from models.scheduler import StudyScheduler
from utils.timezone_utils import localize_to_utc, utc_to_local

scheduler = Blueprint('scheduler', __name__, url_prefix='/scheduler')

INDEX_ROUTE = 'scheduler.index'

@scheduler.route('/')
@login_required
def index():
    """Show scheduler options and current schedule."""
    # Get user's subjects
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    
    # Get current schedule
    now_utc = datetime.now(timezone.utc)
    now_local = utc_to_local(now_utc, current_user.timezone)
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = localize_to_utc(today_start_local.replace(tzinfo=None), current_user.timezone)
    one_week_ahead = today_start_utc + timedelta(days=7)
    
    current_schedule = StudySession.query.filter(
        StudySession.user_id == current_user.id,
        StudySession.start_time >= today_start_utc,
        StudySession.start_time <= one_week_ahead
    ).order_by(StudySession.start_time).all()
    
    # Group sessions by day for better display
    days = {}
    for study_session in current_schedule:
        local_start = utc_to_local(study_session.start_time, current_user.timezone)
        day = local_start.strftime('%Y-%m-%d')
        days.setdefault(day, []).append(study_session)
    days = dict(sorted(days.items()))
    
    from flask import session as flask_session
    urgent_warnings = flask_session.pop('urgent_warnings', [])

    return render_template(
        'scheduler/index.html',
        subjects=subjects,
        schedule_days=days,
        now=now_local,
        urgent_warnings=urgent_warnings,
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
    now = datetime.now(timezone.utc)
    
    # Get scheduling parameters
    start_date_str = request.form.get('start_date')
    days = request.form.get('days', type=int, default=7)
    
    # Parse start date if provided, otherwise use today
    delete_from = None  # UTC datetime from which existing sessions will be cleared
    if start_date_str:
        try:
            # Parse as naive datetime (user's local date)
            naive_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            # Get current time in user's timezone
            current_time_utc = datetime.now(timezone.utc)
            current_time_local = utc_to_local(current_time_utc, current_user.timezone)
            # Combine date from input with current time
            naive_dt = naive_date.replace(
                hour=current_time_local.hour,
                minute=current_time_local.minute,
                second=current_time_local.second
            )
            # Convert to UTC for storage
            start_date = localize_to_utc(naive_dt, current_user.timezone)
            # Delete any existing sessions for that day starting at local midnight
            delete_from = localize_to_utc(
                naive_date.replace(hour=0, minute=0, second=0, microsecond=0),
                current_user.timezone
            )
        except ValueError:
            flash('Invalid start date format. Using today instead.', 'warning')
            start_date = now
    else:
        start_date = now
    
    if delete_from is None:
        # Align deletion to the user's local midnight for the selected day
        local_start = utc_to_local(start_date, current_user.timezone)
        local_midnight = local_start.replace(hour=0, minute=0, second=0, microsecond=0)
        delete_from = localize_to_utc(local_midnight.replace(tzinfo=None), current_user.timezone)
    
    # Calculate end date based on the provided days
    end_date = start_date + timedelta(days=days)
    
    # Check for urgent tasks and warn if hours are insufficient
    temp_scheduler = StudyScheduler(
        user=current_user,
        subjects=subjects,
        start_date=start_date,
        end_date=end_date
    )
    
    urgency_check = temp_scheduler.check_urgent_task_coverage()
    if urgency_check['warnings']:
        session['urgent_warnings'] = urgency_check['warnings']
        for warning in urgency_check['warnings']:
            flash(f"⚠️ {warning['message']} {warning['suggestion']}", 'warning')
    
    # Delete future sessions EXCEPT locked ones and completed ones
    # Locked sessions represent manual edits the user wants to keep
    # Completed sessions are historical records
    StudySession.query.filter(
        StudySession.user_id == current_user.id,
        StudySession.start_time >= delete_from,
        StudySession.locked == False,
        StudySession.status.in_([SessionStatus.planned, SessionStatus.missed])
    ).delete(synchronize_session=False)
    
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
        status_str = request.form.get('status', 'planned')
        session_type_str = request.form.get('session_type', 'learn')
        task_id = request.form.get('task_id', type=int) or None
        productivity = request.form.get('productivity_rating', type=int)
        notes = request.form.get('notes', '')
        location = request.form.get('location', '')
        
        # Update status enum
        try:
            session.status = SessionStatus[status_str]
            session.completed = (session.status == SessionStatus.completed)  # Backward compatibility
        except KeyError:
            session.status = SessionStatus.planned
        
        # Update session type enum
        try:
            session.session_type = SessionType[session_type_str]
        except KeyError:
            session.session_type = SessionType.learn
        
        session.task_id = task_id
        session.productivity_rating = productivity
        session.notes = notes
        session.location = location
        
        db.session.commit()
        
        flash('Session updated successfully!', 'success')
        return redirect(url_for('scheduler.session_details', session_id=session.id))
    
    # Get all tasks for the subject to allow linking
    tasks = Task.query.filter_by(
        user_id=current_user.id, 
        subject_id=session.subject_id,
        completed=False
    ).order_by(Task.deadline.asc()).all()
    
    return render_template(
        'scheduler/session.html',
        session=session,
        subject=subject,
        tasks=tasks
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


@scheduler.route('/toggle_lock/<int:session_id>', methods=['POST'])
@login_required
def toggle_lock(session_id):
    """Toggle the locked status of a session.
    
    Locked sessions are preserved during schedule regeneration and treated as
    busy times that the scheduler must work around.
    """
    session = StudySession.query.get_or_404(session_id)
    
    # Security check: ensure the session belongs to the current user
    if session.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Toggle the locked status
    session.locked = not session.locked
    db.session.commit()
    
    action = 'locked' if session.locked else 'unlocked'
    return jsonify({
        'success': True, 
        'locked': session.locked,
        'message': f'Session {action} successfully'
    })


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