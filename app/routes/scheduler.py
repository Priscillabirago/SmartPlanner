from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for
from flask import flash, jsonify
from flask_login import login_required, current_user

from models.database import db, Subject, StudySession
from models.scheduler import StudyScheduler, GHANA_TZ

scheduler = Blueprint('scheduler', __name__, url_prefix='/scheduler')


@scheduler.route('/')
@login_required
def index():
    """Show scheduler options and current schedule."""
    # Get user's subjects
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    
    # Get current schedule
    now = datetime.now(GHANA_TZ)
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
    now = datetime.now(GHANA_TZ)
    
    # Get scheduling parameters
    start_date_str = request.form.get('start_date')
    days = request.form.get('days', type=int, default=7)
    
    # Parse start date if provided, otherwise use today
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            # Set time to current time
            current_time = datetime.now(GHANA_TZ)
            start_date = start_date.replace(
                hour=current_time.hour, 
                minute=current_time.minute, 
                second=current_time.second
            )
            start_date = GHANA_TZ.localize(start_date)
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
        return redirect(url_for('scheduler.index'))
    
    # Save schedule to database
    schedule_generator.save_schedule_to_db(schedule, db)
    
    flash(f'Successfully generated a study schedule for {days} days!', 'success')
    return redirect(url_for('scheduler.index'))


@scheduler.route('/session/<int:session_id>', methods=['GET', 'POST'])
@login_required
def session_details(session_id):
    """View and update session details."""
    session = StudySession.query.get_or_404(session_id)
    
    # Security check: ensure the session belongs to the current user
    if session.user_id != current_user.id:
        flash('You do not have permission to view this session.', 'danger')
        return redirect(url_for('scheduler.index'))
    
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
        return redirect(url_for('scheduler.index'))
    
    db.session.delete(session)
    db.session.commit()
    
    flash('Study session deleted successfully!', 'success')
    return redirect(url_for('scheduler.index'))


@scheduler.route('/reschedule', methods=['POST'])
@login_required
def reschedule_session():
    """Reschedule a study session to a different time."""
    data = request.get_json()  # Get JSON data instead of form data
    
    session_id = data.get('session_id')
    new_date_str = data.get('new_date')
    new_time_str = data.get('new_time')
    
    if not session_id or not new_date_str or not new_time_str:
        return jsonify({'success': False, 'message': 'Missing required data'}), 400
    
    # If session_id is not numeric, it might be a composite ID (from calendar)
    if isinstance(session_id, str) and '-' in session_id:
        # Try to find the session by date/time/subject
        parts = session_id.split('-')
        subject_name = parts[0]
        date_str = parts[1]
        time_str = parts[2] if len(parts) > 2 else None
        
        # Find the subject by name
        subject = Subject.query.filter_by(
            user_id=current_user.id, 
            name=subject_name
        ).first()
        
        if not subject or not time_str:
            return jsonify({'success': False, 'message': 'Session not found'}), 404
        
        # Find the session that matches
        try:
            # Convert composite strings to datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            session_start = GHANA_TZ.localize(datetime.combine(date_obj, time_obj))
            
            # Find sessions that start at this time for this subject
            session = StudySession.query.filter(
                StudySession.user_id == current_user.id,
                StudySession.subject_id == subject.id,
                StudySession.start_time == session_start
            ).first()
            
            if not session:
                return jsonify({'success': False, 'message': 'Session not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error finding session: {str(e)}'}), 400
    else:
        # Find by numeric ID
        session = StudySession.query.get(session_id)
        if not session:
            return jsonify({'success': False, 'message': 'Session not found'}), 404
    
    # Security check: ensure the session belongs to the current user
    if session.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        # Parse new date and time
        new_datetime_str = f"{new_date_str} {new_time_str}"
        naive_datetime = datetime.strptime(new_datetime_str, '%Y-%m-%d %H:%M')
        # Add Ghana timezone information to make it timezone-aware
        new_start_time = GHANA_TZ.localize(naive_datetime)
        
        # Calculate session duration
        duration = session.end_time - session.start_time
        
        # Set new start and end times
        session.start_time = new_start_time
        session.end_time = new_start_time + duration
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Session rescheduled successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error rescheduling: {str(e)}'
        }), 400 