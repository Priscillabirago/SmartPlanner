from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, abort
from flask import url_for, flash, jsonify
from flask_login import login_required, current_user

from models.database import db, Subject, StudySession, Task

subjects = Blueprint('subjects', __name__, url_prefix='/subjects')

INDEX_ROUTE = 'subjects.index'
ADD_ROUTE = 'subjects.add'
EDIT_ROUTE = 'subjects.edit'
TASKS_ROUTE = 'subjects.tasks'


@subjects.route('/')
@login_required
def index():
    """List all subjects for the current user."""
    user_subjects = Subject.query.filter_by(
        user_id=current_user.id).order_by(Subject.priority.desc()).all()
    
    return render_template('subjects/index.html', subjects=user_subjects)


@subjects.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add a new subject."""
    if request.method == 'POST':
        name = request.form.get('name')
        workload = request.form.get('workload', type=int)
        priority = request.form.get('priority', type=int)
        difficulty = request.form.get('difficulty', type=int)
        color = request.form.get('color', '#3498db')
        notes = request.form.get('notes', '')
        
        # Parse exam date if provided
        exam_date_str = request.form.get('exam_date')
        exam_date = None
        if exam_date_str:
            try:
                # Create datetime
                exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d')
                # Set time to end of day (23:59:59)
                exam_date = exam_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                flash('Invalid exam date format. Please use YYYY-MM-DD.', 'danger')
                return redirect(url_for(ADD_ROUTE))
        
        # Validate required fields
        if not name:
            flash('Subject name is required.', 'danger')
            return redirect(url_for(ADD_ROUTE))
        
        if not workload or workload < 1:
            flash('Workload must be at least 1 hour per week.', 'danger')
            return redirect(url_for(ADD_ROUTE))
        
        if not priority or priority < 1 or priority > 5:
            flash('Priority must be between 1 and 5.', 'danger')
            return redirect(url_for(ADD_ROUTE))
        
        # Create new subject
        new_subject = Subject(
            user_id=current_user.id,
            name=name,
            workload=workload,
            priority=priority,
            difficulty=difficulty,
            exam_date=exam_date,
            color=color,
            notes=notes
        )
        
        db.session.add(new_subject)
        db.session.commit()
        
        flash(f'Subject "{name}" added successfully!', 'success')
        return redirect(url_for(INDEX_ROUTE))
    
    return render_template('subjects/add.html')


def _validate_subject(subject):
    """Validate subject fields and return error message if invalid."""
    if not subject.name:
        return 'Subject name is required.'
    if not subject.workload or subject.workload < 1:
        return 'Workload must be at least 1 hour per week.'
    if not subject.priority or subject.priority < 1 or subject.priority > 5:
        return 'Priority must be between 1 and 5.'
    return None


def _parse_exam_date(exam_date_str):
    """Parse exam date string and return datetime or None."""
    if not exam_date_str:
        return None
    try:
        exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d')
        return exam_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        return False  # False indicates parsing error


@subjects.route('/edit/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def edit(subject_id):
    """Edit an existing subject."""
    subject = Subject.query.get_or_404(subject_id)
    
    if subject.user_id != current_user.id:
        flash('You do not have permission to edit this subject.', 'danger')
        return redirect(url_for(INDEX_ROUTE))
    
    if request.method == 'POST':
        subject.name = request.form.get('name')
        subject.workload = request.form.get('workload', type=int)
        subject.priority = request.form.get('priority', type=int)
        subject.difficulty = request.form.get('difficulty', type=int)
        subject.color = request.form.get('color', '#3498db')
        subject.notes = request.form.get('notes', '')
        
        exam_date = _parse_exam_date(request.form.get('exam_date'))
        if exam_date is False:
            flash('Invalid exam date format. Please use YYYY-MM-DD.', 'danger')
            return redirect(url_for(EDIT_ROUTE, subject_id=subject.id))
        subject.exam_date = exam_date
        
        error = _validate_subject(subject)
        if error:
            flash(error, 'danger')
            return redirect(url_for(EDIT_ROUTE, subject_id=subject.id))
        
        db.session.commit()
        flash(f'Subject "{subject.name}" updated successfully!', 'success')
        return redirect(url_for(INDEX_ROUTE))
    
    return render_template('subjects/edit.html', subject=subject)


@subjects.route('/delete/<int:subject_id>', methods=['POST'])
@login_required
def delete(subject_id):
    """Delete a subject."""
    subject = Subject.query.get_or_404(subject_id)
    
    # Security check: ensure the subject belongs to the current user
    if subject.user_id != current_user.id:
        flash('You do not have permission to delete this subject.', 'danger')
        return redirect(url_for(INDEX_ROUTE))
    
    subject_name = subject.name
    
    # Delete all associated study sessions
    StudySession.query.filter_by(subject_id=subject_id).delete()
    
    # Delete all associated tasks
    Task.query.filter_by(subject_id=subject_id).delete()
    
    # Delete the subject
    db.session.delete(subject)
    db.session.commit()
    
    flash(f'Subject "{subject_name}" deleted successfully!', 'success')
    return redirect(url_for(INDEX_ROUTE))


@subjects.route('/tasks/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def tasks(subject_id):
    """Manage tasks for a specific subject."""
    subject = Subject.query.get_or_404(subject_id)
    
    # Security check: ensure the subject belongs to the current user
    if subject.user_id != current_user.id:
        abort(403)
    
    # Handle new task submission
    if request.method == 'POST':
        title = request.form.get('title')
        if not title:
            flash('Task title is required', 'danger')
            return redirect(url_for(TASKS_ROUTE, subject_id=subject_id))
        
        # Get other form fields
        description = request.form.get('description', '')
        priority = int(request.form.get('priority', 3))
        estimated_time = int(request.form.get('estimated_time', 30))
        
        # Parse deadline if provided
        deadline = None
        deadline_str = request.form.get('deadline')
        if deadline_str:
            try:
                # Create a datetime from the string
                deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid deadline format', 'danger')
        
        # Create the task
        task = Task(
            title=title,
            description=description,
            priority=priority,
            estimated_time=estimated_time,
            deadline=deadline,
            subject_id=subject_id,
            user_id=current_user.id
        )
        
        db.session.add(task)
        db.session.commit()
        
        flash('Task added successfully', 'success')
        return redirect(url_for(TASKS_ROUTE, subject_id=subject_id))
    
    # Get all tasks for this subject
    tasks = Task.query.filter_by(subject_id=subject_id).order_by(
        Task.completed, Task.deadline, Task.priority.desc()).all()
    
    # Get current time for deadline comparison
    now = datetime.now(timezone.utc)
    
    return render_template('subjects/tasks.html', subject=subject, tasks=tasks, now=now)


@subjects.route('/task/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    """Edit an existing task."""
    task = Task.query.get_or_404(task_id)
    
    # Security check: ensure the task belongs to the current user
    if task.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        task.title = request.form.get('title')
        task.description = request.form.get('description', '')
        task.priority = int(request.form.get('priority', 3))
        task.estimated_time = int(request.form.get('estimated_time', 30))
        
        # Parse deadline if provided
        deadline_str = request.form.get('deadline')
        if deadline_str:
            try:
                task.deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid deadline format', 'danger')
                return redirect(url_for('subjects.edit_task', task_id=task_id))
        else:
            task.deadline = None
        
        db.session.commit()
        flash('Task updated successfully!', 'success')
        return redirect(url_for(TASKS_ROUTE, subject_id=task.subject_id))
    
    return render_template('subjects/edit_task.html', task=task)


@subjects.route('/task/complete/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    """Mark a task as completed."""
    task = Task.query.get_or_404(task_id)
    
    # Security check: ensure the task belongs to the current user
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    task.completed = True
    db.session.commit()
    
    return jsonify({'success': True})


@subjects.route('/task/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    """Delete a task."""
    task = Task.query.get_or_404(task_id)
    
    # Security check: ensure the task belongs to the current user
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    subject_id = task.subject_id
    db.session.delete(task)
    db.session.commit()
    
    flash('Task deleted successfully!', 'success')
    return redirect(url_for(TASKS_ROUTE, subject_id=subject_id)) 